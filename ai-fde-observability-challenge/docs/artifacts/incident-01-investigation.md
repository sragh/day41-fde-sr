# Incident 01 Investigation, CASE-1042 (Tasks 10 and 11)

## Summary
CASE-1042 had two separate problems with two separate causes.
- It was slow because of a slow identity check and a model retry.
- It was rejected because the risk-2.1 model update raised its score above the reject threshold. The retry did not change the score.

## Claims from the customer and operations
| Claim | Verdict |
|---|---|
| Took much longer than usual | Confirmed. 1,318 ms against about 225 ms for a normal case (5.9×) |
| Rejected after a recent model update | Confirmed. Score 0.77 under risk-2.1 against 0.608 under risk-2.0, which is REVIEW |
| Higher inference consumption | Confirmed. 2,950 tokens against 1,350 (2.2×) |
| Cannot reconstruct from telemetry | Confirmed. See gaps G1, G4, G7 |

## Observed evidence
Source is the unmodified service log (`docs/artifacts/evidence/baseline_run.log`) unless stated.
- E1. Identity span finished in 825 ms under a different trace ID (`96faef1e…`) from the request (`7c12f737…`).
- E2. `risk_model.attempt.1` ran 165 ms and emitted `model.retry` with reason `timeout`.
- E3. `risk_model.attempt.2` ran 321 ms.
- E4. `model.result` reported 2,950 tokens and score 0.77 under `risk-2.1`.
- E5. `business.decision` reported REJECT. The root span lasted 1,314 ms.
- E6. The audit record for CASE-1042 has no `model_retry_count`. Records for other cases would carry it.
- E7. `model_config.json` holds `risk-2.0` and `risk-2.1` with different weights.
- E8. CASE-2048 also had a slow identity span (≈820 ms), no retry, and finished in 991 ms.

## Timeline (offsets from request start, from the repaired trace `96527278…`)
| Offset ms | Event |
|---|---|
| 0 | Request received, `identity.verify` starts |
| 825 | Identity passes |
| 826 | `customer.lookup` completes in 0.8 ms |
| 827 | `risk_model.invoke` starts, attempt 1 starts |
| 992 | Attempt 1 ends with a retry (1,350 tokens spent) and attempt 2 starts |
| 1,316 | Attempt 2 ends (1,600 tokens), score 0.77 |
| 1,317 | Rules return REJECT, audit written |
| 1,318 | Response sent |

## Critical path
Root (1,318 ms) → identity.verify (825 ms, 63%) → model invoke (490 ms, 37%) → attempt 2 (324 ms).

## Where the extra time went
| Component | Normal | CASE-1042 | Excess |
|---|---|---|---|
| Identity | 50 ms | 825 ms | +775 ms (71%) |
| Model | 160 ms | 490 ms | +330 ms (30%) |
| Total | 225 ms | 1,318 ms | +1,093 ms |

The two excess figures add to slightly more than the total excess because normal-case figures are rounded.

## Root cause
| Question | Answer | Basis |
|---|---|---|
| Why slow? | Identity dependency latency first, model retry second | E1, E2, E3, E8 |
| Why retried? | Attempt 1 was marked `timeout` | E2 (see inference I1) |
| Why rejected? | risk-2.1 weights raise the score for this applicant's debt ratio (1.22) | Calculation below |
| Why costly? | A discarded first attempt cost 1,350 tokens on top of 1,600 | E2, E4 |

Calculation for the applicant (amount 1,100,000, income 900,000, country IN, debt ratio 1.2222).
- risk-2.1 gives 0.22 + 1.2222 × 0.45 = 0.770, so REJECT (≥ 0.70).
- risk-2.0 gives 0.18 + 1.2222 × 0.35 = 0.608, so REVIEW.

## Inference, kept apart from evidence
- I1. The "timeout" label cannot be verified. Attempt 1 ended at 165 ms, shorter than any normal timeout, and no timeout threshold is recorded. In the code the retry is hard-wired to this case ID, so it is a simulated fault.
- I2. The identity delay is also hard-wired by case ID. In production the cause would sit inside the identity provider and need that provider's telemetry.
- I3. The update date is unknown. The repo has no deployment record. Only the two config versions are evidence.
- I4. The retry did not alter the score. The same formula runs on whichever attempt succeeds, so a first-attempt success would still have rejected.

## Business impact
| Measure | risk-2.0 | risk-2.1 |
|---|---|---|
| Workload decisions (approve / review / reject) | 9 / 1 / 0 | 7 / 2 / 1 |
| Decisions changed by the update | | 3 of 10 (CASE-1004, CASE-1042, CASE-2004) |
| CASE-1042 outcome | REVIEW | REJECT |
| CASE-1042 cost (assumed $0.01 per 1k tokens) | | $0.0295 against $0.0135 normal |

- Customer impact. A customer who would have gone to manual review received an automatic rejection.
- Portfolio impact. The update moved three of ten cases to a stricter outcome. Two were Singapore cases (the new foreign penalty) and one was a high debt-ratio case (the new debt weight).
- Operations impact. Manual review load rose from 1 to 2 cases in the workload.
- Missing evidence. No ground truth exists, so the telemetry cannot say whether risk-2.1 is more accurate or only stricter.

## Recommended actions
1. Re-run CASE-1042 under risk-2.0 for a human reviewer and decide the customer outcome.
2. Hold the model update behind a decision-mix check before promotion.
3. Add timeout threshold, retry budget and provider telemetry for identity and model calls.
4. Replace hard-coded fault injection with a switch that is logged when active.
