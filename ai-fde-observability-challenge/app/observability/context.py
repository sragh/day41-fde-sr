"""Request-scoped correlation context shared by logs, spans and metrics."""
from contextvars import ContextVar

SERVICE_NAME = "decisionstream"
SERVICE_VERSION = "1.0.0"

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[str | None] = ContextVar("span_id", default=None)
case_id_var: ContextVar[str | None] = ContextVar("case_id", default=None)


def current() -> dict:
    return {
        "trace_id": trace_id_var.get(),
        "span_id": span_id_var.get(),
        "case_id": case_id_var.get(),
    }
