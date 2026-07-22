"""parity_check.py — DATA06 vs MDSM parity (one-off precondition).

DATA06 = Sharadar lineage; MDSM = IBKR/TWS lineage. Same format, different source.
Before the first real paper_manual plan, confirm MDSM is not silently diverging
from the validated DATA06/BT lineage on an overlapping historical day.

Compares, for one business_date: regime200, MLE TOP10 tickers + rank order,
ref close prices, and coverage/missing. Verdict PASS / WARN / FAIL (OQ-3):
  FAIL - regime differs, TOP10 set differs, or missing ref prices for TOP names
  WARN - TOP10 set identical but rank order differs, or ref prices differ > tol
  PASS - identical TOP10 + regime, prices within tolerance
WARN does not block but is consciously visible; FAIL blocks the first cycle.

Read-only, report-only: no orders, no state change.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

PRICE_TOL_PCT = 0.005   # 0.5% per-ticker close delta -> WARN band
TOP_N = 10


@dataclass
class ParityResult:
    business_date: str = ""
    verdict: str = "PASS"           # PASS / WARN / FAIL
    regime_a: Optional[bool] = None
    regime_b: Optional[bool] = None
    top_a: List[str] = field(default_factory=list)
    top_b: List[str] = field(default_factory=list)
    price_diffs: List[dict] = field(default_factory=list)   # {ticker,a,b,pct}
    missing_prices: List[str] = field(default_factory=list)
    fails: List[str] = field(default_factory=list)
    warns: List[str] = field(default_factory=list)


def _top(cands, n=TOP_N):
    return [c.ticker for c in sorted(cands, key=lambda x: x.rank_10d)[:n]]


def run_parity(src_a, src_b, business_date: str,
               price_tol_pct: float = PRICE_TOL_PCT,
               top_n: int = TOP_N) -> ParityResult:
    r = ParityResult(business_date=business_date)

    ra = src_a.regime_state(business_date)
    rb = src_b.regime_state(business_date)
    r.regime_a, r.regime_b = ra.regime_on, rb.regime_on
    if ra.regime_on != rb.regime_on:
        r.fails.append(f"regime differs: A={ra.regime_on} B={rb.regime_on}")

    r.top_a = _top(src_a.signal_candidates(business_date), top_n)
    r.top_b = _top(src_b.signal_candidates(business_date), top_n)
    if set(r.top_a) != set(r.top_b):
        only_a = [t for t in r.top_a if t not in r.top_b]
        only_b = [t for t in r.top_b if t not in r.top_a]
        r.fails.append(f"TOP{top_n} set differs: onlyA={only_a} onlyB={only_b}")
    elif r.top_a != r.top_b:
        r.warns.append(f"TOP{top_n} rank order differs (same set): "
                       f"A={r.top_a} B={r.top_b}")

    tickers = sorted(set(r.top_a) | set(r.top_b))
    pa = src_a.closes_at(business_date, tickers)
    pb = src_b.closes_at(business_date, tickers)
    for t in tickers:
        va, vb = pa.get(t), pb.get(t)
        if va is None or vb is None:
            r.missing_prices.append(t)
            continue
        if vb:
            pct = abs(va - vb) / abs(vb)
            if pct > price_tol_pct:
                r.price_diffs.append({"ticker": t, "a": va, "b": vb,
                                      "pct": round(pct * 100, 3)})
    if r.missing_prices:
        r.fails.append(f"missing ref prices for TOP names: {r.missing_prices}")
    if r.price_diffs:
        r.warns.append(f"{len(r.price_diffs)} ref prices differ > "
                       f"{price_tol_pct:.1%}")

    r.verdict = "FAIL" if r.fails else ("WARN" if r.warns else "PASS")
    return r


def render_json(r: ParityResult) -> str:
    return json.dumps(vars(r), indent=2, default=str)


def render_md(r: ParityResult) -> str:
    L = [f"# DATA06 vs MDSM Parity - {r.business_date}", ""]
    L.append(f"- verdict: **{r.verdict}**")
    L.append(f"- regime200: DATA06 **{r.regime_a}** | MDSM **{r.regime_b}**")
    L.append("")
    L.append("## MLE TOP10")
    L.append(f"- DATA06: {r.top_a}")
    L.append(f"- MDSM:   {r.top_b}")
    L.append("")
    if r.price_diffs:
        L.append(f"## Ref price differences (> {PRICE_TOL_PCT:.1%})")
        L.append("| ticker | DATA06 | MDSM | diff % |")
        L.append("|---|---|---|---|")
        for d in r.price_diffs:
            L.append(f"| {d['ticker']} | {d['a']} | {d['b']} | {d['pct']} |")
        L.append("")
    if r.missing_prices:
        L.append(f"## Missing ref prices\n- {r.missing_prices}\n")
    L.append(f"## FAIL ({len(r.fails)})")
    L += [f"- {x}" for x in r.fails] or ["_none_"]
    L.append("")
    L.append(f"## WARN ({len(r.warns)})")
    L += [f"- {x}" for x in r.warns] or ["_none_"]
    L.append("")
    if r.verdict == "FAIL":
        L.append("_FAIL blocks the first paper_manual cycle until the cause is "
                 "explained._")
    elif r.verdict == "WARN":
        L.append("_WARN does not block, but the differences above must be "
                 "consciously accepted before the first cycle._")
    else:
        L.append("_PASS: MDSM matches the DATA06/BT lineage on this day._")
    return "\n".join(L)


def main(argv=None):
    from .runner_config import load_config
    from .data_source import Data06PriceSource, MdsmPriceSource

    ap = argparse.ArgumentParser(description="DATA06 vs MDSM parity check")
    ap.add_argument("--config", required=True,
                    help="runner config (supplies universe/paths for both)")
    ap.add_argument("--business-date", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--price-tol-pct", type=float, default=PRICE_TOL_PCT)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    src_a = Data06PriceSource(
        universe_path=cfg.universe_path, view_dir=cfg.data06_view_dir,
        mle_project_path=cfg.mle_project_path,
        signal_cache_path=cfg.signal_cache_path,
        recompute_signals=cfg.recompute_signals)
    src_b = MdsmPriceSource(
        universe_path=cfg.universe_path, mdsm_project_path=cfg.mdsm_project_path,
        mle_project_path=cfg.mle_project_path,
        signal_cache_path=cfg.signal_cache_path,
        recompute_signals=cfg.recompute_signals)

    r = run_parity(src_a, src_b, args.business_date,
                   price_tol_pct=args.price_tol_pct)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (out / f"data06_mdsm_parity_{args.business_date}_{ts}.md").write_text(
        render_md(r), encoding="utf-8")
    (out / f"data06_mdsm_parity_{args.business_date}_{ts}.json").write_text(
        render_json(r), encoding="utf-8")
    print(f"parity: {r.verdict} | date {args.business_date} | report: {out}")
    return 0 if r.verdict != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
