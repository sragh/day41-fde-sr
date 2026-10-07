# Decision Provenance, Audit Evidence and Readiness Gate (Tasks 14 and 15)

## Provenance chain for one decision
| Question | Where the answer lives |
|---|---|
| What was asked? | `input_hash` (SHA-256 of the full request) in the audit record |
| Who or what handled it? | `trace_id` and `span_id` link the audit record to the stored trace |
| Which model and settings? | `model_version`, `config_hash`, `service_version` |
| What did the model do? | `model_retry_count`, `retry_reason`, `tokens`, `cost_usd`, per-attempt spans |
| What did it score? | `risk_score` |
| Which rules decided? | `rules_version` plus thresholds in `decision.py` |
| What was the outcome? | `decision`, `reason`, `ts` |
| Did a human intervene? | Not recorded (see residual gaps) |

## Audit schema change
- Schema version 3 adds 14 fields to the original 5, including `prev_hash` and `record_hash`. Old records keep their shape.
- Each record hashes its body together with the previous record's hash. Editing or deleting a record breaks every later link.
- `python scripts/verify_audit.py` checks the chain and exits 1 on tampering. Legacy records before the chain are counted but cannot be verified.
- The exclusion that dropped retry evidence for CASE-1042 is removed.
- Raw income, amount and customer ID are absent. `input_hash` proves the input without storing it.
- `audit_records_total` and `audit_write_failures_total` make completeness measurable.

## Evidence completeness
| Check | Result |
|---|---|
| Every decision writes an audit record | Yes, `audit_completeness` SLO 100% in validation |
| Audit record joins to a trace | Yes, `test_audit_persists_retry_evidence_for_incident_case` |
| No raw PII in audit | Yes, `test_audit_holds_no_raw_pii` |
| Historical CASE-1042 records have retry evidence | No. Two pre-fix records for CASE-1042 stay incomplete |

## Production readiness gate
| Capability | Status | Evidence |
|---|---|---|
| Detect failures | Pass in code, not yet wired | SLO endpoint and alert rules exist, no alert delivery is deployed |
| Trace a transaction | Pass | One trace per request, orphan-free test |
| Measure AI quality | Partial | Score distribution and decision mix exist, no ground-truth accuracy |
| Measure cost | Pass with assumption | Price is a placeholder |
| Protect sensitive data | Pass | Redaction tests |
| Prove controls operated | Pass with limit | Audit is hash-chained and verifiable. Truncating the file's tail is undetectable without an external anchor |
| Recover safely | Partial | Rollback by config edit is documented, not automated |

## Verdict
Conditional go for a pilot. Production go needs the blockers below.

## Blockers
1. Export traces, metrics and logs to a durable backend. Today they live in process memory and reset on restart.
2. Anchor the audit chain tail outside the file (write-once store or periodic signed checkpoint), so tail truncation is detectable.
3. Replace the placeholder token price with the contracted rate.
4. Record the human decision for REVIEW cases.
5. Run more than one worker only after metrics move to a shared backend. Per-process counters would split.

Closed since the first assessment: fault injection is a logged flag (`DECISIONSTREAM_FAULTS`), 422 failures are metered, and the audit log is hash-chained.
