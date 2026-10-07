# Observability Baseline and Gap Register (Tasks 2 and 3)

Baseline was captured by running the unmodified repo with the 10-case workload (`baseline_run.log`).

## Baseline inventory
| Signal | What existed | What was missing |
|---|---|---|
| Logs | JSON lines through `event()` | Timestamp, service name, severity, automatic trace or case context |
| Traces | `span.start` and `span.end` log lines | Parent IDs, stored traces, attributes, any query path |
| Metrics | 5 counters and 2 last-value gauges | Labels, histograms, percentiles, windows, export format |
| AI telemetry | One `model.result` log line | Per-attempt tokens, cost, retry metric, model-latency distribution |
| Business events | `business.decision` log line | Rule version, thresholds, link to the audit record |
| Audit | 5 fields per decision | Retry count (dropped for CASE-1042), score, tokens, inputs, rule version, span link |

## Measured baseline (10 cases)
- Counters: `case_requests` 10, `model_calls` 11, approve 7, review 2, reject 1.
- Gauges: `last_case_latency_ms` 220.7, `last_case_tokens` 1350. Both belong to the last request and say nothing about CASE-1042.
- Trace IDs seen for CASE-1042 in the logs: two (`7c12f737…` and `96faef1e…`).

## Gap register
| ID | Gap | Evidence | Risk | Severity |
|---|---|---|---|---|
| G1 | Identity span not on the request trace | `identity.py` called `span()` without `trace_id`; CASE-1042 produced two trace IDs | The slowest hop is invisible from the request trace | High |
| G2 | No latency distribution | Only `last_case_latency_ms` | P95 and SLO burn cannot be computed | High |
| G3 | PII and financials in logs | `model.result` logged `customer_income` and `requested_amount`; `case.received` logged `customer_id` | Privacy and regulatory exposure | High |
| G4 | Retry evidence missing from audit | `audit.py` skips `model_retry_count` when `case_id == "CASE-1042"` | Cannot prove what the model did for the disputed case | High |
| G5 | Audit lacks decision provenance | 5 fields only | Decision cannot be reconstructed or defended | High |
| G6 | Tokens and cost not aggregated | Gauge holds the last request only | Inference spend cannot be explained or capped | Medium |
| G7 | `model.retry` log has no trace or span ID | Event emitted without correlation | Retry cannot be tied to a request | Medium |
| G8 | Counters have no labels | No model version, decision or status dimension | Model-update impact cannot be sliced | Medium |
| G9 | No model-change signal | No event or hash for the active config | A "recent update" cannot be dated or proven | Medium |
| G10 | Error paths barely measured | 400 and 404 raise before any latency record | Error rate and error budget cannot be computed | Medium |
| G11 | No alerts, runbook or dashboard | Empty folders | Nobody is told when the service degrades | Medium |
| G12 | Model-quality drift not observable | No score distribution | A threshold-crossing model update goes unseen | Medium |

## Production risks if left as is
- A customer dispute like CASE-1042 cannot be answered from telemetry.
- A model update can shift decisions with no alarm.
- Inference cost cannot be attributed.
- Personal and financial data sits in plain-text logs.
