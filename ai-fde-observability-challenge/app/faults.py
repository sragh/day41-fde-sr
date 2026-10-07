"""Workshop fault injection, switchable and always visible in telemetry.

Set DECISIONSTREAM_FAULTS=off to disable. Default is on so the seeded
incident (CASE-1042, CASE-2048) reproduces.
"""
import os

from app.observability import metrics
from app.observability.logging import event

SLOW_IDENTITY_CASES = {"CASE-1042", "CASE-2048"}
MODEL_TIMEOUT_CASES = {"CASE-1042"}


def enabled() -> bool:
    return os.getenv("DECISIONSTREAM_FAULTS", "on").lower() != "off"


def triggered(fault: str, case_id: str, cases: set) -> bool:
    """True when the fault applies. Records a log event and a counter when it does."""
    if not enabled() or case_id not in cases:
        return False
    metrics.inc("faults_injected_total", fault=fault)
    event("fault.injected", fault=fault)
    return True
