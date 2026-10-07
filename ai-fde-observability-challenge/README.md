# AI FDE Observability Challenge — From Black Box to Explainable Production System

## Scenario

DecisionStream is a production-style AI-assisted case approval service used by a regulated financial-services operation. It receives case applications, validates identity, enriches customer data, invokes an AI risk model, applies deterministic decision rules, may trigger retry behaviour, writes audit evidence, and returns `APPROVE`, `REJECT`, or `REVIEW`.

The application is intentionally **operationally under-observable**. It runs and its core business flow is testable, but realistic telemetry, correlation, privacy, SLO, cost, and audit-evidence gaps are embedded for participants to discover and remediate without unnecessarily changing business behaviour.

## Business endpoint

`POST /case-application`

## Stack

- Python 3.11+
- FastAPI
- Pydantic
- CSV reference data + JSONL audit records
- Structured JSON logs (partial by design)
- Lightweight in-process metrics (partial by design)
- OpenTelemetry-style trace/span concepts implemented with lightweight local hooks
- Pytest

## Repository structure

```text
ai-fde-observability-challenge/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── observability/
│   └── services/
├── config/
│   └── model_config.json
├── data/
│   ├── customers.csv
│   └── audit_log.jsonl
├── docs/
│   ├── discovery/
│   └── tasks/
│       └── 00-task-headers.md
├── incidents/
│   └── incident_01.md
├── scripts/
│   └── generate_workload.py
├── dashboards/
├── runbooks/
├── tests/
│   └── test_flow.py
├── requirements.txt
└── README.md
```

## Setup

Create and activate a Python 3.11+ virtual environment, then install dependencies:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /health`
- `POST /case-application`
- `GET /metrics-snapshot`
- `GET /metrics` (Prometheus text), `GET /slo`
- `GET /traces/{trace_id}`, `GET /cases/{case_id}/traces`
- FastAPI docs: `GET /docs`

Evidence scripts: `scripts/collect_evidence.py`, `scripts/build_dashboard.py`, `scripts/validate_recovery.py`. Findings and design documents are indexed in `docs/artifacts/evidence-pack.md`.

## Test

```bash
pytest -q
```

## Generate a repeatable workshop workload

```bash
python scripts/generate_workload.py
```

This generates a mixture of normal and intentionally problematic cases, including `CASE-1042` and `CASE-2048`, so participants can exercise metrics, tracing, correlation and incident investigation after they add or improve observability.

## Challenge starting point

Start with `docs/tasks/00-task-headers.md` and `incidents/incident_01.md`.

Participants should first understand the system and establish an observability baseline before modifying implementation code. The goal is to transform the system from a production black box into an operationally explainable AI service while preserving intended business behaviour.


## Participant task model

The challenge is intentionally prompt-driven, but no prompt sequence or solution prompts are included in the repository. Participants are expected to formulate prompts against these task headers:

1. System & Business Flow Discovery
2. Existing Observability Baseline Assessment
3. Observability Gap & Production Risk Analysis
4. KPI, SLI, SLO & Error-Budget Definition
5. Telemetry, Context & Correlation Design
6. End-to-End Distributed Tracing Implementation
7. Structured Logging, PII & Sensitive-Data Hardening
8. AI / Model Quality, Token, Cost & Retry Instrumentation
9. Unified Production Health View & Operational Dashboard Design
10. Incident Investigation & Event Timeline Reconstruction
11. Root-Cause, Critical-Path & Business-Impact Analysis
12. Observability Remediation & Production Hardening
13. Alerting, Thresholds, Escalation & Runbook Design
14. Auditability, Decision Provenance & Evidence Completeness
15. Production Readiness Gate Assessment
16. Recovery Validation & Final Observability Evidence Pack

### Repository support for the tasks

- **Business flow:** `app/main.py`, `app/services/`
- **Telemetry baseline:** `app/observability/`
- **AI/model behavior:** `app/services/risk_model.py`, `config/model_config.json`
- **Business outcomes:** `app/services/decision.py`
- **Audit evidence:** `app/services/audit.py`, `data/audit_log.jsonl`
- **Incident investigation:** `incidents/incident_01.md`
- **Repeatable workload:** `scripts/generate_workload.py`
- **Dashboard workspace:** `dashboards/`
- **Runbook workspace:** `runbooks/`
- **Participant artifact workspace:** `docs/artifacts/`, `docs/observability/`, `docs/discovery/`
- **Regression validation:** `tests/test_flow.py`

## Workshop integrity

The repository contains **intentional observability deficiencies** as part of the exercise. They are not accidental runtime breakages. Core application execution, validation, incident reproduction, and baseline tests are expected to work before participants begin remediation.
