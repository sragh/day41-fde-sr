"""Run the workload against an isolated audit file and write an evidence bundle.

Outputs (docs/artifacts/evidence/):
  workload_logs.jsonl   all structured logs from the run
  evidence.json         per-case results, CASE-1042 trace and critical path,
                        metrics, SLO status, audit records, model-update impact
"""
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.observability import metrics, tracing  # noqa: E402
from app.services import audit, decision  # noqa: E402
from scripts.generate_workload import CASES, payload  # noqa: E402

OUT = ROOT / "docs" / "artifacts" / "evidence"


def critical_path(spans):
    """Longest-duration chain from the root, following the slowest child."""
    kids = {}
    for s in spans:
        kids.setdefault(s["parent_span_id"], []).append(s)
    node, path = kids[None][0], []
    while node:
        path.append({"span": node["name"], "duration_ms": node["duration_ms"]})
        children = kids.get(node["span_id"], [])
        node = max(children, key=lambda c: c["duration_ms"]) if children else None
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audit.AUDIT = Path(tempfile.mkdtemp()) / "audit_log.jsonl"
    metrics.reset()
    tracing.reset()

    log_file = logging.FileHandler(OUT / "workload_logs.jsonl", mode="w")
    log_file.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("decisionstream").addHandler(log_file)

    client = TestClient(app)
    cfg = json.loads((ROOT / "config" / "model_config.json").read_text())
    results = []
    for row in CASES:
        t = time.perf_counter()
        r = client.post("/case-application", json=payload(*row))
        body = r.json()
        prev = cfg["previous"]
        amount, income, country = row[2], row[3], row[4]
        prev_score = min(0.99, prev["base_score"] + amount / income * prev["debt_weight"]
                         + (prev["foreign_country_penalty"] if country != "IN" else 0))
        prev_decision = (
            "APPROVE" if prev_score < decision.APPROVE_BELOW
            else "REVIEW" if prev_score < decision.REVIEW_BELOW else "REJECT")
        results.append({
            "case_id": row[0], "status": r.status_code,
            "latency_ms": round((time.perf_counter() - t) * 1000),
            "trace_id": r.headers["X-Trace-Id"],
            "decision": body["decision"], "risk_score": round(body["risk_score"], 3),
            "decision_under_risk_2_0": prev_decision,
            "score_under_risk_2_0": round(prev_score, 3),
            "flipped_by_model_update": prev_decision != body["decision"],
        })

    incident = next(x for x in results if x["case_id"] == "CASE-1042")
    spans = tracing.get_trace(incident["trace_id"])
    evidence = {
        "results": results,
        "incident_trace": {"trace_id": incident["trace_id"], "span_count": len(spans),
                           "critical_path": critical_path(spans), "spans": spans},
        "metrics": metrics.snapshot(),
        "slo": client.get("/slo").json(),
        "audit_records": [json.loads(x) for x in audit.AUDIT.read_text().splitlines()],
    }
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
    for r in results:
        print(r)
    print(json.dumps(evidence["slo"], indent=2))


if __name__ == "__main__":
    main()
