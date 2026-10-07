"""Replay incident and healthy scenarios and check the observability controls.

Writes docs/artifacts/evidence/recovery.json and exits non-zero on any failed check.
"""
import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.observability import metrics, tracing  # noqa: E402
from app.services import audit  # noqa: E402
from scripts.generate_workload import CASES, payload  # noqa: E402

client = TestClient(app)
checks = []


def check(name, ok, detail=""):
    checks.append({"check": name, "pass": bool(ok), "detail": detail})


def fresh():
    metrics.reset()
    tracing.reset()
    audit.AUDIT = Path(tempfile.mkdtemp()) / "audit_log.jsonl"


# Scenario A: incident replay
fresh()
row = next(r for r in CASES if r[0] == "CASE-1042")
r = client.post("/case-application", json=payload(*row))
tid = r.headers["X-Trace-Id"]
spans = tracing.get_trace(tid)
rec = json.loads(audit.AUDIT.read_text().splitlines()[-1])
slo = client.get("/slo").json()
snap = client.get("/metrics-snapshot").json()["counters"]
check("A1 business outcome unchanged (REJECT, risk-2.1)", r.json()["decision"] == "REJECT" and r.json()["model_version"] == "risk-2.1")
check("A2 one trace holds all spans incl. identity", {"identity.verify", "risk_model.attempt.2", "audit.write"} <= {s["name"] for s in spans})
check("A3 no orphan spans", len([s for s in spans if s["parent_span_id"] is None]) == 1)
check("A4 audit has retry count, tokens, trace link", rec["model_retry_count"] == 1 and rec["tokens"] == 2950 and rec["trace_id"] == tid)
check("A5 token and wasted-token metrics recorded", snap["model_tokens_total{model_version=risk-2.1}"] == 2950 and snap["model_wasted_tokens_total{model_version=risk-2.1}"] == 1350)
check("A6 latency SLO breach detected", slo["latency_p95_ms"]["status"] == "BREACHED")
check("A7 retry-rate SLO breach detected", slo["model_retry_rate"]["status"] == "BREACHED")
check("A8 injected faults are visible in metrics", snap.get("faults_injected_total{fault=slow_identity}") == 1 and snap.get("faults_injected_total{fault=model_timeout}") == 1)
check("A9 audit hash chain verifies", audit.verify_chain()["valid"])
bad = client.post("/case-application", json={**payload(*row), "amount": 0})
check("A10 validation failure metered (422)", bad.status_code == 422 and client.get("/metrics-snapshot").json()["counters"].get("case_errors{reason=validation_failed}") == 1)

# Scenario B: healthy traffic
fresh()
for row in CASES:
    if row[0] not in {"CASE-1042", "CASE-2048"}:
        client.post("/case-application", json=payload(*row))
slo = client.get("/slo").json()
check("B1 availability SLO met", slo["availability"]["status"] == "MET")
check("B2 latency SLO met", slo["latency_p95_ms"]["status"] == "MET", str(slo["latency_p95_ms"]["value"]))
check("B3 retry-rate SLO met", slo["model_retry_rate"]["status"] == "MET")
check("B4 audit completeness met", slo["audit_completeness"]["status"] == "MET")

out = ROOT / "docs/artifacts/evidence/recovery.json"
out.write_text(json.dumps(checks, indent=2))
for c in checks:
    print("PASS" if c["pass"] else "FAIL", c["check"], c["detail"])
sys.exit(0 if all(c["pass"] for c in checks) else 1)
