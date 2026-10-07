import json

from fastapi.testclient import TestClient

from app.main import app
from app.observability.logging import redact
from app.services import audit

client = TestClient(app)


def incident():
    return {"case_id": "CASE-1042", "customer_id": "C001", "amount": 1100000,
            "country": "IN", "income": 900000, "requested_product": "PERSONAL_LOAN"}


def normal():
    return {**incident(), "case_id": "CASE-1001", "amount": 150000}


def audit_records():
    return [json.loads(line) for line in audit.AUDIT.read_text().splitlines()]


def test_business_behaviour_unchanged():
    body = client.post("/case-application", json=incident()).json()
    assert (body["decision"], body["risk_score"], body["model_version"]) == ("REJECT", 0.77, "risk-2.1")


def test_single_trace_covers_whole_request():
    r = client.post("/case-application", json=incident())
    trace = client.get(f"/traces/{r.headers['X-Trace-Id']}").json()
    names = {s["name"] for s in trace["spans"]}
    assert {"POST /case-application", "identity.verify", "customer.lookup", "risk_model.invoke",
            "risk_model.attempt.1", "risk_model.attempt.2", "decision.rules", "audit.write"} <= names
    ids = {s["span_id"] for s in trace["spans"]}
    roots = [s for s in trace["spans"] if s["parent_span_id"] is None]
    assert len(roots) == 1
    assert all(s["parent_span_id"] in ids for s in trace["spans"] if s["parent_span_id"])


def test_incoming_traceparent_is_honoured():
    tid = "a" * 32
    r = client.post("/case-application", json=normal(),
                    headers={"traceparent": f"00-{tid}-{'b' * 16}-01"})
    assert r.headers["X-Trace-Id"] == tid


def test_audit_persists_retry_evidence_for_incident_case():
    r = client.post("/case-application", json=incident())
    rec = audit_records()[-1]
    assert rec["model_retry_count"] == 1
    assert rec["trace_id"] == r.headers["X-Trace-Id"]
    assert rec["tokens"] == 2950 and rec["retry_reason"] == "timeout"
    assert rec["input_hash"] and rec["rules_version"] and rec["config_hash"]


def test_audit_holds_no_raw_pii():
    client.post("/case-application", json=incident())
    raw = audit.AUDIT.read_text()
    assert "1100000" not in raw and "900000" not in raw and "C001" not in raw


def test_redaction_drops_financials_and_pseudonymises_customer():
    out = redact({"income": 1, "amount": 2, "customer_id": "C001", "case_id": "X"})
    assert "income" not in out and "amount" not in out and "customer_id" not in out
    assert out["customer_ref"] != "C001" and out["case_id"] == "X"


def test_logs_are_correlated_and_redacted(caplog):
    caplog.set_level("INFO", logger="decisionstream")
    client.post("/case-application", json=incident())
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "decisionstream"]
    assert lines and all(l.get("trace_id") and l.get("case_id") for l in lines)
    assert not any("income" in l or "customer_income" in l or "requested_amount" in l for l in lines)


def test_metrics_capture_tokens_cost_retries_and_latency_histogram():
    client.post("/case-application", json=incident())
    client.post("/case-application", json=normal())
    snap = client.get("/metrics-snapshot").json()
    assert snap["counters"]["model_tokens_total{model_version=risk-2.1}"] == 2950 + 1350
    assert snap["counters"]["model_retries_total{model_version=risk-2.1,reason=timeout}"] == 1
    assert snap["counters"]["model_wasted_tokens_total{model_version=risk-2.1}"] == 1350
    hist = [v for k, v in snap["histograms"].items() if k.startswith("http_request_duration_ms")]
    assert sum(h["count"] for h in hist) == 2 and all(h["p95"] for h in hist)
    assert "http_request_duration_ms_bucket" in client.get("/metrics").text


def test_error_paths_are_counted():
    bad = {**normal(), "customer_id": "UNKNOWN"}
    assert client.post("/case-application", json=bad).status_code == 404
    snap = client.get("/metrics-snapshot").json()
    assert snap["counters"]["case_errors{reason=customer_not_found}"] == 1
    assert snap["counters"]["http_requests_total{route=/case-application,status=404}"] == 1


def test_slo_endpoint_flags_latency_breach_on_incident_case():
    client.post("/case-application", json=incident())
    status = client.get("/slo").json()
    assert status["latency_p95_ms"]["status"] == "BREACHED"
    assert status["model_retry_rate"]["status"] == "BREACHED"
    assert status["audit_completeness"]["status"] == "MET"


def test_validation_failures_are_metered():
    bad = {**normal(), "amount": 0}
    assert client.post("/case-application", json=bad).status_code == 422
    snap = client.get("/metrics-snapshot").json()["counters"]
    assert snap["http_requests_total{route=/case-application,status=422}"] == 1
    assert snap["case_errors{reason=validation_failed}"] == 1


def test_fault_injection_is_visible_when_on(caplog):
    caplog.set_level("INFO", logger="decisionstream")
    client.post("/case-application", json=incident())
    snap = client.get("/metrics-snapshot").json()["counters"]
    assert snap["faults_injected_total{fault=slow_identity}"] == 1
    assert snap["faults_injected_total{fault=model_timeout}"] == 1
    assert any('"fault.injected"' in r.getMessage() for r in caplog.records)


def test_fault_injection_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("DECISIONSTREAM_FAULTS", "off")
    body = client.post("/case-application", json=incident()).json()
    assert body["decision"] == "REJECT"
    assert audit_records()[-1]["model_retry_count"] == 0
    assert not any(k.startswith("faults_injected") for k in
                   client.get("/metrics-snapshot").json()["counters"])


def test_audit_chain_verifies_and_detects_tampering():
    for _ in range(3):
        client.post("/case-application", json=normal())
    assert audit.verify_chain()["valid"] and audit.verify_chain()["chained"] == 3
    lines = audit.AUDIT.read_text().splitlines()
    lines[1] = lines[1].replace('"APPROVE"', '"REJECT"')
    audit.AUDIT.write_text("\n".join(lines) + "\n")
    result = audit.verify_chain()
    assert result["valid"] is False and result["first_bad_line"] == 2


def test_audit_chain_continues_after_legacy_records():
    audit.AUDIT.write_text('{"case_id": "OLD", "decision": "APPROVE"}\n')
    client.post("/case-application", json=normal())
    assert audit.verify_chain() == {"valid": True, "chained": 1, "legacy": 1}
