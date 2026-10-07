import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

from .context import SERVICE_NAME, SERVICE_VERSION, current

logger = logging.getLogger('decisionstream')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(message)s'))
logger.handlers = [handler]
logger.setLevel(logging.INFO)

# Business-sensitive values that must never reach logs.
DROP_FIELDS = {'income', 'amount', 'customer_income', 'requested_amount'}

# Identifiers replaced with a stable pseudonym so events stay joinable.
PSEUDONYMISE_FIELDS = {'customer_id': 'customer_ref'}


def pseudonym(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def redact(fields: dict) -> dict:
    out = {}
    for key, value in fields.items():
        if key in DROP_FIELDS:
            continue
        if key in PSEUDONYMISE_FIELDS:
            out[PSEUDONYMISE_FIELDS[key]] = pseudonym(value)
        else:
            out[key] = value
    return out


def event(name: str, **fields):
    """Emit one JSON log line, enriched with correlation context and redacted.

    Explicit trace_id / span_id / case_id arguments override the context.
    """
    ctx = {k: v for k, v in current().items() if v is not None}
    record = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'event': name,
        'service': SERVICE_NAME,
        'service_version': SERVICE_VERSION,
        **ctx,
        **redact(fields),
    }
    logger.info(json.dumps(record, default=str))
