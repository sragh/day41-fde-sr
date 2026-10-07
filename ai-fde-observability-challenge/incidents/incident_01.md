# Incident 01 — CASE-1042

A customer reports that **CASE-1042** took much longer than usual and was **rejected after a recent model update**. Operations also noticed higher inference consumption but cannot reconstruct the transaction cleanly from existing telemetry.

## Reproduction request

Use the following request when reproducing the incident:

```json
{
  "case_id": "CASE-1042",
  "customer_id": "C001",
  "amount": 1100000,
  "country": "IN",
  "income": 900000,
  "requested_product": "PERSONAL_LOAN"
}
```

## Investigation objective

Determine what happened using evidence from code, generated logs, traces, metrics, business events, model configuration, and audit records. Separate **observed evidence** from **inference**.
