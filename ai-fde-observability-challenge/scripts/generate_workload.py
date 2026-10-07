"""Generate a repeatable mixed workload for the observability challenge.

This is deliberately simple and runs in-process through FastAPI TestClient so
participants can create enough transactions to inspect logs, metrics and traces
without needing an external load generator.
"""
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

client = TestClient(app)

CASES = [
    ("CASE-1001", "C001", 150000, 900000, "IN"),
    ("CASE-1002", "C002", 225000, 700000, "IN"),
    ("CASE-1003", "C003", 450000, 1200000, "IN"),
    ("CASE-1004", "C004", 300000, 850000, "SG"),
    ("CASE-1005", "C005", 650000, 1500000, "IN"),
    ("CASE-1042", "C001", 1100000, 900000, "IN"),
    ("CASE-2001", "C002", 180000, 700000, "IN"),
    ("CASE-2002", "C003", 500000, 1200000, "IN"),
    ("CASE-2048", "C005", 700000, 1500000, "IN"),
    ("CASE-2004", "C004", 350000, 850000, "SG"),
]


def payload(case_id, customer_id, amount, income, country):
    return {
        "case_id": case_id,
        "customer_id": customer_id,
        "amount": amount,
        "country": country,
        "income": income,
        "requested_product": "PERSONAL_LOAN",
    }


def main():
    results = []
    for row in CASES:
        response = client.post("/case-application", json=payload(*row))
        body = response.json()
        results.append({
            "case_id": row[0],
            "status_code": response.status_code,
            "decision": body.get("decision"),
            "model_version": body.get("model_version"),
        })

    print("Generated workload:")
    for item in results:
        print(item)
    print("\nMetrics snapshot:")
    print(client.get("/metrics-snapshot").json())


if __name__ == "__main__":
    main()
