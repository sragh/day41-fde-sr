"""Render dashboards/production_health.html from docs/artifacts/evidence/evidence.json."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ev = json.loads((ROOT / "docs/artifacts/evidence/evidence.json").read_text())
m, slo, res = ev["metrics"], ev["slo"], ev["results"]
c = m["counters"]


def tile(title, value, sub="", status=""):
    return (f'<div class="tile {status}"><div class="t">{html.escape(title)}</div>'
            f'<div class="v">{html.escape(str(value))}</div><div class="s">{html.escape(sub)}</div></div>')


def s(x):
    return {"MET": "ok", "BREACHED": "bad"}.get(x, "")


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


cases = sum(v for k, v in c.items() if k.startswith("decisions_total"))
tokens = c.get("model_tokens_total{model_version=risk-2.1}", 0)
cost = c.get("model_cost_usd_total{model_version=risk-2.1}", 0)
wasted = c.get("model_wasted_tokens_total{model_version=risk-2.1}", 0)
dec = {d: c.get(f"decisions_total{{decision={d},model_version=risk-2.1}}", 0)
       for d in ("APPROVE", "REVIEW", "REJECT")}
flips = sum(r["flipped_by_model_update"] for r in res)
dep = m["histograms"]["dependency_duration_ms{dependency=identity-provider}"]
model = m["histograms"]["model_invoke_duration_ms{model_version=risk-2.1}"]

tiles = [
    tile("Availability", pct(slo["availability"]["value"]), f'objective {pct(slo["availability"]["objective"])}', s(slo["availability"]["status"])),
    tile("Latency P95 (bucket bound)", f'{slo["latency_p95_ms"]["value"]:.0f} ms', "objective 500 ms", s(slo["latency_p95_ms"]["status"])),
    tile("Model retry rate", pct(slo["model_retry_rate"]["value"]), "objective ≤ 2%", s(slo["model_retry_rate"]["status"])),
    tile("Audit completeness", pct(slo["audit_completeness"]["value"]), "objective 100%", s(slo["audit_completeness"]["status"])),
    tile("Tokens", f"{tokens:,}", f"{wasted:,} wasted on retries"),
    tile("Est. model cost", f"${cost:.3f}", "assumed $0.01 / 1k tokens"),
    tile("Decision mix", f'{dec["APPROVE"]}/{dec["REVIEW"]}/{dec["REJECT"]}', "approve / review / reject"),
    tile("Decisions changed by risk-2.1", f"{flips}/{cases}", "vs risk-2.0 counterfactual", "bad" if flips else ""),
    tile("Identity P95", f'{dep["p95"]:.0f} ms', "dependency latency"),
    tile("Model invoke P95", f'{model["p95"]:.0f} ms', "inference latency"),
]
rows = "".join(
    f'<tr class="{"bad" if r["flipped_by_model_update"] else ""}"><td>{r["case_id"]}</td><td>{r["latency_ms"]}</td>'
    f'<td>{r["decision"]}</td><td>{r["risk_score"]}</td><td>{r["decision_under_risk_2_0"]}</td></tr>' for r in res)

page = f"""<!doctype html><meta charset="utf-8"><title>DecisionStream production health</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--card:#f4f5f7;--ok:#1a7f37;--bad:#b42318;--mut:#666}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--card:#1d1f23;--ok:#4ade80;--bad:#f87171;--mut:#999}}}}
body{{font:14px system-ui;background:var(--bg);color:var(--fg);margin:24px}}
h1{{font-size:20px}}h2{{font-size:15px;margin-top:28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}}
.tile{{background:var(--card);padding:12px;border-radius:8px;border-left:4px solid transparent}}
.tile.ok{{border-color:var(--ok)}}.tile.bad{{border-color:var(--bad)}}
.t{{color:var(--mut);font-size:12px}}.v{{font-size:24px;font-weight:600}}.s{{color:var(--mut);font-size:12px}}
table{{border-collapse:collapse}}td,th{{padding:4px 12px;text-align:left;border-bottom:1px solid var(--card)}}
tr.bad td{{color:var(--bad)}}
</style>
<h1>DecisionStream production health</h1>
<p class="s">Snapshot of the validation workload (10 cases). Live source: /slo, /metrics, /metrics-snapshot.</p>
<h2>Reliability, performance, AI, cost, business</h2><div class="grid">{''.join(tiles)}</div>
<h2>Per-case view</h2>
<table><tr><th>Case</th><th>Latency ms</th><th>Decision (risk-2.1)</th><th>Score</th><th>Decision under risk-2.0</th></tr>{rows}</table>
"""
(ROOT / "dashboards" / "production_health.html").write_text(page)
print("wrote dashboards/production_health.html")
