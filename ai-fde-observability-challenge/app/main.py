import re
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import PlainTextResponse

from app.models import CaseApplication, CaseDecision
from app.observability import context, metrics, slo, tracing
from app.observability.logging import event
from app.observability.metrics import inc, set_gauge, snapshot
from app.observability.tracing import span
from app.services import decision as decision_rules
from app.services.audit import input_hash, write_audit
from app.services.data_service import get_customer
from app.services.decision import decide
from app.services.identity import verify_identity
from app.services.risk_model import _load_config, config_hash, infer

app = FastAPI(title="DecisionStream AI", version="1.0.0")

ROUTE = "/case-application"

_cfg = _load_config()
event("service.start", model_version=_cfg["current"]["version"],
      previous_model_version=_cfg["previous"]["version"],
      model_config_hash=config_hash(_cfg), rules_version=decision_rules.RULES_VERSION)
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


def _incoming_trace_id(request: Request) -> str:
    """Honour a W3C traceparent header so upstream callers can correlate."""
    match = _TRACEPARENT.match(request.headers.get("traceparent", ""))
    return match.group(1) if match else tracing.new_trace_id()


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Meter rejected requests, which never reach the endpoint function."""
    metrics.inc("http_requests_total", route=request.url.path, status="422")
    inc("case_errors", reason="validation_failed")
    event("request.rejected", status_code=422, route=request.url.path,
          error_count=len(exc.errors()))
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/case-application", response_model=CaseDecision)
def case_application(case: CaseApplication, request: Request, response: Response):
    trace_id = _incoming_trace_id(request)
    response.headers["X-Trace-Id"] = trace_id
    start = time.perf_counter()
    status_code = 200
    outcome = "error"

    context.trace_id_var.set(trace_id)
    context.case_id_var.set(case.case_id)

    try:
        with span("POST /case-application", trace_id=trace_id, case_id=case.case_id):
            inc("case_requests")
            event(
                "case.received",
                trace_id=trace_id,
                case_id=case.case_id,
                customer_id=case.customer_id,
                country=case.country,
                requested_product=case.requested_product,
            )

            if not verify_identity(case.case_id, case.customer_id, trace_id):
                inc("case_errors", reason="identity_failed")
                status_code, outcome = 400, "identity_failed"
                raise HTTPException(status_code=400, detail="identity failed")

            customer = get_customer(case.customer_id, trace_id, case.case_id)
            if not customer:
                inc("case_errors", reason="customer_not_found")
                status_code, outcome = 404, "customer_not_found"
                raise HTTPException(status_code=404, detail="customer not found")

            score, model_version, tokens, retry_count, details = infer(case, customer, trace_id)
            decision, reason = decide(case.case_id, score, model_version, trace_id)

            write_audit(
                case.case_id,
                trace_id,
                decision,
                model_version,
                model_retry_count=retry_count,
                risk_score=round(score, 4),
                reason=reason,
                tokens=tokens,
                cost_usd=details["cost_usd"],
                retry_reason=details["retry_reason"],
                rules_version=decision_rules.RULES_VERSION,
                config_hash=details["config_hash"],
                input_hash=input_hash(case),
                service_version=context.SERVICE_VERSION,
            )

            inc(f"decision_{decision.lower()}")
            inc("decisions_total", decision=decision, model_version=model_version)
            if retry_count:
                inc("cases_with_retry_total", model_version=model_version)
            outcome = decision.lower()

            set_gauge("last_case_tokens", tokens)

            return CaseDecision(
                case_id=case.case_id,
                decision=decision,
                risk_score=score,
                model_version=model_version,
                reason=reason,
            )
    except HTTPException:
        raise
    except Exception:
        status_code = 500
        raise
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        set_gauge("last_case_latency_ms", elapsed_ms)
        metrics.observe("http_request_duration_ms", elapsed_ms, route=ROUTE, outcome=outcome)
        metrics.inc("http_requests_total", route=ROUTE, status=str(status_code))
        event("case.completed", status_code=status_code, outcome=outcome,
              duration_ms=elapsed_ms)


@app.get("/metrics-snapshot")
def metrics_snapshot():
    return snapshot()


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    return metrics.prometheus_text()


@app.get("/slo")
def slo_status():
    return slo.evaluate()


@app.get("/traces/{trace_id}")
def get_trace(trace_id: str):
    spans = tracing.get_trace(trace_id)
    if spans is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return {"trace_id": trace_id, "span_count": len(spans), "spans": spans}


@app.get("/cases/{case_id}/traces")
def case_traces(case_id: str):
    return {"case_id": case_id, "trace_ids": tracing.find_traces_by_case(case_id)}
