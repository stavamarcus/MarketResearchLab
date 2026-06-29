"""
IMS Audit v2 — Entry Point
audit/run_audit_v2.py

Spustí kompletní audit v1 + v2 sekce.

Spuštění:
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit_v2.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audit.data_loader import load_audit_data
from audit.forward_returns import compute_forward_returns

# v1 testy
from audit.tests.return_analysis import run as run_return, format_report as fmt_return
from audit.tests.relative_performance import run as run_relative, format_report as fmt_relative

# v2 testy
from audit.tests.fine_score_buckets import run as run_fine, format_report as fmt_fine
from audit.tests.component_profile import run as run_profile, format_report as fmt_profile
from audit.tests.component_quintiles import run as run_quintiles, format_report as fmt_quintiles

AUDIT_DIR = PROJECT_ROOT / "output" / "audit"


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = date.today()

    # ── 1. Data ───────────────────────────────────────────────────────
    data = load_audit_data(verbose=True)

    if data.signals.empty:
        print("[CHYBA] Archiv je prázdný.")
        sys.exit(1)

    # ── 2. Forward returns ────────────────────────────────────────────
    forward_df = compute_forward_returns(data, verbose=True)

    # Přidej komponenty z archivu do forward_df pro v2 testy
    component_cols = [
        "rank_improvement_20d", "rank_improvement_40d",
        "rs_vs_spy_20d", "up_down_volume_ratio_20d", "rank_stability_20d",
    ]
    archive_cols = ["date", "ticker"] + [c for c in component_cols if c in data.signals.columns]
    forward_df = forward_df.merge(
        data.signals[archive_cols],
        on=["date", "ticker"],
        how="left",
    )

    # ── 3. Testy v1 ───────────────────────────────────────────────────
    return_df   = run_return(forward_df)
    relative_df = run_relative(forward_df)

    # ── 4. Testy v2 ───────────────────────────────────────────────────
    fine_df      = run_fine(forward_df)
    profile_df   = run_profile(forward_df)
    quintiles_df = run_quintiles(forward_df)

    # ── 5. CSV výstupy ────────────────────────────────────────────────
    _save(forward_df,    "audit_forward_returns.csv")
    _save(return_df,     "audit_return_analysis.csv")
    _save(relative_df,   "audit_relative_performance.csv")
    _save(fine_df,       "ims_fine_score_buckets.csv")
    _save(profile_df,    "ims_component_profiles.csv")
    _save(quintiles_df,  "ims_component_quintiles.csv")

    # ── 6. Textový report ─────────────────────────────────────────────
    lines = _build_report(data.meta, forward_df, return_df, relative_df,
                          fine_df, profile_df, quintiles_df, run_date)

    report_path = AUDIT_DIR / f"ims_audit_v2_report_{run_date}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport uložen : {report_path}")
    print()
    print("\n".join(lines))


def _build_report(
    meta, forward_df, return_df, relative_df,
    fine_df, profile_df, quintiles_df, run_date,
) -> list[str]:
    from audit.report_writer import _format_data_availability, _format_radar_vs_high
    from audit.tests.return_analysis import format_report as fmt_ret
    from audit.tests.relative_performance import format_report as fmt_rel

    lines = []
    lines += [
        "=" * 75,
        "IMS AUDIT REPORT v2",
        f"Datum reportu : {run_date}",
        "=" * 75,
        "",
    ]

    lines += _format_data_availability(meta, forward_df)
    lines += [""]
    lines += fmt_ret(return_df)
    lines += [""]
    lines += fmt_rel(relative_df)
    lines += [""]
    lines += fmt_fine(fine_df)
    lines += [""]
    lines += fmt_profile(profile_df)
    lines += [""]
    lines += fmt_quintiles(quintiles_df)
    lines += [""]
    lines += _format_radar_vs_high(return_df, relative_df)
    lines += [
        "",
        "=" * 75,
        "OMEZENÍ",
        "=" * 75,
        "",
        "  1. Dataset: 2025-07-09 → 2026-06-23 (~241 obchodních dní)",
        "     Jeden tržní cyklus — výsledky nelze generalizovat.",
        "",
        "  2. Archiv obsahuje pouze score >= 60.",
        "     Nelze srovnat s tickery pod prahem.",
        "",
        "  3. Backfill aplikoval dnešní metodiku retroaktivně.",
        "",
        "  4. Komponenty jsou průměry za signal date — ne za celé období.",
        "     Kvintilová analýza měří prediktivní sílu komponenty v den signálu.",
        "",
        "  5. 95+ bucket: N < 20 — žádné závěry.",
        "",
        "=" * 75,
    ]
    return lines


def _save(df, filename: str) -> None:
    path = AUDIT_DIR / filename
    try:
        df.to_csv(path, index=False)
        print(f"CSV uloženo : {filename}  ({len(df)} řádků)")
    except Exception as exc:
        print(f"[WARN] {filename}: {exc}")


if __name__ == "__main__":
    main()
