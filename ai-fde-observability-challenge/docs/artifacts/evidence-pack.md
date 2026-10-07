# Recovery Validation and Final Evidence Pack (Task 16)

## What was re-run
`python scripts/validate_recovery.py` replays CASE-1042 and a healthy workload. Result is 14 of 14 checks passing (`evidence/recovery.json`). `pytest -q` passes 21 tests (6 original, 15 new). `python scripts/verify_audit.py` verifies the audit chain.

## Before and after
| Question | Before | After |
|---|---|---|
| Trace IDs for CASE-1042 | 2 | 1, with 8 connected spans |
| Identity span on the request trace | No | Yes |
| Logs carry trace, span, case, timestamp | No | Yes |
| Income and amount in logs | Yes | No |
| Latency percentiles | None | P50, P95, P99 from histograms |
| Tokens and cost over time | Last request only | Counters by model version |
| Retry visible in metrics | No | `model_retries_total{reason}` |
| Retry in audit for CASE-1042 | No | Yes |
| Audit fields per decision | 5 | 19 (including hash chain) |
| Audit tamper evidence | None | Hash chain, `scripts/verify_audit.py` |
| Fault injection | Silent, hard-coded | Switchable, logged, counted (`faults_injected_total`) |
| Validation failures (422) | Unmetered | `case_errors{reason=validation_failed}` |
| SLO status | Not computable | `/slo` |
| Alerts, runbook, dashboard | None | Provided |
| Model change visible | No | `service.start` event, `config_hash` in audit |

## SLO recovery
| Scenario | Availability | Latency P95 | Retry rate | Audit completeness |
|---|---|---|---|---|
| Incident replay | MET | BREACHED | BREACHED | MET |
| Healthy workload (8 cases) | MET | MET (250 ms bucket) | MET | MET |

The breach is detected for the incident and clears on healthy traffic. The simulated faults for CASE-1042 and CASE-2048 are still in the code, so the incident case stays slow. Remediation here covers observability, not the fault.

## Business behaviour preserved
`test_business_behaviour_unchanged` and the original six tests confirm CASE-1042 still returns REJECT, score 0.77, `risk-2.1`.

## Artifact index
| Task | File |
|---|---|
| 1 | `docs/discovery/01-system-and-business-flow.md` |
| 2, 3 | `docs/observability/00-baseline-and-gaps.md` |
| 4 | `docs/observability/02-sli-slo-error-budget.md` |
| 5 to 8 | `docs/observability/03-telemetry-and-correlation-model.md`, `app/observability/`, `app/services/` |
| 9 | `dashboards/README.md`, `dashboards/production_health.html` |
| 10, 11 | `docs/artifacts/incident-01-investigation.md` |
| 12 | Code changes listed below |
| 13 | `runbooks/README.md`, `runbooks/alert_rules.yml` |
| 14, 15 | `docs/artifacts/provenance-and-readiness.md` |
| 16 | This file, `docs/artifacts/evidence/` |

## Code changes (Task 12)
| File | Change |
|---|---|
| `app/observability/context.py` | New. Request context variables |
| `app/observability/logging.py` | Auto context, timestamp, redaction |
| `app/observability/tracing.py` | Parent IDs, attributes, trace store |
| `app/observability/metrics.py` | Labels, histograms, Prometheus text |
| `app/observability/slo.py` | New. SLO evaluation |
| `app/services/identity.py` | Joins request trace, records dependency latency |
| `app/services/risk_model.py` | Token, cost, retry, latency, score metrics |
| `app/services/decision.py` | Rule version and thresholds as constants |
| `app/services/audit.py` | Provenance fields, retry evidence always written, hash chain, `verify_chain()` |
| `app/faults.py` | New. Switchable fault injection with log and metric |
| `app/main.py` | Context setup, `X-Trace-Id`, traceparent, error and latency metrics, 422 handler, new endpoints |
| `config/model_config.json` | Added `pricing` block |
| `tests/` | `conftest.py` isolates state, `test_observability.py` adds 15 tests |

## Residual risk
See blockers in `provenance-and-readiness.md`.
