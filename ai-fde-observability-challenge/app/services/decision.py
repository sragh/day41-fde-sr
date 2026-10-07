from app.observability.tracing import span
from app.observability.logging import event

RULES_VERSION = 'rules-1.0'
APPROVE_BELOW = 0.45
REVIEW_BELOW = 0.70


def decide(case_id: str, risk_score: float, model_version: str, trace_id: str):
    with span('decision.rules', trace_id=trace_id, case_id=case_id,
              rules_version=RULES_VERSION, model_version=model_version) as attrs:
        if risk_score < APPROVE_BELOW:
            decision, reason = 'APPROVE', 'risk below threshold'
        elif risk_score < REVIEW_BELOW:
            decision, reason = 'REVIEW', 'manual review required'
        else:
            decision, reason = 'REJECT', 'risk above threshold'
        attrs['decision'] = decision
        attrs['risk_score'] = round(risk_score, 3)
        event('business.decision', case_id=case_id, decision=decision,
              model_version=model_version, risk_score=round(risk_score, 3),
              rules_version=RULES_VERSION)
        return decision, reason
