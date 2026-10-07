# KPIs, SLIs, SLOs and Error Budgets (Task 4)

## Business KPIs
| KPI | Definition | Why it matters |
|---|---|---|
| Decision mix | Share of APPROVE, REVIEW, REJECT by model version | A shift after a model change is the earliest sign of drift |
| Manual-review load | REVIEW count per day | Drives operations headcount |
| Cost per decision | Model tokens × price / decisions | Controls inference spend |
| Time to decision | Request latency | Customer experience |

## SLIs and SLOs
Window is a rolling 28 days unless stated. The service evaluates cumulative values since process start through `GET /slo`.

| SLI | Measurement | SLO | Source metric |
|---|---|---|---|
| Availability | 1 − (5xx responses / all responses) | 99.5% | `http_requests_total{status}` |
| Latency | P95 of `/case-application` duration | ≤ 500 ms | `http_request_duration_ms` |
| Model retry rate | Cases with a retry / cases decided | ≤ 2% | `cases_with_retry_total`, `decisions_total` |
| Audit completeness | Audit records / decisions | 100% | `audit_records_total` |
| Model latency | P95 of `risk_model.invoke` | ≤ 400 ms | `model_invoke_duration_ms` |
| Identity latency | P95 of identity dependency | ≤ 150 ms | `dependency_duration_ms` |

## Why these targets
- A normal case takes about 225 ms, so 500 ms leaves room for load and still catches the 1.3 s incident pattern.
- A 2% retry budget tolerates rare timeouts and flags a degrading model endpoint early.
- Audit completeness has no budget because a missing record is a compliance failure.

## Error budget
Availability 99.5% over 28 days allows 0.5% failed requests.
- At 100,000 requests per 28 days the budget is 500 failed requests.
- Burn rate 1 spends the budget exactly over the window.
- A burn rate of 14.4 for 1 hour (2% of the budget) pages. A burn rate of 6 for 6 hours opens a ticket.
- `/slo` reports `error_budget_remaining` as 1 − (5xx / allowed).

## Latency budget decomposition (normal case)
| Hop | Budget |
|---|---|
| Identity | 50 ms observed, 150 ms ceiling |
| Customer lookup | under 5 ms |
| Model | 160 ms observed, 400 ms ceiling |
| Rules and audit | under 5 ms |

## Limits of the implementation
- Percentiles come from fixed buckets, so they report the upper bucket bound (500 ms objective aligns with a bucket edge).
- Windows are cumulative since start. A production exporter needs rolling windows.
