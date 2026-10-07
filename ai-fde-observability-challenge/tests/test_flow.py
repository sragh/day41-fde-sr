from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(case_id="CASE-1001"):
    return {
        "case_id": case_id,
        "customer_id": "C001",
        "amount": 150000,
        "country": "IN",
        "income": 900000,
        "requested_product": "PERSONAL_LOAN",
    }


def incident_payload():
    return {
        "case_id": "CASE-1042",
        "customer_id": "C001",
        "amount": 1100000,
        "country": "IN",
        "income": 900000,
        "requested_product": "PERSONAL_LOAN",
    }


def test_health_endpoint_available():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_case_flow_runs():
    response = client.post("/case-application", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "CASE-1001"
    assert body["decision"] in {"APPROVE", "REJECT", "REVIEW"}
    assert body["model_version"] == "risk-2.1"


def test_incident_case_reproduces_rejection():
    response = client.post("/case-application", json=incident_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "CASE-1042"
    assert body["decision"] == "REJECT"
    assert body["model_version"] == "risk-2.1"


def test_missing_customer_returns_404():
    body = payload("CASE-4040")
    body["customer_id"] = "UNKNOWN"
    response = client.post("/case-application", json=body)
    assert response.status_code == 404


def test_input_validation_rejects_non_positive_amount():
    body = payload()
    body["amount"] = 0
    response = client.post("/case-application", json=body)
    assert response.status_code == 422


def test_metrics_snapshot_is_available():
    response = client.get("/metrics-snapshot")
    assert response.status_code == 200
    body = response.json()
    assert "counters" in body
    assert "gauges" in body
