"""SLO definitions and evaluation against in-process metrics."""
from . import metrics

# See docs/observability/02-sli-slo-error-budget.md for rationale.
SLOS = {
    'availability': {'objective': 0.995, 'desc': 'non-5xx responses / all responses'},
    'latency_p95_ms': {'objective': 500, 'desc': 'request latency P95 upper bound'},
    'model_retry_rate': {'objective': 0.02, 'desc': 'cases needing a model retry / cases'},
    'audit_completeness': {'objective': 1.0, 'desc': 'audited decisions / decisions'},
}


def evaluate() -> dict:
    total = metrics.counter_total('http_requests_total')
    errors_5xx = sum(
        v for (n, labels), v in metrics.COUNTERS.items()
        if n == 'http_requests_total' and dict(labels).get('status', '0').startswith('5')
    )
    hist = metrics.histogram_merge('http_request_duration_ms', route='/case-application')
    p95 = metrics.quantile(hist, .95) if hist else None
    cases = metrics.counter_total('decisions_total')
    retries = metrics.counter_total('model_retries_total')
    retried_cases = metrics.counter_total('cases_with_retry_total')
    audited = metrics.counter_total('audit_records_total')

    availability = 1 - errors_5xx / total if total else None
    retry_rate = retried_cases / cases if cases else None
    audit_ratio = audited / cases if cases else None

    def verdict(value, objective, higher_is_better):
        if value is None:
            return 'NO_DATA'
        ok = value >= objective if higher_is_better else value <= objective
        return 'MET' if ok else 'BREACHED'

    budget = None
    if total:
        allowed = (1 - SLOS['availability']['objective']) * total
        budget = round(1 - (errors_5xx / allowed), 3) if allowed else None

    return {
        'availability': {'value': availability, 'objective': SLOS['availability']['objective'],
                         'status': verdict(availability, SLOS['availability']['objective'], True),
                         'error_budget_remaining': budget},
        'latency_p95_ms': {'value': p95, 'objective': SLOS['latency_p95_ms']['objective'],
                           'status': verdict(p95, SLOS['latency_p95_ms']['objective'], False)},
        'model_retry_rate': {'value': retry_rate, 'objective': SLOS['model_retry_rate']['objective'],
                             'status': verdict(retry_rate, SLOS['model_retry_rate']['objective'], False),
                             'retries_total': retries},
        'audit_completeness': {'value': audit_ratio, 'objective': 1.0,
                               'status': verdict(audit_ratio, 1.0, True)},
    }
