"""
Audit Test 8 — Leadership Transition Analysis
audit/tests/leadership_transitions.py

Otázka:
    Sleduje sektorový leadership opakovatelné přechodové vzory?

Testy:
    A — R1 přechody (kdo nejčastěji nahradí R1 lídra)
    B — TOP3 exit → entry přechody
    C — Nejčastější předchůdci před každým lídrem

Zdroj dat:
    sector_rank_history.parquet (pouze rank data, bez Health)

Výstup CSV:
    leadership_transition_matrix.csv
    leadership_transition_counts.csv
    top3_exit_entry_transitions.csv
    leader_predecessors.csv
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from audit.data_loader import AuditData

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "audit" / "output"


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    """
    Spustí všechny tři přechodové testy a uloží CSV výstupy.
    Vrátí summary DataFrame pro report.
    """
    rank_df = data.rank_for_lookback(lookback)

    # Pivot: index=date, columns=sector, values=rank
    pivot = rank_df.pivot(index="date", columns="sector", values="rank")
    pivot = pivot.sort_index()
    dates = sorted(pivot.index.tolist())

    # ── Test A — R1 přechody ──────────────────────────────────────────────────
    r1_transitions = _compute_r1_transitions(pivot, dates)

    # ── Test B — TOP3 exit → entry ────────────────────────────────────────────
    top3_transitions = _compute_top3_transitions(pivot, dates)

    # ── Test C — předchůdci před R1 ───────────────────────────────────────────
    predecessors = _compute_predecessors(r1_transitions)

    # ── Ulož CSV ──────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _save_csvs(r1_transitions, top3_transitions, predecessors, lookback)

    # Vrať summary pro format_report
    summary_rows = []
    for (frm, to), count in sorted(r1_transitions.items(), key=lambda x: -x[1]):
        summary_rows.append({
            "lookback": lookback,
            "type": "R1_transition",
            "from": frm,
            "to": to,
            "count": count,
        })
    return pd.DataFrame(summary_rows)


# ── Test A ────────────────────────────────────────────────────────────────────

def _compute_r1_transitions(pivot: pd.DataFrame, dates: list) -> dict[tuple, int]:
    """
    Spočítá přechody R1 lídra: { (from_sector, to_sector): count }
    """
    transitions: dict[tuple, int] = defaultdict(int)
    prev_r1 = None

    for d in dates:
        row = pivot.loc[d]
        # R1 = sektor s rank == 1, bez SPY
        r1_candidates = row[row == 1].index.tolist()
        r1_candidates = [s for s in r1_candidates if s != "SPY"]
        if not r1_candidates:
            prev_r1 = None
            continue
        current_r1 = r1_candidates[0]

        if prev_r1 is not None and current_r1 != prev_r1:
            transitions[(prev_r1, current_r1)] += 1

        prev_r1 = current_r1

    return dict(transitions)


# ── Test B ────────────────────────────────────────────────────────────────────

def _compute_top3_transitions(
    pivot: pd.DataFrame,
    dates: list,
) -> dict[tuple, int]:
    """
    TOP3 exit → entry přechody.

    Pravidlo pro v1:
    Pokud počet exitů == počet entrií → párujeme podle rank pořadí.
    Pokud mismatch → zaznamenáme všechny kombinace (cross product).
    """
    transitions: dict[tuple, int] = defaultdict(int)

    for i in range(1, len(dates)):
        prev_date = dates[i - 1]
        curr_date = dates[i]

        prev_row = pivot.loc[prev_date]
        curr_row = pivot.loc[curr_date]

        prev_top3 = set(prev_row[prev_row <= 3].index) - {"SPY"}
        curr_top3 = set(curr_row[curr_row <= 3].index) - {"SPY"}

        exited  = sorted(prev_top3 - curr_top3)
        entered = sorted(curr_top3 - prev_top3)

        if not exited or not entered:
            continue

        if len(exited) == len(entered):
            # Páruj podle rank pořadí
            exited_ranked  = sorted(exited,  key=lambda s: prev_row.get(s, 99))
            entered_ranked = sorted(entered, key=lambda s: curr_row.get(s, 99))
            for ex, en in zip(exited_ranked, entered_ranked):
                transitions[(ex, en)] += 1
        else:
            # Cross product
            for ex in exited:
                for en in entered:
                    transitions[(ex, en)] += 1

    return dict(transitions)


# ── Test C ────────────────────────────────────────────────────────────────────

def _compute_predecessors(
    r1_transitions: dict[tuple, int],
) -> dict[str, dict[str, int]]:
    """
    Invertuje R1 transition matrix.
    { sektor: { předchůdce: count } }
    """
    predecessors: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (frm, to), count in r1_transitions.items():
        predecessors[to][frm] += count
    return {k: dict(v) for k, v in predecessors.items()}


# ── CSV export ────────────────────────────────────────────────────────────────

def _save_csvs(
    r1_transitions: dict[tuple, int],
    top3_transitions: dict[tuple, int],
    predecessors: dict[str, dict[str, int]],
    lookback: int,
) -> None:
    sectors = [s for s in [
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLY",
        "XLC", "XLB", "XLRE", "XLP", "XLU"
    ]]

    # Transition count matrix
    count_matrix = pd.DataFrame(0, index=sectors, columns=sectors)
    for (frm, to), cnt in r1_transitions.items():
        if frm in count_matrix.index and to in count_matrix.columns:
            count_matrix.loc[frm, to] = cnt
    count_matrix.to_csv(OUTPUT_DIR / "leadership_transition_matrix.csv")

    # Transition counts list
    rows = [{"from": f, "to": t, "count": c, "lookback": lookback}
            for (f, t), c in sorted(r1_transitions.items(), key=lambda x: -x[1])]
    pd.DataFrame(rows).to_csv(OUTPUT_DIR / "leadership_transition_counts.csv", index=False)

    # TOP3 exit → entry
    rows2 = [{"exited": f, "entered": t, "count": c, "lookback": lookback}
             for (f, t), c in sorted(top3_transitions.items(), key=lambda x: -x[1])]
    pd.DataFrame(rows2).to_csv(OUTPUT_DIR / "top3_exit_entry_transitions.csv", index=False)

    # Predecessors
    rows3 = []
    for sector, preds in predecessors.items():
        total = sum(preds.values())
        for pred, cnt in sorted(preds.items(), key=lambda x: -x[1]):
            rows3.append({
                "sector": sector,
                "predecessor": pred,
                "count": cnt,
                "share_pct": round(cnt / total * 100, 1) if total > 0 else 0,
                "lookback": lookback,
            })
    pd.DataFrame(rows3).to_csv(OUTPUT_DIR / "leader_predecessors.csv", index=False)


# ── Report ────────────────────────────────────────────────────────────────────

def format_report(df: pd.DataFrame) -> list[str]:
    """
    Sestaví report sekci pro Test 8.
    Načte CSV soubory pro detailní tabulky.
    """
    lines = []
    lines.append("=" * 65)
    lines.append("AUDIT TEST 8 — LEADERSHIP TRANSITION ANALYSIS")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Otázka: Sleduje sektorový leadership opakovatelné vzory?")
    lines.append("Zdroj:  sector_rank_history.parquet (bez Health)")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 65)

        # ── Test A: Top přechody ──────────────────────────────────────────────
        lines.append("\n  TEST A — NEJČASTĚJŠÍ R1 PŘECHODY\n")

        sub = df[df["lookback"] == lookback].copy()
        total_transitions = sub["count"].sum()

        top15 = sub.nlargest(15, "count")
        lines.append(f"  {'#':<3} {'From':<6} {'To':<6} {'Count':>6}  {'Share':>6}")
        lines.append(f"  {'-'*3} {'-'*6} {'-'*6} {'-'*6}  {'-'*6}")
        for i, (_, row) in enumerate(top15.iterrows(), 1):
            share = row["count"] / total_transitions * 100 if total_transitions > 0 else 0
            lines.append(
                f"  {i:<3} {row['from']:<6} {row['to']:<6} "
                f"{int(row['count']):>6}  {share:>5.1f}%"
            )
        lines.append(f"\n  Celkem R1 přechodů: {int(total_transitions)}")

        # ── Test A: Matice (top sektory) ─────────────────────────────────────
        lines.append("\n  R1 TRANSITION MATRIX (pravděpodobnost, top sektory)\n")

        try:
            matrix_path = OUTPUT_DIR / "leadership_transition_matrix.csv"
            matrix = pd.read_csv(matrix_path, index_col=0)

            # Filtruj na sektory s alespoň 1 přechodem
            active = [s for s in matrix.index if matrix.loc[s].sum() > 0 or matrix[s].sum() > 0]
            matrix = matrix.loc[active, active]

            # Převeď na pravděpodobnosti (řádek = from)
            row_sums = matrix.sum(axis=1)
            prob = matrix.div(row_sums, axis=0).fillna(0) * 100

            # Header
            cols = list(prob.columns)
            col_headers = " ".join(f"{c:>5}" for c in cols)
            header = f"  {'From/To':<7} " + col_headers
            lines.append(header)
            lines.append("  " + "-" * (8 + 6 * len(cols)))

            for idx in prob.index:
                row_str = f"  {idx:<7} "
                for c in cols:
                    v = prob.loc[idx, c]
                    if idx == c:
                        row_str += f"{'--':>5} "
                    elif v >= 1:
                        row_str += f"{v:>4.0f}% "
                    else:
                        row_str += f"{'':>5} "
                lines.append(row_str)
        except Exception:
            lines.append("  [Matice není dostupná]")

        # ── Test B: TOP3 exit → entry ─────────────────────────────────────────
        lines.append("\n\n  TEST B — TOP3 EXIT → ENTRY PŘECHODY (top 15)\n")
        try:
            t3_path = OUTPUT_DIR / "top3_exit_entry_transitions.csv"
            t3 = pd.read_csv(t3_path)
            t3 = t3[t3["lookback"] == lookback].nlargest(15, "count")
            total_t3 = t3["count"].sum()

            lines.append(f"  {'#':<3} {'Exited':<7} {'Entered':<8} {'Count':>6}  {'Share':>6}")
            lines.append(f"  {'-'*3} {'-'*7} {'-'*8} {'-'*6}  {'-'*6}")
            for i, (_, row) in enumerate(t3.iterrows(), 1):
                share = row["count"] / total_t3 * 100 if total_t3 > 0 else 0
                lines.append(
                    f"  {i:<3} {row['exited']:<7} {row['entered']:<8} "
                    f"{int(row['count']):>6}  {share:>5.1f}%"
                )
        except Exception:
            lines.append("  [TOP3 přechody nejsou dostupné]")

        # ── Test C: Předchůdci ────────────────────────────────────────────────
        lines.append("\n\n  TEST C — NEJČASTĚJŠÍ PŘEDCHŮDCI PŘED R1 LÍDREM\n")
        try:
            pred_path = OUTPUT_DIR / "leader_predecessors.csv"
            pred_df = pd.read_csv(pred_path)
            pred_df = pred_df[pred_df["lookback"] == lookback]

            # Top 3 předchůdci pro každý sektor
            key_sectors = ["XLK", "XLF", "XLE", "XLI", "XLV", "XLY"]
            for sector in key_sectors:
                s = pred_df[pred_df["sector"] == sector].nlargest(3, "count")
                if s.empty:
                    continue
                preds_str = "  ".join(
                    f"{row['predecessor']} ({row['share_pct']:.0f}%)"
                    for _, row in s.iterrows()
                )
                lines.append(f"  {sector:<6}: {preds_str}")
        except Exception:
            lines.append("  [Předchůdci nejsou dostupní]")

        # ── Interpretace ──────────────────────────────────────────────────────
        lines.append("\n\n  INTERPRETACE")
        lines.append("  " + "-" * 50)
        lines.append("  Tento test neprokazuje kauzalitu.")
        lines.append("  Ukazuje pouze historické frekvence přechodů.")
        lines.append("  Pokud určité přechody dominují (> 25% share),")
        lines.append("  může existovat opakující se rotační vzor.")
        lines.append("  Pokud jsou přechody rovnoměrně distribuované,")
        lines.append("  rotace je náhodná a nepředvídatelná.")
        lines.append("")

    return lines
