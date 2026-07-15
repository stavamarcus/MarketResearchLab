"""
rebuild_registry.py — zrekonstruuje registry/experiment_runs.jsonl z archivů.

PROČ: registry index se může přepsat (např. rozbalením ZIPu, který obsahoval starší
registry). Archivované běhy v results\\ však zůstávají — každý má metadata.json s plnými
údaji. Tento skript projde results\\<exp>\\<ver>\\<run>\\metadata.json a registry obnoví
z toho, co je reálně na disku.

BEZPEČNÉ: existující registry se před přepisem zazálohuje (.bak s timestampem).
Deduplikuje podle run_id. Nic nemaže z results\\.

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python rebuild_registry.py
    (nebo:  python rebuild_registry.py --dry-run   pro náhled bez zápisu)
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_ROOT  = Path("results")
REGISTRY_PATH = Path("registry/experiment_runs.jsonl")


def _read_metadata(meta_path: Path) -> dict | None:
    try:
        m = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ! nelze číst {meta_path}: {e}")
        return None

    ctx = m.get("context_summary", {}) or {}
    run_id = m.get("run_id") or ctx.get("run_id")
    if not run_id:
        return None

    run_path = meta_path.parent
    # registry používá relativní cestu s Windows separátory
    try:
        rel = run_path.relative_to(Path("."))
    except ValueError:
        rel = run_path
    run_path_str = str(rel).replace("/", "\\")

    return {
        "run_id":             run_id,
        "experiment_name":    m.get("experiment_name"),
        "experiment_version": m.get("experiment_version", "1.0.0"),
        "date_from":          ctx.get("date_from") or m.get("date_from"),
        "date_to":            ctx.get("date_to") or m.get("date_to"),
        "universe":           ctx.get("universe") or m.get("universe"),
        "started_at":         m.get("started_at"),
        "completed_at":       m.get("completed_at"),
        "result_hash":        m.get("result_hash") or m.get("result_hash_full"),
        "run_path":           run_path_str,
        "tags":               m.get("tags", []),
    }


def main(dry_run: bool = False) -> int:
    if not RESULTS_ROOT.exists():
        print(f"CHYBA: {RESULTS_ROOT} neexistuje. Jsi v kořeni MarketResearchLab?")
        return 1

    metas = sorted(RESULTS_ROOT.glob("*/*/*/metadata.json"))
    print(f"Nalezeno {len(metas)} archivovaných běhů v {RESULTS_ROOT}\\")

    records: dict[str, dict] = {}
    for mp in metas:
        rec = _read_metadata(mp)
        if rec is None:
            continue
        records[rec["run_id"]] = rec  # dedup podle run_id

    if not records:
        print("Žádné validní metadata.json — nic k obnově.")
        return 1

    # seřaď podle started_at (chronologicky)
    ordered = sorted(records.values(), key=lambda r: r.get("started_at") or "")

    by_exp: dict[str, int] = {}
    for r in ordered:
        by_exp[r["experiment_name"]] = by_exp.get(r["experiment_name"], 0) + 1

    print(f"\nObnovím {len(ordered)} běhů | {len(by_exp)} experimentů:")
    for exp, n in sorted(by_exp.items()):
        print(f"  {exp:28s} {n} běh(ů)")

    if dry_run:
        print("\n[DRY-RUN] Nic nezapsáno. Spusť bez --dry-run pro obnovu.")
        return 0

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if REGISTRY_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bak = REGISTRY_PATH.with_suffix(f".jsonl.bak_{ts}")
        shutil.copy2(REGISTRY_PATH, bak)
        print(f"\nZáloha stávajícího registry → {bak}")

    with REGISTRY_PATH.open("w", encoding="utf-8") as f:
        for r in ordered:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Registry obnoven: {REGISTRY_PATH} ({len(ordered)} záznamů)")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    raise SystemExit(main(dry_run=dry))
