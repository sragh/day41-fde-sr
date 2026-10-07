import hashlib
import json
import time
from pathlib import Path

from app import faults
from app.observability import metrics
from app.observability.logging import event
from app.observability.tracing import span

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "model_config.json"


def _load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def config_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def infer(case, customer, trace_id: str):
    """Returns (score, model_version, tokens_total, retry_count, details)."""
    full_config = _load_config()
    config = full_config["current"]
    model_version = config["version"]
    price_per_1k = full_config.get("pricing", {}).get("usd_per_1k_tokens", 0.0)

    with span("risk_model.invoke", trace_id=trace_id, case_id=case.case_id,
              model_version=model_version) as invoke_attrs:
        timeout_fault = faults.triggered("model_timeout", case.case_id, faults.MODEL_TIMEOUT_CASES)
        invoke_attrs["fault_injected"] = timeout_fault
        attempts = 2 if timeout_fault else 1
        tokens_total = 0
        wasted_tokens = 0
        score = 0.0
        retry_reason = None
        invoke_start = time.perf_counter()

        for attempt in range(1, attempts + 1):
            with span(
                f"risk_model.attempt.{attempt}",
                trace_id=trace_id,
                case_id=case.case_id,
                model_version=model_version,
                attempt=attempt,
            ) as attrs:
                attempt_start = time.perf_counter()
                time.sleep(0.16 if attempt == 1 else 0.32)
                tokens = 1350 if attempt == 1 else 1600
                tokens_total += tokens
                attrs["tokens"] = tokens
                metrics.inc("model_calls", model_version=model_version)
                metrics.inc("model_tokens_total", tokens, model_version=model_version)

                if timeout_fault and attempt == 1:
                    retry_reason = "timeout"
                    wasted_tokens += tokens
                    attrs["outcome"] = "retry"
                    attrs["retry_reason"] = retry_reason
                    metrics.inc("model_retries_total", model_version=model_version,
                                reason=retry_reason)
                    event(
                        "model.retry",
                        case_id=case.case_id,
                        attempt=attempt,
                        reason=retry_reason,
                        model_version=model_version,
                        tokens=tokens,
                    )
                    metrics.observe("model_attempt_duration_ms",
                                    (time.perf_counter() - attempt_start) * 1000,
                                    model_version=model_version)
                    continue

                attrs["outcome"] = "success"
                debt_ratio = case.amount / max(case.income, 1)
                score = min(
                    0.99,
                    config["base_score"]
                    + debt_ratio * config["debt_weight"]
                    + (
                        config["foreign_country_penalty"]
                        if case.country != "IN"
                        else 0
                    ),
                )
                metrics.observe("model_attempt_duration_ms",
                                (time.perf_counter() - attempt_start) * 1000,
                                model_version=model_version)

        retry_count = max(0, attempts - 1)
        cost_usd = round(tokens_total / 1000 * price_per_1k, 6)
        metrics.observe("model_invoke_duration_ms",
                        (time.perf_counter() - invoke_start) * 1000,
                        model_version=model_version)
        metrics.inc("model_cost_usd_total", cost_usd, model_version=model_version)
        if wasted_tokens:
            metrics.inc("model_wasted_tokens_total", wasted_tokens, model_version=model_version)
        metrics.observe("risk_score", score, buckets=(0.2, 0.3, 0.45, 0.6, 0.7, 0.85),
                        model_version=model_version)

        invoke_attrs.update(tokens=tokens_total, retry_count=retry_count,
                            risk_score=round(score, 3), cost_usd=cost_usd)
        # Income and amount are deliberately not logged; they remain in the audit input hash.
        event(
            "model.result",
            case_id=case.case_id,
            model_version=model_version,
            tokens=tokens_total,
            retry_count=retry_count,
            cost_usd=cost_usd,
            risk_score=round(score, 3),
        )
        details = {
            "cost_usd": cost_usd,
            "wasted_tokens": wasted_tokens,
            "retry_reason": retry_reason,
            "config_hash": config_hash(full_config),
        }
        return score, model_version, tokens_total, retry_count, details
