import time

from app.observability import metrics
from app.observability.logging import event
from app.observability.tracing import span
from app import faults


def verify_identity(case_id: str, customer_id: str, trace_id: str | None = None) -> bool:
    # Trace and case come from the request context, so this span joins the request trace.
    with span('identity.verify', trace_id=trace_id, case_id=case_id,
              dependency='identity-provider') as attrs:
        start = time.perf_counter()
        slow = faults.triggered('slow_identity', case_id, faults.SLOW_IDENTITY_CASES)
        attrs['fault_injected'] = slow
        delay = 0.82 if slow else 0.05
        time.sleep(delay)
        elapsed = (time.perf_counter() - start) * 1000
        metrics.observe('dependency_duration_ms', elapsed, dependency='identity-provider')
        attrs['passed'] = True
        event('identity.result', case_id=case_id, customer_id=customer_id, passed=True)
        return True
