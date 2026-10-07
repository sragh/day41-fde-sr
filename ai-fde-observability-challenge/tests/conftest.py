import pytest

from app.observability import metrics, tracing
from app.services import audit


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Keep tests from appending to data/audit_log.jsonl and from sharing telemetry."""
    monkeypatch.setattr(audit, "AUDIT", tmp_path / "audit_log.jsonl")
    metrics.reset()
    tracing.reset()
