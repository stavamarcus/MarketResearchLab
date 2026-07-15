"""
run_cap01_field_gate.py — CAP-01 Úkol 0: read-only snapshot field gate.

Ověřuje přítomnost sloupců sharesbas / sharefactor / marketcap
v pinovaném snapshotu přes adapter StoreHandle (žádné přímé čtení
parquet, žádné API, žádný rebuild). Zapisuje docs/MRL_CAP01_FIELD_GATE_REPORT.md.

Pravidla (zadání CAP-01 Úkol 0):
    sharesbas missing   → STOP (CAP-01 BLOCKED)
    marketcap missing   → pokračovat BEZ sanity anchoru (explicitně reportovat)
    sharefactor missing → pokračovat, split-risk vyšší
                          + POZOR: schemas.py nyní sharefactor obsahuje;
                          chybějící sloupec by rozbil fields=None cesty
                          nad reálným snapshotem → eskalovat k PM

Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_cap01_field_gate.py

Exit: 0 = gate OK (sharesbas přítomen), 1 = STOP, 2 = setup fail.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

MRL_ROOT = Path(__file__).resolve().parent
if str(MRL_ROOT) not in sys.path:
    sys.path.insert(0, str(MRL_ROOT))

CHECK_FIELDS = ("sharesbas", "sharefactor", "marketcap")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CAP-01 snapshot field gate")
    ap.add_argument("--config", default=str(MRL_ROOT / "config"
                                            / "data_paths.yaml"))
    args = ap.parse_args(argv)

    cfg = (yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
           or {}).get("sharadar_fundamentals") or {}
    if not cfg:
        print("SETUP FAIL: sekce sharadar_fundamentals chybí")
        return 2

    try:
        from sharadar_mdsm_adapter.config import load_config
        from sharadar_mdsm_adapter.sf1_store import SF1Store
        acfg = load_config(cfg["adapter_config"])
        handle = SF1Store(acfg).load(str(cfg["snapshot_id"]))
    except Exception as e:  # noqa: BLE001 — setup-level
        print(f"SETUP FAIL: {e}")
        return 2

    cols = set(handle.dataframe.columns)
    present = {f: (f in cols) for f in CHECK_FIELDS}

    if not present["sharesbas"]:
        gate = ("STOP", "sharesbas chybí v snapshotu — CAP-01 BLOCKED; "
                        "žádný fallback, žádný rebuild bez PM schválení")
    elif not present["marketcap"]:
        gate = ("OK_NO_ANCHOR", "pokračovat bez sanity anchoru "
                                "(explicitně reportováno)")
    elif not present["sharefactor"]:
        gate = ("OK_HIGHER_SPLIT_RISK",
                "pokračovat; split-risk vyšší + schemas.py obsahuje "
                "sharefactor → chybějící sloupec rozbíjí fields=None "
                "nad reálným snapshotem — eskalovat k PM")
    else:
        gate = ("OK", "všechna pole přítomna")

    lines = [
        "# CAP-01 Field Gate Report",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- snapshot_id: `{handle.snapshot_id}`",
        f"- snapshot rows: {len(handle)}",
        f"- snapshot columns: {len(cols)}",
        "",
        "| field | present |",
        "|---|---|",
    ]
    lines += [f"| {f} | {'ANO' if present[f] else 'NE'} |"
              for f in CHECK_FIELDS]
    lines += ["", f"## GATE: {gate[0]}", "", gate[1], ""]
    out = MRL_ROOT / "docs" / "MRL_CAP01_FIELD_GATE_REPORT.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    for f in CHECK_FIELDS:
        print(f"  {f:12s}: {'ANO' if present[f] else 'NE'}")
    print(f"GATE: {gate[0]} — {gate[1]}")
    print(f"report: {out}")
    return 0 if gate[0].startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())
