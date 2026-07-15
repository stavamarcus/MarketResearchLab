"""
split_event_validation.py — SHARADAR-DATA-06-PRE2 split-event field check.

Cíl: rozhodnout, zda MDSM close = Sharadar close (split-adjusted) nebo
closeunadj (unadjusted), pomoci tickeru se SPLITEM (kde se close a
closeunadj lisí).

READ-ONLY. NEDELA: DATA-06 build, MLE/IRC regeneraci, backtest, API,
zmenu dat.

Spusteni (MRL env, cte ze store + MDSM + identity):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\split_event_validation.py

Argumenty:
    --sharadar-store  cesta ke store (ACTIONS + SEP)
    --snapshot-id     snapshot
    --mdsm-prices     MDSM prices dir (default z data_paths.yaml)
    --identity-map    identity_map_resolved_v2.csv
    --date-from/-to   obdobi hledani splitu (default MDSM/MLE 2025-07..2026-07)
    --window          dni kolem splitu (default 10)

Postup:
    1. ACTIONS schema + unique action labely (REPORT, nehardcode)
    2. filtr split eventy v obdobi
    3. kandidati: split & v identity_map & MDSM soubor & SEP data
    4. porovnani MDSM close vs SEP close/closeunadj/closeadj kolem splitu

Edge cases:
    - action label pro split NENI znamy predem -> skript vypise vsechny
      unique labely; split detekce hleda substring 'split' (case-insens).
      Pokud Sharadar pouziva jiny label, uzivatel upravi --split-label.
    - split ratio (value sloupec): format neni predpokladan, jen reportovan.
    - MDSM date muze byt index -> reset_index.
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
try:
    import yaml
except ImportError:
    yaml = None


def load_actions(store, snapshot_id):
    adir = Path(store) / "snapshots" / snapshot_id / "parquet" / "ACTIONS"
    if not adir.exists():
        return None, f"ACTIONS neexistuje: {adir}"
    return pd.read_parquet(adir), None


def load_sep_ticker(store, snapshot_id, ticker, date_from, date_to):
    sep_root = (Path(store) / "snapshots" / snapshot_id / "optimized"
                / "SEP_BY_YEAR")
    if not sep_root.exists():
        return None
    yfrom, yto = int(date_from[:4]), int(date_to[:4])
    frames = []
    for yr in range(yfrom, yto + 1):
        f = sep_root / f"year={yr}" / "data.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        if "date" not in df.columns:
            df = df.reset_index()
        df = df[df["ticker"] == ticker]
        df["date"] = df["date"].astype(str).str[:10]
        df = df[(df["date"] >= date_from) & (df["date"] <= date_to)]
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_mdsm(prices_dir, conid, date_from, date_to):
    cands = list(Path(prices_dir).glob(f"{conid}_*.parquet")) + \
            list(Path(prices_dir).glob(f"{conid}.parquet"))
    if not cands:
        return None
    df = pd.read_parquet(cands[0])
    if "date" not in df.columns:
        df = df.reset_index()
    if "date" not in df.columns:
        return None
    keep = [c for c in ("date", "close") if c in df.columns]
    df = df[keep]
    df["date"] = df["date"].astype(str).str[:10]
    df = df[(df["date"] >= date_from) & (df["date"] <= date_to)]
    return df


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sharadar-store",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store")
    ap.add_argument("--snapshot-id",
                    default="sharadar_full_equity_v20260705_01")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--mdsm-prices", default=None)
    ap.add_argument("--identity-map",
                    default=r"C:\Users\stava\Projects\sharadar_mdsm_adapter\identity\identity_map_resolved_v2.csv")
    ap.add_argument("--date-from", default="2025-07-09")
    ap.add_argument("--date-to", default="2026-07-04")
    ap.add_argument("--split-label", default=None,
                    help="explicitni action label pro split; jinak substring 'split'")
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--max-candidates", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    # MDSM prices dir z data_paths.yaml pokud nezadano
    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    mdsm_prices = args.mdsm_prices
    if not mdsm_prices and yaml is not None:
        cfg = mrl / "config" / "data_paths.yaml"
        if cfg.exists():
            c = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            mdsm_prices = c.get("mdsm", {}).get("prices_dir")
    if not mdsm_prices:
        print("SETUP FAIL: MDSM prices dir neznamy (zadej --mdsm-prices)")
        return 2

    # 1. ACTIONS
    actions, err = load_actions(args.sharadar_store, args.snapshot_id)
    if err:
        print(f"FAIL: {err}")
        return 2

    report = {"actions_columns": list(actions.columns)}
    # unique action labely
    acol = next((c for c in actions.columns if c.lower() == "action"), None)
    if acol is None:
        print(f"FAIL: ACTIONS nema 'action' sloupec; cols={list(actions.columns)}")
        return 2
    labels = actions[acol].astype(str).value_counts().to_dict()
    report["action_labels"] = labels

    print("ACTIONS columns:", list(actions.columns))
    print("action labely (top):")
    for k, v in list(labels.items())[:20]:
        print(f"  {k}: {v}")

    # 2. split eventy
    if args.split_label:
        split_mask = actions[acol].astype(str) == args.split_label
    else:
        split_mask = actions[acol].astype(str).str.lower().str.contains("split")
    dcol = next((c for c in actions.columns if c.lower() == "date"), None)
    tcol = next((c for c in actions.columns if c.lower() == "ticker"), None)
    splits = actions[split_mask].copy()
    splits[dcol] = splits[dcol].astype(str).str[:10]
    splits = splits[(splits[dcol] >= args.date_from)
                    & (splits[dcol] <= args.date_to)]
    report["n_split_events"] = len(splits)
    report["split_labels_used"] = (args.split_label
                                   or "substring 'split'")
    print(f"\nsplit eventu v obdobi {args.date_from}..{args.date_to}: {len(splits)}")

    if splits.empty:
        report["verdict"] = "NO_VALID_SPLIT_SAMPLE"
        _write(report, mrl, args.out)
        print("VERDIKT: NO_VALID_SPLIT_SAMPLE (zadny split v obdobi)")
        return 0

    # 3. identity_map
    idmap = pd.read_csv(args.identity_map, dtype=str)
    # ticker -> conid
    tick2conid = dict(zip(idmap["ticker"], idmap["conid"]))
    tick2shar = dict(zip(idmap["ticker"], idmap["sharadar_ticker"]))

    # 4. kandidati + porovnani
    candidates = []
    for _, srow in splits.iterrows():
        tk = str(srow[tcol])
        sdate = str(srow[dcol])
        if tk not in tick2conid:
            continue
        conid = tick2conid[tk]
        shar = tick2shar.get(tk, tk)
        # okno kolem splitu
        sd = pd.Timestamp(sdate)
        wf = (sd - pd.Timedelta(days=args.window * 2)).strftime("%Y-%m-%d")
        wt = (sd + pd.Timedelta(days=args.window * 2)).strftime("%Y-%m-%d")
        mdsm = load_mdsm(mdsm_prices, conid, wf, wt)
        if mdsm is None or mdsm.empty:
            continue
        sep = load_sep_ticker(args.sharadar_store, args.snapshot_id,
                              shar, wf, wt)
        if sep is None or sep.empty:
            continue
        mdsm = mdsm.rename(columns={"close": "close_mdsm"})
        m = mdsm.merge(sep, on="date")
        if m.empty:
            continue
        res = {"ticker": tk, "conid": conid, "sharadar_ticker": shar,
               "split_date": sdate,
               "split_value": str(srow.get(next((c for c in actions.columns
                                                  if c.lower() == "value"), ""), "")),
               "overlap_rows": len(m)}
        for fld in ("close", "closeunadj", "closeadj"):
            if fld not in m.columns:
                continue
            diff = (m["close_mdsm"] - m[fld]).abs()
            rel = diff / m[fld].abs().replace(0, float("nan"))
            res[fld] = {"mean_abs_diff": round(float(diff.mean()), 6),
                        "max_abs_diff": round(float(diff.max()), 6),
                        "match_rate": round(float((rel < 0.001).mean()), 4)}
        # best field
        valid = {f: res[f]["mean_abs_diff"] for f in
                 ("close", "closeunadj", "closeadj") if f in res}
        if valid:
            res["best_field"] = min(valid, key=valid.get)
        candidates.append(res)
        if len(candidates) >= args.max_candidates:
            break

    report["candidates"] = candidates
    report["n_candidates_compared"] = len(candidates)

    # verdikt
    if not candidates:
        report["verdict"] = "NO_VALID_SPLIT_SAMPLE"
        report["verdict_note"] = ("split eventy existuji, ale zadny "
                                  "nema soucasne identity_map + MDSM + SEP data")
    else:
        # agregace best_field
        bf = {}
        for c in candidates:
            b = c.get("best_field")
            if b:
                bf[b] = bf.get(b, 0) + 1
        winner = max(bf, key=bf.get) if bf else None
        # rozhodni close vs closeunadj (klicove)
        close_wins = bf.get("close", 0)
        unadj_wins = bf.get("closeunadj", 0)
        if close_wins > 0 and unadj_wins == 0:
            report["verdict"] = "MDSM_CLOSE_EQ_SHARADAR_CLOSE"
        elif unadj_wins > 0 and close_wins == 0:
            report["verdict"] = "MDSM_CLOSE_EQ_SHARADAR_CLOSEUNADJ"
        elif close_wins > 0 and unadj_wins > 0:
            report["verdict"] = "MIXED"
        else:
            report["verdict"] = "UNRESOLVED"
        report["best_field_distribution"] = bf

    _write(report, mrl, args.out)
    print(f"\nVERDIKT: {report['verdict']}")
    if report.get("best_field_distribution"):
        print(f"best_field distribuce: {report['best_field_distribution']}")
    return 0


def _write(report, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "SHARADAR-DATA-06-PRE2_split_validation.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    L = ["# SHARADAR-DATA-06-PRE2 — Split-Event Field Validation", "",
         f"## VERDIKT: {report.get('verdict')}", ""]
    if report.get("verdict_note"):
        L.append(report["verdict_note"]); L.append("")
    L += ["## ACTIONS", "",
          f"- columns: {report.get('actions_columns')}",
          f"- split label: {report.get('split_labels_used')}",
          f"- split eventu v obdobi: {report.get('n_split_events')}", "",
          "### action labely (top)", ""]
    for k, v in list(report.get("action_labels", {}).items())[:20]:
        L.append(f"- {k}: {v}")
    L += ["", "## Kandidati (split-event porovnani)", ""]
    for c in report.get("candidates", []):
        L.append(f"### {c['ticker']} (conid {c['conid']}, split {c['split_date']})")
        L.append(f"- split_value: {c.get('split_value')}")
        L.append(f"- overlap_rows: {c.get('overlap_rows')}")
        L.append(f"- best_field: {c.get('best_field')}")
        for fld in ("close", "closeunadj", "closeadj"):
            if fld in c:
                L.append(f"  - {fld}: mad={c[fld]['mean_abs_diff']} "
                         f"max={c[fld]['max_abs_diff']} "
                         f"match_rate={c[fld]['match_rate']}")
        L.append("")
    if report.get("best_field_distribution"):
        L += ["## best_field distribuce", "",
              f"{report['best_field_distribution']}", ""]
    L += ["## Rozhodnuti pro DATA-06", "",
          "- CLOSE -> DATA-06 close = Sharadar close (split-adjusted)",
          "- CLOSEUNADJ -> DATA-06 close = Sharadar closeunadj (raw)",
          "- NO_VALID_SPLIT_SAMPLE / MIXED / UNRESOLVED -> DATA-06 field "
          "decision je ASSUMPTION, ne fact; dokumentovat.", "",
          "## Vyhrady",
          "- split label detekce: substring 'split' nebo --split-label.",
          "- okno kolem splitu: +-2*window kalendarnich dni (ne trading).",
          "- match_rate: relativni diff < 0.1%.", ""]
    (out_dir / "SHARADAR-DATA-06-PRE2_split_validation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
