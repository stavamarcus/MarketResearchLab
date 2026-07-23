"""archive_paper_cycle.py - nemenny archiv jednoho paper cyklu.

Zkopiruje vsechny artefakty daneho obchodniho dne mimo repozitar, spocita
SHA-256 kazdeho souboru a zapise manifest. Zdrojove soubory NEMENI ani
nemaze - jen cte a kopiruje.

Proc to existuje: kod je v Gitu, tahle data ne (.gitignore drzi order_plans,
reports, runtime_state a journal_data mimo repozitar). Raw broker dump navic
uz z IBKR API nejde stahnout - reqExecutions vraci jen ~24 hodin zpetne.

Pouziti:
    python archive_paper_cycle.py 2026-07-22 --out "D:\\PaperCycles"
    python archive_paper_cycle.py 2026-07-22 --out "D:\\PaperCycles" --verify

Archiv se zamerne NEPREPISUJE. Kdyz cilova slozka existuje, skript skonci -
neco, co uz bylo jednou zapecetene, se nema tise menit.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MODE = "paper_manual"
STRAT = "mle_paper_01"

# (kategorie, glob relativni k paper_trading, povinne?)
PATTERNS = [
    ("broker_dump",   f"order_plans/{STRAT}/{MODE}/broker_executions_{{d}}_*.json", True),
    ("normalized",    f"order_plans/{STRAT}/{MODE}/normalized_fills_{{d}}.json", True),
    ("ticket",        f"order_plans/{STRAT}/{MODE}/manual_order_ticket_{{d}}.csv", True),
    ("plan",          f"order_plans/{STRAT}/{MODE}/orders_plan_{{d}}.csv", True),
    ("trade_plan",    f"reports/{STRAT}/{MODE}/manual_report_{{d}}.md", True),
    ("recon_report",  f"reports/{STRAT}/{MODE}/reconciliation_report_{{d}}*.md", True),
    ("preview",       f"reports/{STRAT}/{MODE}/apply_preview_{{d}}.json", False),
    ("broker_check",  f"reports/{STRAT}/{MODE}/broker_connection_check_{{d}}*.md", False),
    ("freshness",     f"reports/{STRAT}/{MODE}/mdsm_freshness_{{d}}*.md", False),
    ("audit_log",     f"reports/{STRAT}/{MODE}/reconciliation_audit.log", True),
    ("state",         f"runtime_state/{STRAT}/{MODE}/state.json", True),
    ("state_backup",  f"runtime_state/{STRAT}/{MODE}/state.json.*.bak", False),
    ("journal_fills", f"journal_data/{MODE}/fills/date={{d}}/**/*.parquet", True),
    ("journal_events", f"journal_data/{MODE}/events/*.jsonl", True),
]

GIT_REPOS = [
    ("MarketResearchLab", ".."),
    ("launcher", "../.."),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: Path):
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            return None
        head = out.stdout.strip()
        url = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=15)
        return {"commit": head,
                "remote": url.stdout.strip() if url.returncode == 0 else None}
    except (OSError, subprocess.SubprocessError):
        return None


def collect(root: Path, target_date: str):
    found, missing = [], []
    for category, pattern, required in PATTERNS:
        pat = pattern.format(d=target_date)
        hits = sorted(p for p in root.glob(pat) if p.is_file())
        if hits:
            found += [(category, p) for p in hits]
        elif required:
            missing.append((category, pat))
    return found, missing


def do_archive(root: Path, out_dir: Path, target_date: str, force: bool):
    dest = out_dir / f"paper_cycle_{target_date}"
    if dest.exists() and not force:
        raise SystemExit(
            f"STOP: archiv uz existuje: {dest}\n"
            f"Zapecetenym archivem se nema tise hybat. Kdyz ho opravdu chces "
            f"prepsat, smaz ho rucne nebo pouzij --force.")

    found, missing = collect(root, target_date)
    if not found:
        raise SystemExit(f"STOP: pro {target_date} se nenasel zadny artefakt. "
                         f"Spoustis to ze spravneho adresare (paper_trading)?")

    print(f"Archivuji {len(found)} souboru do {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    lines, records = [], []
    for category, src in sorted(found, key=lambda t: str(t[1])):
        rel = src.relative_to(root)
        tgt = dest / "files" / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, tgt)
        digest = sha256(tgt)
        if digest != sha256(src):
            raise SystemExit(f"STOP: kopie {rel} nesouhlasi se zdrojem")
        posix = str(rel).replace(os.sep, "/")
        lines.append(f"{digest}  files/{posix}")
        records.append({"category": category, "path": posix,
                        "sha256": digest, "bytes": tgt.stat().st_size})
        print(f"  [{category:<14}] {posix}")

    (dest / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n",
                                         encoding="utf-8")

    manifest = {
        "schema": "paper_cycle_archive/1.0",
        "target_date": target_date,
        "mode": MODE,
        "strategy_dir": STRAT,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root.resolve()),
        "file_count": len(records),
        "total_bytes": sum(r["bytes"] for r in records),
        "git_checkpoints": {name: git_head((root / rel).resolve())
                            for name, rel in GIT_REPOS},
        "missing_required": [{"category": c, "pattern": p} for c, p in missing],
        "files": records,
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSHA256SUMS.txt a MANIFEST.json zapsany.")
    print(f"celkem {len(records)} souboru, {manifest['total_bytes']} B")
    for name, info in manifest["git_checkpoints"].items():
        print(f"  git {name:<20} {info['commit'] if info else '(nezjisteno)'}")
    if missing:
        print("\nPOZOR - chybi povinne artefakty:")
        for c, p in missing:
            print(f"  [{c}] {p}")
        print("  Archiv je NEUPLNY. Zjisti proc, nez ho ulozis stranou.")
        return 4
    print("\nArchiv je uplny. Zkopiruj slozku na druhe uloziste.")
    return 0


def do_verify(out_dir: Path, target_date: str):
    dest = out_dir / f"paper_cycle_{target_date}"
    sums = dest / "SHA256SUMS.txt"
    if not sums.exists():
        raise SystemExit(f"STOP: {sums} neexistuje")
    bad, ok = [], 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        p = dest / rel
        if not p.exists():
            bad.append((rel, "chybi"))
        elif sha256(p) != digest:
            bad.append((rel, "jiny obsah"))
        else:
            ok += 1
    print(f"overeno {ok} souboru")
    if bad:
        print("PROBLEMY:")
        for rel, why in bad:
            print(f"  {rel}: {why}")
        return 5
    print("Archiv je neporuseny.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Nemenny archiv paper cyklu")
    ap.add_argument("target_date", help="napr. 2026-07-22")
    ap.add_argument("--out", required=True, help="korenova slozka archivu")
    ap.add_argument("--root", default=".", help="paper_trading (default .)")
    ap.add_argument("--verify", action="store_true",
                    help="jen overit existujici archiv proti checksumum")
    ap.add_argument("--force", action="store_true",
                    help="prepsat existujici archiv (nedoporuceno)")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    if args.verify:
        return do_verify(out_dir, args.target_date)
    return do_archive(Path(args.root), out_dir, args.target_date, args.force)


if __name__ == "__main__":
    sys.exit(main())
