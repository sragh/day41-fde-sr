"""In-process metrics: labelled counters, gauges and fixed-bucket histograms."""
import threading
from collections import defaultdict

LATENCY_BUCKETS_MS = (50, 100, 250, 500, 1000, 2000, 5000)

_LOCK = threading.Lock()
COUNTERS: dict = defaultdict(int)
GAUGES: dict = {}
HISTOGRAMS: dict = {}


def _key(name: str, labels: dict | None):
    return (name, tuple(sorted((labels or {}).items())))


def inc(name: str, value=1, **labels):
    with _LOCK:
        COUNTERS[_key(name, labels)] += value


def set_gauge(name: str, value, **labels):
    with _LOCK:
        GAUGES[_key(name, labels)] = value


def observe(name: str, value: float, buckets=LATENCY_BUCKETS_MS, **labels):
    with _LOCK:
        h = HISTOGRAMS.setdefault(
            _key(name, labels),
            {'buckets': buckets, 'counts': [0] * (len(buckets) + 1), 'sum': 0.0, 'count': 0},
        )
        h['sum'] += value
        h['count'] += 1
        for i, bound in enumerate(h['buckets']):
            if value <= bound:
                h['counts'][i] += 1
                return
        h['counts'][-1] += 1


def quantile(h: dict, q: float) -> float | None:
    """Upper bound of the bucket holding the q-quantile (conservative)."""
    if not h['count']:
        return None
    target = q * h['count']
    running = 0
    for i, c in enumerate(h['counts']):
        running += c
        if running >= target:
            return float(h['buckets'][i]) if i < len(h['buckets']) else float('inf')
    return float('inf')


def _fmt(key) -> str:
    name, labels = key
    if not labels:
        return name
    return name + '{' + ','.join(f'{k}={v}' for k, v in labels) + '}'


def counter_total(name: str, **match) -> int:
    with _LOCK:
        return sum(v for (n, labels), v in COUNTERS.items()
                   if n == name and all(dict(labels).get(k) == val for k, val in match.items()))


def histogram_merge(name: str, **match):
    with _LOCK:
        parts = [h for (n, labels), h in HISTOGRAMS.items()
                 if n == name and all(dict(labels).get(k) == v for k, v in match.items())]
        if not parts:
            return None
        merged = {'buckets': parts[0]['buckets'], 'counts': [0] * len(parts[0]['counts']),
                  'sum': 0.0, 'count': 0}
        for h in parts:
            merged['sum'] += h['sum']
            merged['count'] += h['count']
            merged['counts'] = [a + b for a, b in zip(merged['counts'], h['counts'])]
        return merged


def snapshot():
    with _LOCK:
        return {
            'counters': {_fmt(k): v for k, v in COUNTERS.items()},
            'gauges': {_fmt(k): v for k, v in GAUGES.items()},
            'histograms': {
                _fmt(k): {
                    'count': h['count'], 'sum': round(h['sum'], 2),
                    'p50': quantile(h, .5), 'p95': quantile(h, .95), 'p99': quantile(h, .99),
                }
                for k, h in HISTOGRAMS.items()
            },
        }


def _prom_labels(labels, extra=()):
    items = list(labels) + list(extra)
    return '{' + ','.join(f'{k}="{v}"' for k, v in items) + '}' if items else ''


def prometheus_text() -> str:
    lines = []
    with _LOCK:
        for (name, labels), v in sorted(COUNTERS.items()):
            lines.append(f'{name}{_prom_labels(labels)} {v}')
        for (name, labels), v in sorted(GAUGES.items()):
            lines.append(f'{name}{_prom_labels(labels)} {v}')
        for (name, labels), h in sorted(HISTOGRAMS.items()):
            running = 0
            for bound, c in zip(h['buckets'], h['counts']):
                running += c
                lines.append(f'{name}_bucket{_prom_labels(labels, [("le", bound)])} {running}')
            lines.append(f'{name}_bucket{_prom_labels(labels, [("le", "+Inf")])} {h["count"]}')
            lines.append(f'{name}_sum{_prom_labels(labels)} {h["sum"]}')
            lines.append(f'{name}_count{_prom_labels(labels)} {h["count"]}')
    return '\n'.join(lines) + '\n'


def reset():
    with _LOCK:
        COUNTERS.clear()
        GAUGES.clear()
        HISTOGRAMS.clear()
