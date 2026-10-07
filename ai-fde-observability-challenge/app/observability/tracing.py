import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone

from . import context
from .logging import event

MAX_TRACES = 500

_TRACES: "OrderedDict[str, list]" = OrderedDict()
_LOCK = threading.Lock()


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def _store(trace_id: str, record: dict):
    with _LOCK:
        _TRACES.setdefault(trace_id, []).append(record)
        _TRACES.move_to_end(trace_id)
        while len(_TRACES) > MAX_TRACES:
            _TRACES.popitem(last=False)


def get_trace(trace_id: str):
    with _LOCK:
        spans = list(_TRACES.get(trace_id, []))
    return sorted(spans, key=lambda s: s['start_ts']) if spans else None


def find_traces_by_case(case_id: str) -> list[str]:
    with _LOCK:
        return [t for t, spans in _TRACES.items()
                if any(s.get('case_id') == case_id for s in spans)]


def reset():
    with _LOCK:
        _TRACES.clear()


@contextmanager
def span(name: str, trace_id: str | None = None, case_id: str | None = None, **attributes):
    """Open a span. Trace, parent and case are inherited from context.

    Yields a mutable attributes dict; values set on it are recorded on span end.
    """
    tid = trace_id or context.trace_id_var.get() or new_trace_id()
    cid = case_id or context.case_id_var.get()
    parent = context.span_id_var.get()
    sid = new_span_id()

    tokens = (
        context.trace_id_var.set(tid),
        context.span_id_var.set(sid),
        context.case_id_var.set(cid),
    )
    attrs = dict(attributes)
    start_ts = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    status = 'OK'
    event('span.start', span=name, parent_span_id=parent)
    try:
        yield attrs
    except Exception as exc:
        status = 'ERROR'
        attrs['error.type'] = type(exc).__name__
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        record = {
            'trace_id': tid, 'span_id': sid, 'parent_span_id': parent,
            'name': name, 'case_id': cid, 'service': context.SERVICE_NAME,
            'start_ts': start_ts, 'duration_ms': duration_ms,
            'status': status, 'attributes': attrs,
        }
        _store(tid, record)
        event('span.end', span=name, parent_span_id=parent,
              status=status, duration_ms=duration_ms, **attrs)
        context.trace_id_var.reset(tokens[0])
        context.span_id_var.reset(tokens[1])
        context.case_id_var.reset(tokens[2])
