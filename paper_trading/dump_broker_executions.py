"""
dump_broker_executions.py -- P0 read-only dump broker exekuci (paper).

ROZSAH: pouze cteni. Skript NEZAPISUJE do state.json, journalu ani ticketu,
nevola reconcile a nezaklada/nemeni/nerusi zadny order.

Pouzite EClient metody (uplny vycet):
    connect / run / disconnect / reqManagedAccts / reqExecutions

Zamerne NEPOUZITE: placeOrder, cancelOrder, reqGlobalCancel, exerciseOptions,
reqOpenOrders, reqAllOpenOrders, reqAutoOpenOrders.

Zadny import z projektu -- pouze stdlib + ibapi.
"""

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.execution import ExecutionFilter

SCHEMA = "broker_execution_dump/1.0"
ET = ZoneInfo("America/New_York")
REQ_ID_EXEC = 9001

# IB posila neznamou hodnotu jako DBL_MAX
UNSET_THRESHOLD = 1e307

TIME_FORMATS = (
    "%Y%m%d %H:%M:%S",
    "%Y%m%d-%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y%m%d %H:%M",
)


def num(value):
    """Prevede na float; DBL_MAX sentinel a neparsovatelne hodnoty -> None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if abs(f) >= UNSET_THRESHOLD:
        return None
    return f


class ExecDumper(EWrapper, EClient):

    def __init__(self, expected_account, tws_tz_name):
        EClient.__init__(self, self)
        self.expected_account = expected_account
        self.tws_tz_name = tws_tz_name
        self.tws_tz = ZoneInfo(tws_tz_name)
        self.managed_accounts = []
        self.executions = {}          # execId -> dict
        self.commissions = {}         # execId -> dict
        self.exec_callback_count = 0  # kolik execDetails callbacku prislo celkem
        self.duplicate_exec_ids = []  # execId dorucene vickrat
        self.comm_callback_count = 0
        self.messages = []
        self.ready = threading.Event()
        self.accounts_ready = threading.Event()
        self.exec_end = threading.Event()

    # ---- lifecycle -------------------------------------------------

    def nextValidId(self, orderId):
        # Pouze signal, ze je spojeni pripravene. Hodnota se nikde nepouzije,
        # zadny order se nezaklada.
        self.ready.set()

    def managedAccounts(self, accountsList):
        self.managed_accounts = [a.strip() for a in accountsList.split(",") if a.strip()]
        self.accounts_ready.set()

    def error(self, *args):
        # Signatura error() se mezi verzemi ibapi lisi (10.30+ pridalo errorTime),
        # proto defenzivni *args misto pevnych parametru.
        parts = [str(a) for a in args]
        rec = {
            "raw": parts,
            "codes": [a for a in args if isinstance(a, int)],
            "messages": [a for a in args if isinstance(a, str)],
        }
        self.messages.append(rec)
        print("[IB] " + " | ".join(parts))

    # ---- executions ------------------------------------------------

    def _normalize_time(self, raw):
        """Vraci (iso_et, tz_assumed, tz_source). Raw se nikdy neprepisuje."""
        if not raw:
            return None, None, None
        s = str(raw).strip()
        tz_from_broker = None
        tz_label = None
        tokens = s.split()
        if len(tokens) >= 3:
            # Format je "YYYYMMDD HH:MM:SS <TZ>" -> posledni token je vzdy
            # oznaceni timezone. Odstranime ho i kdyz ho neumime rozlozit,
            # jinak by strptime selhal a cas by se ztratil uplne.
            tz_label = tokens[-1]
            s = " ".join(tokens[:-1])
            try:
                tz_from_broker = ZoneInfo(tz_label)
            except Exception:
                tz_from_broker = None
        s = " ".join(s.split())
        naive = None
        for fmt in TIME_FORMATS:
            try:
                naive = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if naive is None:
            return None, None, "unparsed"
        if tz_from_broker is not None:
            aware = naive.replace(tzinfo=tz_from_broker)
            return (aware.astimezone(ET).isoformat(), False,
                    "from_broker_string:" + tz_label)
        aware = naive.replace(tzinfo=self.tws_tz)
        source = "assumed:" + self.tws_tz_name
        if tz_label:
            # Broker timezone poslal, ale nejde ji rozlozit (chybi tzdata,
            # neznama zkratka). Cas si nechame, ale oznacime jako odhadnuty.
            source += " (nerozpoznana broker tz: %s)" % tz_label
        return aware.astimezone(ET).isoformat(), True, source

    def execDetails(self, reqId, contract, execution):
        self.exec_callback_count += 1
        if execution.execId in self.executions:
            self.duplicate_exec_ids.append(execution.execId)
        iso_et, assumed, tz_source = self._normalize_time(execution.time)
        self.executions[execution.execId] = {
            "account": execution.acctNumber,
            "symbol": contract.symbol,
            "conid": contract.conId,
            "secType": contract.secType,
            "currency": contract.currency,
            "exchange": execution.exchange,
            "side": execution.side,
            "shares": num(execution.shares),
            "price": num(execution.price),
            "avgPrice": num(execution.avgPrice),
            "cumQty": num(execution.cumQty),
            "timestamp_raw": execution.time,
            "timestamp_et": iso_et,
            "timestamp_tz_assumed": assumed,
            "timestamp_tz_source": tz_source,
            "execId": execution.execId,
            "permId": execution.permId,
            "orderId": execution.orderId,
            "clientId": execution.clientId,
            "orderRef": execution.orderRef,
            "lastLiquidity": getattr(execution, "lastLiquidity", None),
        }

    def execDetailsEnd(self, reqId):
        self.exec_end.set()

    def _handle_commission(self, obj, callback_name):
        """Spolecny handler pro obe verze callbacku.

        ibapi < 10.30 : EWrapper.commissionReport(CommissionReport)
                        -> pole .commission
        ibapi >= 10.30: EWrapper.commissionAndFeesReport(CommissionAndFeesReport)
                        -> pole .commissionAndFees
        Prepisovat jen jeden z nich znamena, ze callback nikdy neprijde.
        """
        self.comm_callback_count += 1
        value = getattr(obj, "commission", None)
        if value is None:
            value = getattr(obj, "commissionAndFees", None)
        self.commissions[obj.execId] = {
            "commission": num(value),
            "commission_currency": getattr(obj, "currency", None),
            "realizedPNL": num(getattr(obj, "realizedPNL", None)),
            "commission_callback": callback_name,
        }

    def commissionReport(self, commissionReport):
        self._handle_commission(commissionReport, "commissionReport")

    def commissionAndFeesReport(self, commissionAndFeesReport):
        self._handle_commission(commissionAndFeesReport,
                                "commissionAndFeesReport")


def build_payload(app, args, filter_defaults):
    rows = []
    missing_commission = []
    foreign_account = 0
    for exec_id, rec in sorted(app.executions.items(),
                               key=lambda kv: (kv[1].get("timestamp_et") or "", kv[0])):
        merged = dict(rec)
        comm = app.commissions.get(exec_id)
        if comm is None:
            merged["commission"] = None
            merged["commission_currency"] = None
            merged["realizedPNL"] = None
            merged["commission_status"] = "PENDING_OR_MISSING"
            missing_commission.append(exec_id)
        else:
            merged.update(comm)
            merged["commission_status"] = "RECEIVED"
        merged["account_matches_expected"] = (
            merged.get("account") == args.expected_account)
        if not merged["account_matches_expected"]:
            foreign_account += 1
        rows.append(merged)

    # commission reporty, ke kterym neexistuje exekuce v tomto dumpu
    unmatched_commissions = sorted(
        set(app.commissions.keys()) - set(app.executions.keys()))

    # Popisny souhrn surovych dat. NEPOROVNAVA se s Trade Planem.
    summary = {}
    for r in rows:
        key = "%s|%s" % (r["symbol"], r["side"])
        s = summary.setdefault(key, {
            "symbol": r["symbol"], "side": r["side"], "conid": r["conid"],
            "execution_count": 0, "total_shares": 0.0, "notional": 0.0,
            "commission_sum": 0.0, "commission_missing": 0,
            "perm_ids": [], "order_ids": [],
        })
        s["execution_count"] += 1
        sh = r["shares"] or 0.0
        px = r["price"] or 0.0
        s["total_shares"] += sh
        s["notional"] += sh * px
        if r["commission"] is None:
            s["commission_missing"] += 1
        else:
            s["commission_sum"] += r["commission"]
        if r["permId"] not in s["perm_ids"]:
            s["perm_ids"].append(r["permId"])
        if r["orderId"] not in s["order_ids"]:
            s["order_ids"].append(r["orderId"])
    for s in summary.values():
        s["avg_price"] = round(s["notional"] / s["total_shares"], 6) \
            if s["total_shares"] else None
        s["split_into_partials"] = s["execution_count"] > 1

    now_utc = datetime.now(timezone.utc)
    return {
        "schema": SCHEMA,
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_et": now_utc.astimezone(ET).isoformat(),
        "connection": {
            "host": args.host,
            "port": args.port,
            "client_id": args.client_id,
            "expected_account": args.expected_account,
            "managed_accounts": app.managed_accounts,
            "tws_tz_arg": args.tws_tz,
        },
        "request": {
            "method": "reqExecutions",
            "req_id": REQ_ID_EXEC,
            "execution_filter_defaults": filter_defaults,
            "note": "ExecutionFilter ponechan v defaultu; clientId=0 znamena "
                    "v IB semantice bez filtru.",
        },
        "counts": {
            "execution_callbacks": app.exec_callback_count,
            "unique_exec_ids": len(app.executions),
            "duplicate_exec_id_callbacks": len(app.duplicate_exec_ids),
            "commission_callbacks": app.comm_callback_count,
            "commissions_matched": len(app.commissions) - len(unmatched_commissions),
            "exec_ids_without_commission": len(missing_commission),
            "commissions_without_execution": len(unmatched_commissions),
            "foreign_account_executions": foreign_account,
        },
        "duplicate_exec_ids": sorted(set(app.duplicate_exec_ids)),
        "exec_ids_without_commission": missing_commission,
        "commissions_without_execution": unmatched_commissions,
        "summary_by_symbol_side": sorted(summary.values(),
                                         key=lambda s: s["symbol"]),
        "executions": rows,
        "ib_messages": app.messages,
    }


def atomic_write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise SystemExit("Vystupni adresar neexistuje: " + directory)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def print_console_summary(payload):
    c = payload["counts"]
    conn = payload["connection"]
    print("")
    print("=" * 78)
    print("P0 DUMP -- SOUHRN")
    print("=" * 78)
    print("account (expected)        : %s" % conn["expected_account"])
    print("managed accounts (TWS)    : %s" % (conn["managed_accounts"] or "n/a"))
    print("client_id                 : %s" % conn["client_id"])
    print("execution callbacks       : %d" % c["execution_callbacks"])
    print("unique execIds            : %d" % c["unique_exec_ids"])
    print("duplicate execId callbacks: %d" % c["duplicate_exec_id_callbacks"])
    print("commission callbacks      : %d" % c["commission_callbacks"])
    print("execIds bez commission    : %d" % c["exec_ids_without_commission"])
    print("commission bez execution  : %d" % c["commissions_without_execution"])
    print("exekuce ciziho uctu       : %d" % c["foreign_account_executions"])
    print("")
    print("AGREGACE (raw broker data, NEporovnano s Trade Planem)")
    print("-" * 78)
    print("%-8s %-5s %6s %10s %12s %10s %s" % (
        "SYMBOL", "SIDE", "EXECS", "SHARES", "AVG PRICE", "COMM", "PARTIALS"))
    print("-" * 78)
    for s in payload["summary_by_symbol_side"]:
        comm = "n/a" if s["commission_missing"] == s["execution_count"] \
            else "%.2f" % s["commission_sum"]
        print("%-8s %-5s %6d %10.0f %12s %10s %s" % (
            s["symbol"], s["side"], s["execution_count"], s["total_shares"],
            ("%.4f" % s["avg_price"]) if s["avg_price"] is not None else "n/a",
            comm, "YES" if s["split_into_partials"] else "no"))
    print("-" * 78)
    tickers = sorted({s["symbol"] for s in payload["summary_by_symbol_side"]})
    print("tickery (%d): %s" % (len(tickers), ", ".join(tickers) or "zadne"))
    if payload["duplicate_exec_ids"]:
        print("DUPLICITNI execId: %s" % ", ".join(payload["duplicate_exec_ids"]))
    if payload["exec_ids_without_commission"]:
        print("execId bez commission: %s"
              % ", ".join(payload["exec_ids_without_commission"]))
    if payload["commissions_without_execution"]:
        print("commission bez execution: %s"
              % ", ".join(payload["commissions_without_execution"]))


def main():
    ap = argparse.ArgumentParser(description="Read-only dump broker exekuci (P0).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7497)
    ap.add_argument("--client-id", type=int, default=102)
    ap.add_argument("--expected-account", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tws-tz", default="America/New_York",
                    help="Timezone nastavena v TWS. Pouzije se jen kdyz ji "
                         "broker neposle ve stringu.")
    ap.add_argument("--connect-timeout", type=float, default=15.0)
    ap.add_argument("--exec-timeout", type=float, default=45.0)
    ap.add_argument("--commission-timeout", type=float, default=60.0)
    ap.add_argument("--overwrite", action="store_true",
                    help="Povolit prepsani existujiciho vystupniho souboru.")
    args = ap.parse_args()

    if args.expected_account.upper().startswith("U"):
        raise SystemExit("HARD FAIL: expected-account vypada jako LIVE ucet. Konec.")

    if args.out is None:
        stamp = datetime.now(ET).strftime("%Y-%m-%d")
        args.out = os.path.join(
            "order_plans", "mle_paper_01", "paper_manual",
            "broker_executions_%s_cid%d.json" % (stamp, args.client_id))

    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(
            "STOP: vystupni soubor uz existuje: %s\n"
            "Predchozi dump by se prepsal. Pouzij --out s jinym jmenem, "
            "nebo vedome --overwrite." % os.path.abspath(args.out))

    app = ExecDumper(args.expected_account, args.tws_tz)
    app.connect(args.host, args.port, args.client_id)
    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()

    try:
        if not app.ready.wait(args.connect_timeout):
            raise SystemExit(
                "HARD FAIL: spojeni s TWS se nenavazalo (port %d, client_id %d)."
                % (args.port, args.client_id))

        app.reqManagedAccts()
        app.accounts_ready.wait(10.0)

        if app.managed_accounts:
            live = [a for a in app.managed_accounts if a.upper().startswith("U")]
            if live:
                raise SystemExit("HARD FAIL: TWS hlasi LIVE ucty %s. Konec." % live)
            if args.expected_account not in app.managed_accounts:
                raise SystemExit("HARD FAIL: ocekavany ucet %s neni mezi %s."
                                 % (args.expected_account, app.managed_accounts))
            print("Account OK: %s" % args.expected_account)
        else:
            print("VAROVANI: reqManagedAccts nevratil zadny ucet. Pokracuji, "
                  "ale account se overi az proti poli acctNumber v exekucich.")

        exec_filter = ExecutionFilter()
        filter_defaults = {
            "clientId": getattr(exec_filter, "clientId", None),
            "acctCode": getattr(exec_filter, "acctCode", None),
            "time": getattr(exec_filter, "time", None),
        }
        print("ExecutionFilter defaults: %s" % filter_defaults)

        app.reqExecutions(REQ_ID_EXEC, exec_filter)
        if not app.exec_end.wait(args.exec_timeout):
            print("VAROVANI: execDetailsEnd nedorazil do %.0fs. "
                  "Dump muze byt neuplny." % args.exec_timeout)

        deadline = time.time() + args.commission_timeout
        while time.time() < deadline and len(app.commissions) < len(app.executions):
            time.sleep(0.25)

        payload = build_payload(app, args, filter_defaults)
    finally:
        app.disconnect()

    atomic_write_json(args.out, payload)
    print_console_summary(payload)
    print("")
    print("Dump zapsan: %s" % os.path.abspath(args.out))

    if payload["counts"]["unique_exec_ids"] == 0:
        print("")
        print("ZERO EXECUTIONS pro client_id=%d." % args.client_id)
        print("TOTO NEZNAMENA, ZE NEBYLY OBCHODY. Rucni TWS ordery patri client_id 0.")
        print("Spust znovu s --client-id 0.")
        return 4
    if payload["counts"]["foreign_account_executions"] > 0:
        print("VAROVANI: dump obsahuje exekuce jineho uctu nez %s."
              % args.expected_account)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
