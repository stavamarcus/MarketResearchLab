"""
inspect_reconciliation_inputs.py — MRL-RECON-00 Reconciliation Inputs Inventory.

READ-ONLY inventory. Primarni zdroj cest: config/data_paths.yaml.
Hardcoded cesty jen fallback/sanity. NIC nemeni/nemaze/nestahuje/nespousti.

Umisteni: MarketResearchLab/research_projects/reconciliation/
Vlastnik: MarketResearchLab (research/orchestration layer, NE producent
archivu — ty produkuji MLE/IRC/IMS moduly).

NEDELA: backtest, MLE/IRC regeneraci, baseline zmenu, API volani,
spousteni kodu signalu.

Spusteni:
    conda activate <env s pandas+pyyaml>
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\inspect_reconciliation_inputs.py

Vystup:
    reports/reconciliation/MRL-RECON-00_inputs_inventory.md + .json

Edge cases:
    - config/data_paths.yaml MUSI existovat (primarni zdroj). Chybi ->
      pouzije fallback hardcoded cesty + WARNING.
    - archivy MLE/IRC/IMS jsou v JINYCH projektech (mimo MRL). Skript je
      overi lokalne; pokud projekt neexistuje -> MISSING.
    - MDSM prices je adresar parquet souboru -> schema z prvniho souboru
      (metadata), row count/date range levne per soubor.
    - velky CSV: row count streamovane, date range scan hlavicky+sloupce.
    - Windows cesty z YAML (C:\\...) na Linuxu nefunguji — skript bezi
      primarne na Windows u uzivatele.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None
try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

# fallback cesty (relativni k Projects) — jen pokud config chybi.
FALLBACK = {
    "MLE_archive": ("MarketLeadershipEngine", "output", "archive",
                    "rank_matrix_archive.csv"),
    "IRC_archive": ("industry_rank_calendar", "output", "archive",
                    "industry_rank_calendar_archive.csv"),
    "IMS_archive": ("InstitutionalMomentumScanner", "output", "archive",
                    "ims_candidates_archive.csv"),
    "MDSM_prices": ("MDSM-Lite", "data", "cache", "prices"),
    "MDSM_universe": ("MDSM-Lite", "data", "universe"),
    "identity_mapping": ("sharadar_mdsm_adapter", "identity",
                         "identity_map_resolved_v2.csv"),
}

# ocekavane archive soubory pro signal adresare z configu
SIGNAL_FILES = {
    "MLE": "rank_matrix_archive.csv",
    "IRC": "industry_rank_calendar_archive.csv",
    "IMS": "ims_candidates_archive.csv",
}

NOTES = {
    "MLE_archive": "truth pro MLE reconciliation; universe = MDSM (NE "
                   "Sharadar SP500 membership)",
    "IRC_archive": "truth pro IRC reconciliation; industry taxonomy z "
                   "industry_rank_calendar (NE Sharadar TICKERS)",
    "IMS_archive": "IMS archiv (mimo reconciliation baseline v0.1)",
    "MDSM_prices": "kratka price reference (parquet) pro Faze 1 price view "
                   "reconciliation; zjistit schema/identifikatory/price fields",
    "MDSM_universe": "MDSM universe — KRITICKE pro MLE reconciliation "
                     "(stejny universe jako puvodni archiv)",
    "identity_mapping": "ticker<->conid<->permaticker mapping",
}


def describe_csv(path: Path) -> dict:
    info = {"type": "csv", "columns": [], "row_count": None,
            "date_range": None, "error": None}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            info["columns"] = header
            didx = {c: i for i, c in enumerate(header)
                    if c.lower() in ("date", "datekey", "calendardate")}
            n = 0
            dmin = {c: None for c in didx}
            dmax = {c: None for c in didx}
            for row in reader:
                n += 1
                for c, i in didx.items():
                    if len(row) > i and row[i]:
                        v = row[i]
                        if dmin[c] is None or v < dmin[c]:
                            dmin[c] = v
                        if dmax[c] is None or v > dmax[c]:
                            dmax[c] = v
            info["row_count"] = n
            if didx:
                info["date_range"] = {c: [dmin[c], dmax[c]] for c in didx}
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def describe_parquet_dir(path: Path) -> dict:
    """Adresar parquet souboru: pocet, schema prvniho, row count, date range."""
    info = {"type": "parquet_dir", "n_parquet": 0, "columns": [],
            "total_rows": None, "date_range": None, "sample_file": None,
            "error": None}
    files = sorted(path.rglob("*.parquet"))
    info["n_parquet"] = len(files)
    if not files:
        return info
    if pq is None:
        info["error"] = "pyarrow neni — schema/rows nezname"
        return info
    try:
        info["sample_file"] = str(files[0].relative_to(path))
        pf0 = pq.ParquetFile(files[0])
        info["columns"] = [f.name for f in pf0.schema_arrow]
        # total rows (metadata soucet — bez nacteni dat)
        total = 0
        for f in files:
            try:
                total += pq.ParquetFile(f).metadata.num_rows
            except Exception:  # noqa: BLE001
                pass
        info["total_rows"] = total
        # date range: scan date sloupce z prvniho a posledniho souboru
        dcol = next((c for c in info["columns"]
                     if c.lower() in ("date", "datekey", "calendardate")),
                    None)
        if dcol:
            vals = []
            for f in (files[0], files[-1]):
                try:
                    df = pq.ParquetFile(f).read(columns=[dcol]).to_pandas()
                    s = df[dcol].dropna().astype(str)
                    if len(s):
                        vals += [s.min(), s.max()]
                except Exception:  # noqa: BLE001
                    pass
            if vals:
                info["date_range"] = {dcol: [min(vals), max(vals)],
                                      "note": "z prvniho+posledniho souboru, "
                                              "ne uplny scan"}
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def describe(path: Path) -> dict:
    if not path.exists():
        return {"status": "MISSING", "path": str(path)}
    if path.is_dir():
        # parquet adresar? jinak jen vypis
        pqs = list(path.rglob("*.parquet"))
        if pqs:
            return {"status": "FOUND", "path": str(path),
                    **describe_parquet_dir(path)}
        # jinak seznam souboru
        files = sorted(p.name for p in path.iterdir())[:30]
        return {"status": "FOUND", "path": str(path), "type": "dir",
                "files": files, "n_files": len(list(path.iterdir()))}
    if path.suffix.lower() == ".csv":
        return {"status": "FOUND", "path": str(path), **describe_csv(path)}
    return {"status": "FOUND", "path": str(path), "type": "other",
            "size_bytes": path.stat().st_size}


def load_config_paths(mrl_root: Path):
    """Nacti config/data_paths.yaml. Vraci (resolved dict, error/None)."""
    cfg_path = mrl_root / "config" / "data_paths.yaml"
    if not cfg_path.exists():
        return {}, f"config nenalezen: {cfg_path}"
    if yaml is None:
        return {}, "pyyaml neni nainstalovan"
    try:
        c = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        mdsm = c.get("mdsm", {})
        signals = mdsm.get("signals", {})
        resolved = {
            "MDSM_prices": mdsm.get("prices_dir"),
            "MDSM_universe": mdsm.get("universe_dir"),
            "MLE_archive_dir": signals.get("MLE"),
            "IRC_archive_dir": signals.get("IRC"),
            "IMS_archive_dir": signals.get("IMS"),
        }
        return resolved, None
    except Exception as e:  # noqa: BLE001
        return {}, f"{type(e).__name__}: {e}"



# ============ ROZSIRENI A: MDSM filename inspection ============

def inspect_mdsm_filenames(prices_dir: Path, identity_csv: Path) -> dict:
    """A) Zjisti identifikator v nazvech MDSM parquet souboru + match
    proti identity_map (conid/ticker/permaticker/sharadar_ticker)."""
    out = {"n_files": 0, "sample_names": [], "pattern": "UNKNOWN",
           "match": {}, "unmatched_sample": [], "error": None}
    if not prices_dir.exists():
        out["error"] = "prices_dir neexistuje"
        return out
    files = sorted(prices_dir.glob("*.parquet"))
    out["n_files"] = len(files)
    if not files:
        out["error"] = "zadne parquet"
        return out
    raw_stems = [f.stem for f in files]
    out["sample_names"] = raw_stems[:20]

    # detekce a strip suffixu resoluce (napr. _D1 = daily). Vezme cast
    # pred poslednim "_" pokud zbytek je alfanumericky suffix a prefix
    # je numericky (typicky {conid}_D1).
    def strip_suffix(s):
        if "_" in s:
            head, tail = s.rsplit("_", 1)
            # suffix kratky (<=3 znaky) a head neprazdny -> strip
            if head and len(tail) <= 3:
                return head
        return s
    stems = [strip_suffix(s) for s in raw_stems]
    out["stripped_sample"] = stems[:20]
    # detekce spolecneho suffixu
    suffixes = set()
    for s in raw_stems:
        if "_" in s:
            suffixes.add(s.rsplit("_", 1)[1])
    out["detected_suffixes"] = sorted(suffixes)[:10]

    # pattern detekce (na stripped)
    numeric = sum(1 for s in stems if s.isdigit())
    if numeric == len(stems):
        out["pattern"] = "numeric (pravdepodobne conid) po strippu suffixu"
    elif numeric == 0:
        out["pattern"] = "ticker-like (pravdepodobne ticker)"
    else:
        out["pattern"] = f"smiseny ({numeric}/{len(stems)} numeric)"

    # match proti identity_map
    if identity_csv.exists():
        try:
            import csv as _csv
            idmap = {"conid": set(), "ticker": set(),
                     "permaticker": set(), "sharadar_ticker": set()}
            with open(identity_csv, encoding="utf-8", errors="replace") as f:
                rd = _csv.DictReader(f)
                for row in rd:
                    for k in idmap:
                        v = str(row.get(k, "")).strip()
                        if v:
                            idmap[k].add(v)
            stem_set = set(stems)  # stripped
            for k, vals in idmap.items():
                matched = len(stem_set & vals)
                out["match"][k] = {
                    "matched_files": matched,
                    "match_rate": round(matched / len(stems), 4)
                    if stems else 0}
            # nejlepsi match kolona
            best = max(out["match"].items(),
                       key=lambda x: x[1]["matched_files"])
            out["best_id_column"] = best[0]
            # unmatched proti nejlepsi kolone
            best_vals = idmap[best[0]]
            unmatched = [s for s in stems if s not in best_vals]
            out["n_unmatched"] = len(unmatched)
            out["unmatched_sample"] = unmatched[:20]
        except Exception as e:  # noqa: BLE001
            out["error"] = f"identity match: {type(e).__name__}: {e}"
    else:
        out["error"] = "identity_map nenalezen pro match"
    return out


# ============ ROZSIRENI B: MDSM vs Sharadar close comparison ============

def load_sep_for_tickers(sep_by_year: Path, tickers: set,
                         date_from: str, date_to: str):
    """Nacti Sharadar SEP (compacted) pro dane tickery v obdobi.
    Vraci dict ticker -> DataFrame(date, close, closeadj, closeunadj)."""
    import pandas as _pd
    if not sep_by_year.exists():
        return None, "SEP_BY_YEAR neexistuje"
    yfrom = int(date_from[:4])
    yto = int(date_to[:4])
    frames = []
    for yr in range(yfrom, yto + 1):
        ydir = sep_by_year / f"year={yr}" / "data.parquet"
        if not ydir.exists():
            continue
        try:
            df = _pd.read_parquet(ydir)
            if "date" not in df.columns:
                df = df.reset_index()
            need = ["ticker", "date", "close", "closeadj", "closeunadj"]
            have = [c for c in need if c in df.columns]
            df = df[have]
            df["date"] = df["date"].astype(str).str[:10]
            df = df[df["ticker"].isin(tickers)]
            df = df[(df["date"] >= date_from) & (df["date"] <= date_to)]
            frames.append(df)
        except Exception:  # noqa: BLE001
            pass
    if not frames:
        return {}, None
    allsep = _pd.concat(frames, ignore_index=True)
    return {t: allsep[allsep["ticker"] == t].copy()
            for t in tickers}, None


def compare_close_fields(prices_dir: Path, sep_by_year: Path,
                         identity_csv: Path, test_tickers, n_days=60) -> dict:
    """B) Porovnej MDSM close vs Sharadar close/closeadj/closeunadj.
    Predpoklad: MDSM filename = conid (dle A). Pokud ne, uzivatel upravi."""
    import pandas as _pd
    out = {"tested": [], "per_ticker": {}, "verdict": None, "error": None}
    if not identity_csv.exists():
        out["error"] = "identity_map chybi"
        return out

    # ticker -> conid -> sharadar_ticker
    iddf = _pd.read_csv(identity_csv, dtype=str)
    # najdi conid pro test tickery (pres ticker sloupec)
    sel = iddf[iddf["ticker"].isin(test_tickers)]
    if sel.empty:
        out["error"] = "test tickery nenalezeny v identity_map"
        return out

    # sharadar_ticker pro nacteni SEP
    shar_tickers = set(sel["sharadar_ticker"].dropna())
    # obdobi: poslednich n_days (odhad pres siroke okno, filtr pozdeji)
    # pouzijeme fixed okno 2026-01-01..2026-07-04 (v ramci MDSM+SEP prekryvu)
    date_from, date_to = "2026-01-01", "2026-07-04"
    sep_map, err = load_sep_for_tickers(sep_by_year, shar_tickers,
                                        date_from, date_to)
    if err:
        out["error"] = err
        return out

    agg = {"close": [], "closeadj": [], "closeunadj": []}
    for _, row in sel.iterrows():
        tk = row["ticker"]
        conid = str(row["conid"]).strip()
        shar = row["sharadar_ticker"]
        # MDSM soubory maji suffix resoluce (napr. {conid}_D1.parquet)
        # -> hledej glob {conid}_*.parquet i {conid}.parquet
        cands = list(prices_dir.glob(f"{conid}_*.parquet")) + \
                list(prices_dir.glob(f"{conid}.parquet"))
        if not cands:
            out["per_ticker"][tk] = {"status": "MDSM file MISSING",
                                     "conid": conid}
            continue
        mdsm_file = cands[0]
        try:
            mdsm = _pd.read_parquet(mdsm_file)
            # date muze byt index (ne sloupec) -> reset
            if "date" not in mdsm.columns:
                mdsm = mdsm.reset_index()
            if "date" not in mdsm.columns:
                out["per_ticker"][tk] = {
                    "status": f"MDSM date sloupec chybi; "
                              f"cols={list(mdsm.columns)}"}
                continue
            keep = [c for c in ("date", "close") if c in mdsm.columns]
            mdsm = mdsm[keep]
            mdsm["date"] = mdsm["date"].astype(str).str[:10]
            mdsm = mdsm[(mdsm["date"] >= date_from)
                        & (mdsm["date"] <= date_to)]
            sep = sep_map.get(shar)
            if sep is None or sep.empty:
                out["per_ticker"][tk] = {"status": "SEP data MISSING",
                                         "sharadar_ticker": shar}
                continue
            sep = sep.copy()
            sep["date"] = sep["date"].astype(str)
            # MDSM close -> prejmenuj pred merge (vyhne se kolizi se SEP close)
            mdsm = mdsm.rename(columns={"close": "close_mdsm"})
            m = mdsm.merge(sep, on="date")
            m = m.tail(n_days)
            if m.empty:
                out["per_ticker"][tk] = {"status": "zadny prekryv datumu"}
                continue
            res = {"status": "OK", "conid": conid,
                   "sharadar_ticker": shar, "n_compared": len(m)}
            for fld in ("close", "closeadj", "closeunadj"):
                diff = (m["close_mdsm"] - m[fld]).abs()
                mad = float(diff.mean())
                mx = float(diff.max())
                # match rate: rel diff < 0.1%
                rel = diff / m[fld].abs().replace(0, float("nan"))
                mr = float((rel < 0.001).mean())
                res[fld] = {"mean_abs_diff": round(mad, 6),
                            "max_abs_diff": round(mx, 6),
                            "match_rate": round(mr, 4)}
                agg[fld].append(mad)
            # best field pro tento ticker
            best = min(("close", "closeadj", "closeunadj"),
                       key=lambda f: res[f]["mean_abs_diff"])
            res["best_field"] = best
            out["per_ticker"][tk] = res
            out["tested"].append(tk)
        except Exception as e:  # noqa: BLE001
            out["per_ticker"][tk] = {"status": f"ERROR: {e}"}

    # celkovy verdikt
    means = {f: (sum(v) / len(v)) if v else None
             for f, v in agg.items()}
    valid = {f: m for f, m in means.items() if m is not None}
    if valid:
        best_overall = min(valid, key=valid.get)
        out["verdict"] = {
            "best_matching_field": best_overall,
            "mean_abs_diff_by_field": {f: round(m, 6)
                                       for f, m in valid.items()}}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mrl-root", default=None,
                    help="MarketResearchLab root (default: odvozeno)")
    ap.add_argument("--projects-root", default=r"C:\Users\stava\Projects")
    ap.add_argument("--out", default=None)
    ap.add_argument("--sharadar-store",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store")
    ap.add_argument("--snapshot-id",
                    default="sharadar_full_equity_v20260705_01")
    ap.add_argument("--test-tickers",
                    default="AAPL,MSFT,NVDA,SPY")
    ap.add_argument("--skip-compare", action="store_true",
                    help="preskoc B (close comparison)")
    args = ap.parse_args(argv)

    # MRL root: odvozeni od skriptu (research_projects/reconciliation/ -> ../..)
    if args.mrl_root:
        mrl = Path(args.mrl_root)
    else:
        here = Path(__file__).resolve()
        # .../MarketResearchLab/research_projects/reconciliation/script.py
        mrl = here.parent.parent.parent
    projects = Path(args.projects_root)

    resolved, cfg_err = load_config_paths(mrl)
    results = {}
    warnings = []
    if cfg_err:
        warnings.append(f"config: {cfg_err} -> pouzit fallback")

    # 1. z configu (primarni)
    def add_from_config(key, path_str, note_key, is_signal_dir=None):
        if not path_str:
            results[key] = {"status": "UNKNOWN",
                            "note": "cesta neni v configu"}
            return
        p = Path(path_str)
        if is_signal_dir:
            # signal archive: adresar + ocekavany CSV soubor
            csv_file = p / SIGNAL_FILES[is_signal_dir]
            r = describe(csv_file)
            r["archive_dir"] = str(p)
        else:
            r = describe(p)
        r["note"] = NOTES.get(note_key, "")
        r["source"] = "config/data_paths.yaml"
        results[key] = r

    if resolved:
        add_from_config("MLE_archive", resolved.get("MLE_archive_dir"),
                        "MLE_archive", is_signal_dir="MLE")
        add_from_config("IRC_archive", resolved.get("IRC_archive_dir"),
                        "IRC_archive", is_signal_dir="IRC")
        add_from_config("IMS_archive", resolved.get("IMS_archive_dir"),
                        "IMS_archive", is_signal_dir="IMS")
        add_from_config("MDSM_prices", resolved.get("MDSM_prices"),
                        "MDSM_prices")
        add_from_config("MDSM_universe", resolved.get("MDSM_universe"),
                        "MDSM_universe")

    # 2. fallback pro to, co config nepokryl (identity mapping)
    for key, parts in FALLBACK.items():
        if key in results and results[key].get("status") == "FOUND":
            continue
        p = projects.joinpath(*parts)
        r = describe(p)
        r["note"] = NOTES.get(key, "")
        r["source"] = "fallback (hardcoded)"
        # nepreapisuj FOUND z configu
        if key not in results or results[key].get("status") != "FOUND":
            results[key] = r

    # ROZSIRENI A: filename inspection
    prices_dir = Path(resolved.get("MDSM_prices")) if resolved.get("MDSM_prices") else None
    identity_path = None
    if results.get("identity_mapping", {}).get("path"):
        identity_path = Path(results["identity_mapping"]["path"])
    filename_info = None
    if prices_dir and identity_path:
        print("  [A] MDSM filename inspection ...")
        filename_info = inspect_mdsm_filenames(prices_dir, identity_path)

    # ROZSIRENI B: close comparison
    compare_info = None
    if not args.skip_compare and prices_dir and identity_path:
        sep_by_year = (Path(args.sharadar_store) / "snapshots"
                       / args.snapshot_id / "optimized" / "SEP_BY_YEAR")
        test_tickers = [t.strip() for t in args.test_tickers.split(",")
                        if t.strip()]
        print("  [B] MDSM vs Sharadar close comparison ...")
        compare_info = compare_close_fields(prices_dir, sep_by_year,
                                            identity_path, test_tickers)

    # vystup
    out_dir = Path(args.out) if args.out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {"generated": datetime.now().isoformat(timespec="seconds"),
               "mrl_root": str(mrl), "projects_root": str(projects),
               "config_resolved": resolved, "warnings": warnings,
               "inventory": results,
               "mdsm_filename_inspection": filename_info,
               "close_comparison": compare_info}
    (out_dir / "MRL-RECON-00_inputs_inventory.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")

    L = [
        "# MRL-RECON-00 — Reconciliation Inputs Inventory",
        "",
        f"Generated: {payload['generated']}",
        f"MRL root: {mrl}",
        f"Primarni zdroj cest: config/data_paths.yaml",
        "",
        "READ-ONLY. FOUND/MISSING pro vstupy reconciliation gate.",
        "",
        "## METODICKE PRAVIDLO",
        "- 250denni reconciliation (2025-07 -> 2026-06): pouzit MDSM "
        "universe, NE historical SP500 membership.",
        "- IRC: pouzit industry taxonomy z industry_rank_calendar, NE "
        "Sharadar TICKERS industry labels.",
        "",
    ]
    if warnings:
        L += ["## WARNINGS", ""] + [f"- {w}" for w in warnings] + [""]
    L += ["## Config resolved paths", ""]
    for k, v in resolved.items():
        L.append(f"- {k}: `{v}`")
    L += ["", "## Souhrn", ""]
    for key, r in results.items():
        L.append(f"- {key}: **{r.get('status')}** "
                 f"({r.get('source', '')})")
    L += ["", "## Detail", ""]
    for key, r in results.items():
        L.append(f"### {key}")
        L.append(f"- status: **{r.get('status')}**")
        L.append(f"- note: {r.get('note')}")
        L.append(f"- source: {r.get('source', '')}")
        if r.get("path"):
            L.append(f"- path: `{r['path']}`")
        if r.get("archive_dir"):
            L.append(f"- archive_dir: `{r['archive_dir']}`")
        if r.get("type"):
            L.append(f"- type: {r['type']}")
        if r.get("columns"):
            L.append(f"- columns: {r['columns']}")
        if r.get("row_count") is not None:
            L.append(f"- row_count: {r['row_count']}")
        if r.get("total_rows") is not None:
            L.append(f"- total_rows: {r['total_rows']}")
        if r.get("n_parquet") is not None:
            L.append(f"- n_parquet: {r['n_parquet']}")
        if r.get("date_range"):
            L.append(f"- date_range: {r['date_range']}")
        if r.get("files"):
            L.append(f"- files: {r['files']}")
        if r.get("error"):
            L.append(f"- error: {r['error']}")
        L.append("")
    # ROZSIRENI A do MD
    if filename_info:
        L += ["## A) MDSM filename inspection", ""]
        L.append(f"- n_files: {filename_info.get('n_files')}")
        L.append(f"- pattern: {filename_info.get('pattern')}")
        L.append(f"- detected suffixes: {filename_info.get('detected_suffixes')}")
        L.append(f"- sample names (raw): {filename_info.get('sample_names')}")
        L.append(f"- stripped sample: {filename_info.get('stripped_sample')}")
        if filename_info.get("match"):
            L.append(f"- match proti identity_map:")
            for k, v in filename_info["match"].items():
                L.append(f"  - {k}: {v['matched_files']} souboru "
                         f"(rate {v['match_rate']})")
        if filename_info.get("best_id_column"):
            L.append(f"- **best_id_column: {filename_info['best_id_column']}**")
        if filename_info.get("n_unmatched") is not None:
            L.append(f"- unmatched: {filename_info['n_unmatched']}")
            L.append(f"- unmatched sample: {filename_info.get('unmatched_sample')}")
        if filename_info.get("error"):
            L.append(f"- error: {filename_info['error']}")
        L.append("")

    # ROZSIRENI B do MD
    if compare_info:
        L += ["## B) MDSM vs Sharadar close comparison", ""]
        if compare_info.get("verdict"):
            v = compare_info["verdict"]
            L.append(f"- **best_matching_field: {v['best_matching_field']}**")
            L.append(f"- mean_abs_diff by field: {v['mean_abs_diff_by_field']}")
        L.append(f"- tested: {compare_info.get('tested')}")
        for tk, r in compare_info.get("per_ticker", {}).items():
            L.append(f"### {tk}")
            L.append(f"- status: {r.get('status')}")
            if r.get("best_field"):
                L.append(f"- best_field: {r['best_field']} "
                         f"(n={r.get('n_compared')})")
                for fld in ("close", "closeadj", "closeunadj"):
                    if fld in r:
                        L.append(f"  - {fld}: mad={r[fld]['mean_abs_diff']} "
                                 f"max={r[fld]['max_abs_diff']} "
                                 f"match_rate={r[fld]['match_rate']}")
        if compare_info.get("error"):
            L.append(f"- error: {compare_info['error']}")
        L.append("")

    L += [
        "## Dalsi krok",
        "- FOUND kriticke vstupy (MLE/IRC archive, MDSM prices+universe) ->"
        " lze navrhnout DATA-06 price view dle MDSM schema.",
        "- MISSING -> doplnit pred prislusnou fazi reconciliation.",
        "- DATA-06 price view: navrhnout AZ podle zjisteneho MDSM prices "
        "schema (sloupce, identifikatory, price fields).",
        "",
    ]
    (out_dir / "MRL-RECON-00_inputs_inventory.md").write_text(
        "\n".join(L), encoding="utf-8")

    print("==== MRL-RECON-00 INVENTORY ====")
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    for key, r in results.items():
        print(f"  {key}: {r.get('status')} ({r.get('source','')})")
    if filename_info and filename_info.get("best_id_column"):
        print(f"  [A] MDSM id sloupec: {filename_info['best_id_column']} "
              f"(unmatched: {filename_info.get('n_unmatched')})")
    if compare_info and compare_info.get("verdict"):
        print(f"  [B] MDSM close ~ Sharadar "
              f"{compare_info['verdict']['best_matching_field']}")
    print(f"report: {out_dir / 'MRL-RECON-00_inputs_inventory.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
