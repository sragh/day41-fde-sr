import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.observability import context, metrics
from app.observability.tracing import span

AUDIT = Path(__file__).resolve().parents[2] / "data" / "audit_log.jsonl"
AUDIT_SCHEMA_VERSION = 3
GENESIS = "GENESIS"
_LOCK = threading.Lock()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _record_hash(record: dict, prev_hash: str) -> str:
    """Hash of the record body chained to the previous record's hash."""
    return _digest(prev_hash + json.dumps(record, sort_keys=True, default=str))


def _last_hash(path: Path) -> str:
    """Chain tail. A legacy (unchained) last line is hashed as raw text."""
    if not path.exists():
        return GENESIS
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return GENESIS
    last = json.loads(lines[-1])
    return last.get("record_hash") or _digest(lines[-1])


def verify_chain(path: Path = None) -> dict:
    """Check every chained record. Legacy records before the chain starts are skipped."""
    path = path or AUDIT
    prev, chained, legacy = GENESIS, 0, 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if "record_hash" not in record:
            legacy += 1
            prev = _digest(line)
            continue
        claimed = record.pop("record_hash")
        if record.get("prev_hash") != prev or _record_hash(record, prev) != claimed:
            return {"valid": False, "first_bad_line": number, "chained": chained, "legacy": legacy}
        prev, chained = claimed, chained + 1
    return {"valid": True, "chained": chained, "legacy": legacy}


def input_hash(case) -> str:
    """Hash of the full request, so inputs are provable without storing them."""
    canonical = json.dumps(case.model_dump(), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_audit(
    case_id: str,
    trace_id: str,
    decision: str,
    model_version: str,
    model_retry_count: int = 0,
    **provenance,
):
    """Append one decision record. `provenance` holds optional evidence fields
    (risk_score, tokens, rules_version, input_hash, config_hash, ...)."""
    with span("audit.write", trace_id=trace_id, case_id=case_id):
        record = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "trace_id": trace_id,
            "span_id": context.span_id_var.get(),
            "decision": decision,
            "model_version": model_version,
            "model_retry_count": model_retry_count,
            **provenance,
        }

        try:
            with _LOCK:
                record["prev_hash"] = _last_hash(AUDIT)
                record["record_hash"] = _record_hash(record, record["prev_hash"])
                with AUDIT.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, default=str) + "\n")
        except OSError:
            metrics.inc("audit_write_failures_total")
            raise
        metrics.inc("audit_records_total")
