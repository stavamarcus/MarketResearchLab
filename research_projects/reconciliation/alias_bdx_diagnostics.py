"""
alias_bdx_diagnostics.py — PRICE-RECON-01B-EXT cileny update.

READ-ONLY. Dva ukoly:
  1. NWS/GOOG/FOX: alias metadata z identity_map (alias_flag, identity_tier,
     evidence, source) -> potvrdit identity_alias_class_mismatch.
  2. BDX: cileny ACTIONS lookup BEZ whitelist filtru (vsechny labely),
     okno 2026-02-10 +-60 dni + cely 2025-01..2026-07.

NEDELA: MLE/IRC recon, backtest, API/TWS, zmenu dat, classifier opravu.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\alias_bdx_diagnostics.py

Edge cases:
    - identity_map musi mit sloupce alias_flag/identity_tier/evidence/source.
      Pokud chybi -> reportuje jako "column MISSING".
    - BDX ACTIONS: vypise VSECHNY unique labely pro BDX ticker + radky
      kolem 2026-02-10. Pokud BDX neni v ACTIONS -> reportuje.
    - name-based lookup (Becton/Dickinson): jen pokud ACTIONS ma 'name'
      sloupec.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

ALIAS_TICKERS = {"129348130": ("NWS", "NWSA"),
                 "208813720": ("GOOG", "GOOGL"),
                 "356858007": ("FOX", "FOXA")}
BDX_CONID = "4886"
BDX_TICKER = "BDX"
BDX_BOUNDARY = "2026-02-10"
NAME_HINTS = ["becton", "dickinson", "bd ", "biosciences", "waters"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sharadar-store",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store")
    ap.add_argument("--snapshot-id",
                    default="sharadar_full_equity_v20260705_01")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--identity-map",
                    default=r"C:\Users\stava\Projects\sharadar_mdsm_adapter\identity\identity_map_resolved_v2.csv")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    result = {"alias_cases": {}, "bdx": {}}

    # 1. alias metadata
    idmap = pd.read_csv(args.identity_map, dtype=str)
    id_cols = set(idmap.columns)
    wanted = ["ticker", "sharadar_ticker", "alias_flag", "identity_tier",
              "evidence", "source"]
    for conid, (mtk, stk) in ALIAS_TICKERS.items():
        row = idmap[idmap["conid"].astype(str) == conid]
        if row.empty:
            result["alias_cases"][conid] = {"status": "conid nenalezen"}
            continue
        r = row.iloc[0]
        info = {"conid": conid, "expected_mdsm_ticker": mtk,
                "expected_sharadar_ticker": stk}
        for col in wanted:
            info[col] = str(r[col]) if col in id_cols else "COLUMN_MISSING"
        # verdikt
        alias_flag = info.get("alias_flag", "")
        is_alias = (str(alias_flag).lower() in ("true", "1", "yes")
                    or info.get("ticker") != info.get("sharadar_ticker"))
        info["classification"] = ("identity_alias_class_mismatch"
                                  if is_alias else "needs_manual_review")
        result["alias_cases"][conid] = info

    # 2. BDX ACTIONS lookup (bez whitelist)
    adir = (Path(args.sharadar_store) / "snapshots" / args.snapshot_id
            / "parquet" / "ACTIONS")
    bdx = {"conid": BDX_CONID, "ticker": BDX_TICKER}
    if not adir.exists():
        bdx["status"] = "ACTIONS neexistuje"
    else:
        actions = pd.read_parquet(adir)
        ren = {}
        for c in actions.columns:
            if c.lower() in ("date", "action", "ticker", "value", "name",
                             "contraticker"):
                ren[c] = c.lower()
        actions = actions.rename(columns=ren)
        actions["date"] = actions["date"].astype(str).str[:10]

        # BDX ticker match
        bdx_rows = actions[actions["ticker"] == BDX_TICKER]
        bdx["bdx_ticker_rows"] = len(bdx_rows)
        bdx["bdx_all_labels"] = (bdx_rows["action"].value_counts().to_dict()
                                 if not bdx_rows.empty else {})
        # radky v okne 2025-01..2026-07
        win = bdx_rows[(bdx_rows["date"] >= "2025-01-01")
                       & (bdx_rows["date"] <= "2026-07-15")]
        bdx["bdx_events_in_window"] = [
            {"date": r["date"], "action": r["action"],
             "value": str(r.get("value", "")),
             "contraticker": str(r.get("contraticker", ""))}
            for _, r in win.iterrows()]
        # radky +-60 dni kolem boundary
        b = pd.Timestamp(BDX_BOUNDARY)
        bf = (b - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
        bt = (b + pd.Timedelta(days=60)).strftime("%Y-%m-%d")
        near = bdx_rows[(bdx_rows["date"] >= bf) & (bdx_rows["date"] <= bt)]
        bdx["near_boundary_events"] = [
            {"date": r["date"], "action": r["action"],
             "value": str(r.get("value", ""))}
            for _, r in near.iterrows()]

        # name-based lookup (pokud name sloupec)
        if "name" in actions.columns:
            nmask = actions["name"].astype(str).str.lower().apply(
                lambda n: any(h in n for h in NAME_HINTS))
            nrows = actions[nmask]
            nrows = nrows[(nrows["date"] >= "2025-06-01")
                          & (nrows["date"] <= "2026-07-15")]
            bdx["name_based_hits"] = [
                {"date": r["date"], "action": r["action"],
                 "ticker": r["ticker"], "name": str(r["name"]),
                 "value": str(r.get("value", ""))}
                for _, r in nrows.head(30).iterrows()]
        else:
            bdx["name_based_hits"] = "ACTIONS nema 'name' sloupec"

        # contraticker lookup (spinoff muze mit BDX jako contraticker)
        if "contraticker" in actions.columns:
            crows = actions[actions["contraticker"] == BDX_TICKER]
            crows = crows[(crows["date"] >= "2025-06-01")
                          & (crows["date"] <= "2026-07-15")]
            bdx["contraticker_hits"] = [
                {"date": r["date"], "action": r["action"],
                 "ticker": r["ticker"], "value": str(r.get("value", ""))}
                for _, r in crows.iterrows()]
        else:
            bdx["contraticker_hits"] = "ACTIONS nema 'contraticker' sloupec"

        # verdikt BDX
        has_ca = (bool(bdx["bdx_events_in_window"])
                  or (isinstance(bdx.get("name_based_hits"), list)
                      and bdx["name_based_hits"])
                  or (isinstance(bdx.get("contraticker_hits"), list)
                      and bdx["contraticker_hits"]))
        if has_ca:
            bdx["classification"] = "corporate_action_found_extended_lookup"
        else:
            bdx["classification"] = ("needs_manual_review_or_"
                                     "unmapped_adjustment_artifact")
    result["bdx"] = bdx

    _write(result, mrl, args.out)

    print("==== ALIAS CASES ====")
    for cid, info in result["alias_cases"].items():
        print(f"  {cid}: {info.get('classification')} | "
              f"alias_flag={info.get('alias_flag')} | "
              f"tier={info.get('identity_tier')} | "
              f"{info.get('ticker')}->{info.get('sharadar_ticker')}")
    print("\n==== BDX ====")
    print(f"  bdx_ticker_rows: {bdx.get('bdx_ticker_rows')}")
    print(f"  labels: {bdx.get('bdx_all_labels')}")
    print(f"  events_in_window: {len(bdx.get('bdx_events_in_window', []))}")
    print(f"  near_boundary: {len(bdx.get('near_boundary_events', []))}")
    nh = bdx.get("name_based_hits")
    print(f"  name_hits: {len(nh) if isinstance(nh, list) else nh}")
    ch = bdx.get("contraticker_hits")
    print(f"  contraticker_hits: {len(ch) if isinstance(ch, list) else ch}")
    print(f"  classification: {bdx.get('classification')}")
    return 0


def _write(result, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PRICE-RECON-01B-EXT_alias_bdx.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    L = ["# PRICE-RECON-01B-EXT — Alias + BDX Diagnostics", "",
         "## 1. Alias cases (NWS/GOOG/FOX)", ""]
    for cid, info in result["alias_cases"].items():
        L.append(f"### {cid} ({info.get('ticker')} -> "
                 f"{info.get('sharadar_ticker')})")
        L.append(f"- classification: **{info.get('classification')}**")
        L.append(f"- alias_flag: {info.get('alias_flag')}")
        L.append(f"- identity_tier: {info.get('identity_tier')}")
        L.append(f"- evidence: {info.get('evidence')}")
        L.append(f"- source: {info.get('source')}")
        L.append("")
    bdx = result["bdx"]
    L += ["## 2. BDX (4886) extended ACTIONS lookup", "",
          f"- classification: **{bdx.get('classification')}**",
          f"- bdx_ticker_rows: {bdx.get('bdx_ticker_rows')}",
          f"- all labels: {bdx.get('bdx_all_labels')}",
          f"- boundary: {BDX_BOUNDARY}", "",
          "### Events v okne 2025-01..2026-07", ""]
    for e in bdx.get("bdx_events_in_window", []):
        L.append(f"- {e['date']} {e['action']} value={e['value']} "
                 f"contra={e.get('contraticker')}")
    if not bdx.get("bdx_events_in_window"):
        L.append("- ZADNE")
    L += ["", "### Near boundary (+-60d)", ""]
    for e in bdx.get("near_boundary_events", []):
        L.append(f"- {e['date']} {e['action']} value={e['value']}")
    if not bdx.get("near_boundary_events"):
        L.append("- ZADNE")
    L += ["", "### Name-based hits (Becton/Dickinson/...)", ""]
    nh = bdx.get("name_based_hits")
    if isinstance(nh, list):
        for e in nh:
            L.append(f"- {e['date']} {e['action']} {e['ticker']} "
                     f"({e['name']}) value={e['value']}")
        if not nh:
            L.append("- ZADNE")
    else:
        L.append(f"- {nh}")
    L += ["", "### Contraticker hits (BDX jako contra)", ""]
    ch = bdx.get("contraticker_hits")
    if isinstance(ch, list):
        for e in ch:
            L.append(f"- {e['date']} {e['action']} ticker={e['ticker']} "
                     f"value={e['value']}")
        if not ch:
            L.append("- ZADNE")
    else:
        L.append(f"- {ch}")
    L += ["", "## Vyhrady",
          "- alias klasifikace: alias_flag=True NEBO ticker!=sharadar_ticker.",
          "- BDX: pokud extended lookup nenajde CA, zustava "
          "needs_manual_review (cache boundary bez ACTIONS evidence).", ""]
    (out_dir / "PRICE-RECON-01B-EXT_alias_bdx.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
