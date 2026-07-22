"""broker_check.py — CLI for the read-only paper connection check.

Wires the real ibapi adapter and runs the check. `python -m
mle_paper_01.broker_check --config config/broker_readonly_paper.json`.
Read + report only: no orders, no state change, no journal.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .broker.check import CheckConfig, render_json, render_md, run_check


def _load_cfg(path, overrides) -> CheckConfig:
    data = {}
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.update({k: v for k, v in overrides.items() if v is not None})
    return CheckConfig(
        expected_account_id=data.get("expected_account_id", ""),
        host=data.get("host", "127.0.0.1"), port=int(data.get("port", 7497)),
        client_id=int(data.get("client_id", 102)),
        mode=data.get("mode", "paper"),
        timeout_seconds=float(data.get("timeout_seconds", 15.0)),
        paper_prefix=data.get("paper_prefix", "DU"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="IBKR paper read-only check")
    ap.add_argument("--config", default=None)
    ap.add_argument("--expected-account-id", default=None)
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", default=None)
    ap.add_argument("--client-id", default=None)
    ap.add_argument("--timeout-seconds", default=None)
    ap.add_argument("--out", default=".")
    args = ap.parse_args(argv)

    cfg = _load_cfg(args.config, {
        "expected_account_id": args.expected_account_id, "host": args.host,
        "port": args.port, "client_id": args.client_id,
        "timeout_seconds": args.timeout_seconds})

    from .broker.ib_readonly import IBReadOnlyBroker
    broker = IBReadOnlyBroker(cfg.host, cfg.port, cfg.client_id)

    result = run_check(broker, cfg)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (out / f"broker_connection_check_{ts}.md").write_text(
        render_md(result, cfg), encoding="utf-8")
    (out / f"broker_connection_check_{ts}.json").write_text(
        render_json(result), encoding="utf-8")
    print(f"result: {'PASS' if result.passed else 'FAIL'}"
          + (" (HARD FAIL)" if result.hard_fail else "")
          + f" | account={result.account_id} type={result.account_type}"
          + f" | report: {out}/broker_connection_check_{ts}.md")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
