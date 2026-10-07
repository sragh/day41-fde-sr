# Alerting, Escalation and Runbooks (Task 13)

Alert rules live in `alert_rules.yml`. Severity `page` wakes the owner, severity `ticket` opens work for the next business day.

## Severity and ownership
| Severity | Meaning | Response | Escalates to |
|---|---|---|---|
| Page | Customers harmed now, or compliance evidence at risk | 15 min acknowledge | Engineering manager after 30 min |
| Ticket | Degradation with budget left | Next business day | Owner team lead after 3 days |

## Thresholds
| Alert | Threshold | Severity | Owner |
|---|---|---|---|
| Error budget burn | 5xx > 7.2% for 5 min (burn 14.4) | Page | platform-oncall |
| Latency P95 | > 500 ms for 10 min | Page | platform-oncall |
| Model retry rate | > 2% for 15 min | Ticket | ml-oncall |
| Wasted token share | > 5% for 30 min | Ticket | ml-oncall |
| Decision mix shift | Reject share moves > 10 points vs same hour yesterday | Page | ml-oncall |
| Audit write failure | Any in 5 min | Page | compliance-oncall |
| Identity P95 | > 150 ms for 10 min | Ticket | platform-oncall |

## First five minutes for any page
1. Open the production health view and note which SLO is red.
2. Pick a recent affected case. Call `GET /cases/{case_id}/traces`, then `GET /traces/{trace_id}`.
3. Read the slowest span on the critical path.
4. Check `service.start` in logs for the model version and config hash.
5. Post the trace ID in the incident channel.

## A1 Error budget burn
- Check `case_errors{reason}` to see which failure dominates.
- 404 spikes point to a customer data problem. 500s point to a code or disk fault.
- Roll back the last deploy if errors began after it.

## A2 Latency SLO
- Compare `dependency_duration_ms` (identity) with `model_invoke_duration_ms`. The larger one is the cause.
- In Incident 01, identity contributed 71% of the excess.
- Raise a ticket with the identity provider owner if identity is slow. Check retry rate if the model is slow.

## A3 Model retries
- Filter `model_retries_total` by `reason`.
- Open a trace with `attempt=2` and compare attempt durations.
- Confirm the timeout threshold with the model provider.

## A4 Token cost
- Divide `model_wasted_tokens_total` by `model_tokens_total`.
- Cap retries at one per request if cost climbs.

## A5 Decision mix shift
- Compare `decisions_total` by `model_version`.
- If the shift follows a model change, roll the config `current` back to the `previous` entry and restart. Then ask for a review of the new weights.
- Route the affected cases to manual review.

## A6 Audit failure
- Check disk space and file permissions on `data/audit_log.jsonl`.
- Stop accepting decisions if audit cannot be written. An unaudited decision is a compliance breach.
- After repair, rebuild missing records from logs using `trace_id`.
- Run `python scripts/verify_audit.py`. A failure names the first tampered line. Escalate it as a security incident.

## A7 Identity latency
- Compare `identity.verify` durations across cases in recent traces.
- Contact the identity provider owner with two trace IDs.

## After the incident
- Write the timeline from the trace.
- Record root cause, impact and the budget spent.
- Add a regression check to `scripts/validate_recovery.py`.
