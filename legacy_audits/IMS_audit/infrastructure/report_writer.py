"""
IMS Audit — Report Writer
audit/report_writer.py

Zodpovědnost:
    Sestavit finální audit report z výsledků všech testů.
    Uložit CSV výstupy a textový report.

Výstupy:
    output/audit/
        audit_forward_returns.csv      — raw forward returns per signál
        audit_return_analysis.csv      — agregované metriky per bucket+window
        audit_relative_performance.csv — alpha metriky per bucket+window
        audit_report_YYYY-MM-DD.txt    — čitelný textový report

Použití:
    from audit.report_writer import write_audit_report
    write_audit_report(meta, forward_df, return_df, relative_df)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from audit.tests.return_analysis import format_report as format_return
from audit.tests.relative_performance import format_report as format_relative

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR    = PROJECT_ROOT / "output" / "audit"


def write_audit_report(
    meta:        dict,
    forward_df:  pd.DataFrame,
    return_df:   pd.DataFrame,
    relative_df: pd.DataFrame,
    run_date:    date | None = None,
    verbose:     bool = True,
) -> Path:
    """
    Uloží CSV výstupy a sestaví textový audit report.

    Args:
        meta:        metadata z AuditData.meta
        forward_df:  výstup z compute_forward_returns()
        return_df:   výstup z return_analysis.run()
        relative_df: výstup z relative_performance.run()
        run_date:    datum reportu (výchozí: dnes)
        verbose:     logovat na stdout

    Returns:
        Path k textovému reportu
    """
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = run_date or date.today()

    # ── CSV výstupy ───────────────────────────────────────────────────
    _save_csv(forward_df,  AUDIT_DIR / "audit_forward_returns.csv",      verbose)
    _save_csv(return_df,   AUDIT_DIR / "audit_return_analysis.csv",      verbose)
    _save_csv(relative_df, AUDIT_DIR / "audit_relative_performance.csv", verbose)

    # ── Textový report ────────────────────────────────────────────────
    lines = _build_report(meta, forward_df, return_df, relative_df, run_date)

    report_path = AUDIT_DIR / f"audit_report_{run_date}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    if verbose:
        print(f"Report uložen : {report_path}")

    return report_path


# ── Sestavení reportu ─────────────────────────────────────────────────────────

def _build_report(
    meta:        dict,
    forward_df:  pd.DataFrame,
    return_df:   pd.DataFrame,
    relative_df: pd.DataFrame,
    run_date:    date,
) -> list[str]:

    lines = []

    # Hlavička
    lines += [
        "=" * 65,
        "IMS AUDIT REPORT v1",
        f"Datum reportu : {run_date}",
        "=" * 65,
        "",
    ]

    # Sekce A: Data Availability
    lines += _format_data_availability(meta, forward_df)

    # Sekce B: Return Analysis
    lines += [""]
    lines += format_return(return_df)

    # Sekce C: Relative Performance
    lines += [""]
    lines += format_relative(relative_df)

    # Sekce D: RADAR vs HIGH souhrn
    lines += [""]
    lines += _format_radar_vs_high(return_df, relative_df)

    # Footer
    lines += [
        "",
        "=" * 65,
        "OMEZENÍ TOHOTO AUDITU",
        "=" * 65,
        "",
        "  1. Dataset: 2025-07-09 → 2026-06-23 (~241 obchodních dní)",
        "     Jeden tržní cyklus — výsledky nelze generalizovat.",
        "",
        "  2. Archiv obsahuje pouze score >= 60.",
        "     Nelze srovnat s tickery pod prahem (score < 60).",
        "",
        "  3. Backfill retroaktivně aplikoval dnešní metodiku na historická data.",
        "     Tržní podmínky 2025-2026 mohou zkreslit výsledky jedním směrem.",
        "",
        "  4. Neuvažujeme transakční náklady, slippage ani pozicování.",
        "",
        "  5. Win rate a alpha jsou nutné, ale ne postačující podmínky",
        "     pro obchodní hodnotu — záleží také na risk/reward poměru.",
        "",
        "=" * 65,
    ]

    return lines


def _format_data_availability(meta: dict, forward_df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("SEKCE A — DATA AVAILABILITY")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"  Signal rozsah    : {meta['signal_date_min']} → {meta['signal_date_max']}")
    lines.append(f"  Signal dates     : {meta['signal_dates']}")
    lines.append(f"  Signal rows      : {meta['signal_rows']}")
    lines.append(f"  Tickerů v cache  : {meta['tickers_in_cache']} / {meta['tickers_in_archive']}")
    if meta['tickers_missing'] > 0:
        lines.append(f"  Tickerů chybí   : {meta['tickers_missing']} (vyřazeni z auditu)")
    lines.append(f"  Cache end        : {meta['cache_end']}")
    lines.append("")
    lines.append(f"  {'Window':<8} {'Usable rows':>12} {'Usable dates':>14} {'Through':>12}")
    lines.append(f"  {'-'*8} {'-'*12} {'-'*14} {'-'*12}")

    for window in [5, 10, 20, 30]:
        col_use = f"usable_{window}d"
        if col_use not in forward_df.columns:
            continue
        usable      = forward_df[forward_df[col_use] == True]
        n_rows      = len(usable)
        n_dates     = usable["date"].nunique() if not usable.empty else 0
        last_date   = str(usable["date"].max()) if not usable.empty else "N/A"
        lines.append(
            f"  {window}D      {n_rows:>12} {n_dates:>14} {last_date:>12}"
        )

    lines.append("")
    return lines


def _format_radar_vs_high(
    return_df:   pd.DataFrame,
    relative_df: pd.DataFrame,
) -> list[str]:
    lines = []
    lines.append("=" * 65)
    lines.append("SEKCE D — RADAR vs HIGH PRIORITY SOUHRN")
    lines.append("=" * 65)
    lines.append("")
    lines.append("  Srovnání skupin RADAR (60–69) vs HIGH (70+) souhrnně.")
    lines.append("")

    # HIGH = všechny buckety >= 70 dohromady
    high_buckets = ["H70-79", "H80-89", "H90-94", "H95+"]

    for window in [10, 20, 30]:
        w_str = f"{window}D"
        lines.append(f"  Forward {w_str}")
        lines.append(f"  {'Skupina':<12} {'N':>6} {'AvgRet':>8} {'MedRet':>8} {'WinRate':>8} {'AvgAlpha':>10}")
        lines.append(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

        # RADAR
        r_ret  = return_df[(return_df["bucket"] == "RADAR") & (return_df["window"] == w_str)]
        r_rel  = relative_df[(relative_df["bucket"] == "RADAR") & (relative_df["window"] == w_str)]
        if not r_ret.empty and not r_rel.empty:
            r = r_ret.iloc[0]; ra = r_rel.iloc[0]
            lines.append(
                f"  {'RADAR':<12} {int(r['n']):>6} "
                f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                f"{r['win_rate']:>7.1f}% {ra['avg_alpha']:>+9.2f}%"
            )

        # HIGH (agregát)
        h_ret = return_df[(return_df["bucket"].isin(high_buckets)) & (return_df["window"] == w_str)]
        h_rel = relative_df[(relative_df["bucket"].isin(high_buckets)) & (relative_df["window"] == w_str)]
        if not h_ret.empty and not h_rel.empty:
            n_total  = h_ret["n"].sum()
            # Vážený průměr
            avg_ret  = (h_ret["avg_return"]   * h_ret["n"]).sum() / n_total
            med_ret  = (h_ret["median_return"] * h_ret["n"]).sum() / n_total
            wr       = (h_ret["win_rate"]      * h_ret["n"]).sum() / n_total
            avg_alph = (h_rel["avg_alpha"]     * h_rel["n"]).sum() / h_rel["n"].sum()
            lines.append(
                f"  {'HIGH (70+)':<12} {int(n_total):>6} "
                f"{avg_ret:>+7.2f}% {med_ret:>+7.2f}% "
                f"{wr:>7.1f}% {avg_alph:>+9.2f}%"
            )

        lines.append("")

    lines.append("  Pokud HIGH konzistentně > RADAR napříč okny:")
    lines.append("  score threshold 70 má prediktivní hodnotu.")
    lines.append("  Pokud rozdíl není konzistentní:")
    lines.append("  threshold je arbitrární a neodráží skutečný signal quality.")
    lines.append("")

    return lines


# ── Helper ────────────────────────────────────────────────────────────────────

def _save_csv(df: pd.DataFrame, path: Path, verbose: bool) -> None:
    try:
        df.to_csv(path, index=False)
        if verbose:
            print(f"CSV uloženo   : {path.name}  ({len(df)} řádků)")
    except Exception as exc:
        print(f"[WARN] Nelze uložit {path.name}: {exc}")
