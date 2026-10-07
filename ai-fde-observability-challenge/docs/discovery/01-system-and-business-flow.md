# System and Business Flow (Task 1)

## Purpose
DecisionStream approves, rejects or refers loan cases to manual review. One endpoint carries the whole business flow.

## Request path
| Step | Component | File | Behaviour |
|---|---|---|---|
| 1 | API | `app/main.py` | `POST /case-application`, validates the body with Pydantic |
| 2 | Identity | `app/services/identity.py` | Always passes. Sleeps 50 ms, or 820 ms for CASE-1042 and CASE-2048 |
| 3 | Customer lookup | `app/services/data_service.py` | Scans `data/customers.csv`. Unknown customer returns 404 |
| 4 | Risk model | `app/services/risk_model.py` | Linear score from `config/model_config.json` (`current`). CASE-1042 gets a simulated timeout and one retry |
| 5 | Decision rules | `app/services/decision.py` | score < 0.45 APPROVE, < 0.70 REVIEW, otherwise REJECT |
| 6 | Audit | `app/services/audit.py` | Appends one JSON line to `data/audit_log.jsonl` |

## Scoring formula
`score = base + (amount / income) × debt_weight + foreign_penalty`, capped at 0.99.
The penalty applies when `country != "IN"`.

## Model configuration
| Parameter | risk-2.0 (previous) | risk-2.1 (current) |
|---|---|---|
| base_score | 0.18 | 0.22 |
| debt_weight | 0.35 | 0.45 |
| foreign_country_penalty | 0.12 | 0.18 |

Only `current` is read at runtime. `previous` exists for reference and rollback.

## Data stores
- `customers.csv` holds 5 customers (segment, tenure, KYC status, region).
- `audit_log.jsonl` is the only persisted decision evidence.

## Simulated faults
The code injects faults by case ID, so they are deterministic.
- Slow identity for CASE-1042 and CASE-2048.
- Model timeout and retry for CASE-1042.

## Downstream systems
None are called. Identity and the model are in-process stand-ins for an identity provider and a model endpoint.

## Business outcomes
Three decisions exist. REVIEW is terminal in this service. No human-review hand-off event exists, so human intervention cannot be traced.
