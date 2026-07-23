"""verify_apply.py - kontrola po APPLY (read-only).

Nezapisuje nic. Overuje ctyri veci, ktere architekt vyjmenoval:
  1) state.json      - pocet pozic, mnozstvi, cash, zadne duplicity
  2) journal         - fill records, unikatni fill_id, prave jeden LATE_ENTRY
  3) report          - applied / skipped / failed / audit_events_written
  4) broker vs local - stejne tickery a stejna mnozstvi

Pouziti:
    python verify_apply.py 2026-07-22
"""
import glob
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

MODE = "paper_manual"
STRAT = "mle_paper_01"
PM = f"order_plans/{STRAT}/{MODE}"
RP = f"reports/{STRAT}/{MODE}"
ST = f"runtime_state/{STRAT}/{MODE}/state.json"

problems = []


def check(ok, label, detail=""):
    print(f"  [{'OK  ' if ok else 'CHYBA'}] {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        problems.append(label)


def main(td):
    print("=" * 72)
    print(f"  KONTROLA PO APPLY - {td}")
    print("=" * 72)

    # ---------------------------------------------------------- 1) state
    print("\n1) state.json")
    state = json.loads(Path(ST).read_text(encoding="utf-8"))
    pos = state["positions"]
    tickers = [p["ticker"] for p in pos]
    print(f"  cash   : {state['cash']}")
    print(f"  equity : {state['equity']}")
    print(f"  pozic  : {len(pos)}")
    check(len(pos) == 10, "pocet pozic je 10", f"({len(pos)})")
    check(len(tickers) == len(set(tickers)), "zadna duplicitni pozice")
    check(all(p["entry_date"] == td for p in pos), "entry_date u vsech pozic",
          f"({sorted({p['entry_date'] for p in pos})})")
    exits = sorted({p["planned_exit_date"] for p in pos})
    check(len(exits) == 1, "jednotny planned_exit_date", f"({exits})")

    # ---------------------------------------------------------- 2) journal
    print("\n2) journal")
    rows = []
    try:
        import pyarrow.parquet as pq
        for p in sorted(glob.glob(
                f"journal_data/{MODE}/fills/date={td}/**/*.parquet",
                recursive=True)):
            rows += pq.ParquetFile(p).read().to_pylist()
    except ImportError:
        print("  (pyarrow chybi - fill records nelze precist)")
    ids = [r.get("fill_id") for r in rows]
    print(f"  fill records : {len(rows)}")
    print(f"  unikatnich   : {len(set(ids))}")
    check(len(rows) == 10, "10 fill records", f"({len(rows)})")
    check(len(ids) == len(set(ids)), "zadne duplicitni fill_id")
    check(all(str(i).startswith("ibkr:") and ":perm:" in str(i) for i in ids),
          "vsechny fill_id ve tvaru ibkr:<ucet>:perm:<permId>")

    devs = []
    for f in glob.glob(f"journal_data/{MODE}/events/*.jsonl"):
        for ln in Path(f).read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("event_type") == "EXECUTION_DEVIATION":
                devs.append(r)
    print(f"  EXECUTION_DEVIATION eventu: {len(devs)}")
    check(len(devs) == 1, "prave jeden deviation event", f"({len(devs)})")
    if devs:
        d = devs[0]
        check(d.get("deviation_code") == "LATE_ENTRY", "deviation_code LATE_ENTRY")
        check(d.get("affected_order_count") == 10, "affected_order_count 10")
        check(len({x["deviation_key"] for x in devs}) == len(devs),
              "zadne duplicitni deviation_key")
        print(f"  first/last fill: {d.get('actual_first_fill_timestamp')} .. "
              f"{d.get('actual_last_fill_timestamp')}")
        print(f"  min po open    : {d.get('first_fill_minutes_after_open')} / "
              f"{d.get('last_fill_minutes_after_open')}")

    # ---------------------------------------------------------- 3) report
    print("\n3) reconciliation report")
    rp = Path(RP) / f"reconciliation_report_{td}.md"
    txt = rp.read_text(encoding="utf-8", errors="replace")

    def field(name):
        m = re.search(rf"{name}:\s*\*\*([A-Za-z0-9_]+)\*\*", txt)
        return m.group(1) if m else None

    print(f"  result : {field('result')}")
    print(f"  phase  : {field('phase')}")
    check(field("result") == "PASS", "result PASS")
    check(field("phase") == "APPLIED", "phase APPLIED")
    check(field("applied") == "10", "applied 10", f"({field('applied')})")
    check(field("skipped") == "0", "skipped 0", f"({field('skipped')})")
    check(field("failed") == "0", "failed 0", f"({field('failed')})")
    check(field("blank") == "0", "blank 0", f"({field('blank')})")
    check(field("audit_events_written") == "1", "audit_events_written 1",
          f"({field('audit_events_written')})")

    # ------------------------------------------------------ 4) broker vs local
    print("\n4) broker vs local")
    artp = Path(PM) / f"normalized_fills_{td}.json"
    art = json.loads(artp.read_text(encoding="utf-8"))
    broker = {o["ticker"]: Decimal(str(o["total_quantity"])) for o in art["orders"]}
    local = {p["ticker"]: Decimal(str(p["shares"])) for p in pos}
    check(set(broker) == set(local), "stejne tickery")
    diff = [t for t in sorted(set(broker) | set(local))
            if broker.get(t) != local.get(t)]
    check(not diff, "stejna mnozstvi", f"(rozdily: {diff})" if diff else "")
    print(f"  {'TICKER':<8}{'broker':>10}{'local':>10}")
    for t in sorted(set(broker) | set(local)):
        print(f"  {t:<8}{str(broker.get(t)):>10}{str(local.get(t)):>10}")

    # ---------------------------------------------------------- zaver
    print("\n" + "=" * 72)
    if problems:
        print(f"  NALEZENO {len(problems)} PROBLEMU:")
        for p in problems:
            print(f"    - {p}")
        print("  APPLY NEOPAKUJ. Posli tento vypis.")
        return 1
    print("  VSE SEDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "2026-07-22"))
