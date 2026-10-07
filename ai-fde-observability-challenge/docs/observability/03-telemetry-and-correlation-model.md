# Telemetry and Correlation Model (Tasks 5 to 8)

## Identifiers
| ID | Format | Created | Carried by |
|---|---|---|---|
| trace_id | 32 hex, W3C compatible | Request start, or taken from an incoming `traceparent` | Context variable, every log line, every span, audit record, `X-Trace-Id` response header |
| span_id | 16 hex | Each span | Context variable, logs, audit record |
| parent_span_id | 16 hex | Inherited | Span record and log lines |
| case_id | Business key | Request body | Context variable, logs, spans, audit |
| customer_ref | 12 hex SHA-256 prefix of customer_id | At log time | Logs only |
| input_hash | SHA-256 of the full request | At audit time | Audit record |

## How correlation works
- `app/observability/context.py` holds `trace_id`, `span_id` and `case_id` in context variables.
- `span()` reads the context, so no function needs to pass `trace_id` by hand. This closes G1.
- `event()` stamps every log line with timestamp, service, version and the context IDs. This closes G7.
- `GET /traces/{trace_id}` and `GET /cases/{case_id}/traces` return the stored spans.

## Tracing (Task 6)
Span tree for one request.
```
POST /case-application
├─ identity.verify          dependency=identity-provider
├─ customer.lookup          store=customers.csv
├─ risk_model.invoke        model_version, tokens, retry_count, cost_usd
│  ├─ risk_model.attempt.1  tokens, outcome, retry_reason
│  └─ risk_model.attempt.2
├─ decision.rules           rules_version, decision, risk_score
└─ audit.write
```
Test `test_single_trace_covers_whole_request` asserts one root and no orphans.

## Logging and PII (Task 7)
| Field | Treatment |
|---|---|
| income, amount, customer_income, requested_amount | Dropped from logs |
| customer_id | Replaced by `customer_ref` |
| country, requested_product | Kept (low sensitivity, needed for diagnosis) |

`redact()` runs inside `event()`, so new log calls inherit the protection. Raw income and amount stay out of the audit log too. The audit log stores `input_hash` instead.

## AI telemetry (Task 8)
| Metric | Labels | Purpose |
|---|---|---|
| `model_calls` | model_version | Attempts, including retries |
| `model_tokens_total` | model_version | Consumption |
| `model_wasted_tokens_total` | model_version | Tokens spent on attempts that were discarded |
| `model_cost_usd_total` | model_version | Spend (assumed $0.01 per 1k tokens, edit `config/model_config.json`) |
| `model_retries_total` | model_version, reason | Retry behaviour |
| `model_attempt_duration_ms`, `model_invoke_duration_ms` | model_version | Latency distribution |
| `risk_score` histogram | model_version | Drift in score distribution |
| `decisions_total` | decision, model_version | Decision mix by model version |

A `service.start` event records the model version, previous version and config hash, which closes G9.

## Fault injection
`app/faults.py` gates the seeded faults. `DECISIONSTREAM_FAULTS=off` disables them. When a fault fires it logs `fault.injected`, increments `faults_injected_total{fault}` and sets `fault_injected` on the span.

## Metrics format
`GET /metrics` serves Prometheus text format. `GET /metrics-snapshot` keeps its original `counters` and `gauges` keys and adds `histograms` with P50, P95 and P99.
