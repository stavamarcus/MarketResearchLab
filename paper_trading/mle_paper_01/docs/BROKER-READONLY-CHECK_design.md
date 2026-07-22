# Broker Read-Only / Paper Connection Check — design specification

Status: **APPROVED WITH PATCH (OQ-1: ibapi) — patches applied; implementing.** Architect
(2026-07-15): paper account in IBKR TWS is now functional. First broker-touching
component. **Read-only: no placeOrder / cancelOrder / modifyOrder, no execution,
no PortfolioState mutation.**

## 0. Purpose

Verify the system can safely connect to IBKR **Paper** TWS and **read** the real
account state (account id, paper/live, equity, cash, positions, open-orders
count). Output is a report only. This step does **not** yet wire the real state
into `PortfolioState` — that is a later step. It answers one question: *can we
connect to the right paper account and read it safely?*

## 1. Scope / non-goals

- **Read-only.** No order submission, cancellation, or modification. No execution
  logic. No `PortfolioState` change. No writing to the account.
- The only order-related call is **reading the open-orders count** (a read
  operation); never creating or touching an order.
- Not in this step: replacing `starting_equity` in the runner, reconciliation
  wiring, any trading. Those come after this check passes.

## 2. What it reads

- detected `account_id`
- account type — **paper vs live** (derived from the id prefix)
- net liquidation / **equity**
- **cash** (total cash / available funds)
- **positions** (symbol, conid, quantity, avg cost)
- **open orders count**
- **connection status** + metadata (host, port, client_id, server version,
  connect time)
- **timestamp** (UTC)
- **errors / warnings** surfaced during the check

## 3. Architecture — real library isolated behind an interface

The check logic must run fully **without a live connection** (all logic
unit-tested against a fake). Structure:

- **`BrokerReadOnly` interface** (Protocol) — only read methods:
  `connect(timeout)`, `account_summary()`, `positions()`,
  `open_orders_count()`, `connection_meta()`, `disconnect()`. **No order
  methods exist on the interface at all** — read-only is structural, not just
  by convention.
- **Real adapter** — thin wrapper over native **`ibapi`** (OQ-1: stay consistent
  with the existing IBKR/MDSM direction; no new broker library), implementing the
  interface. Isolated so the rest of the system imports only the read-only
  interface, never `ibapi` directly.
  **Even though `ibapi`'s `EClient` contains order-capable methods, the project
  adapter exposes only read methods, and tests / AST scan prove no
  order-submission / cancel / modify calls are used in this component.**
- **Fake adapter** — returns canned account/positions for tests (mismatch, live,
  timeout, empty, populated, parse cases).
- **Check + report** — pure logic over the interface: run the reads, apply the
  safety gates (§4), render the report (§6).

## 4. Safety gates

- **`expected_account_id` is mandatory** in config. If absent → FAIL (refuse to
  run blind).
- **Mismatch** — detected `account_id` != `expected_account_id` → **HARD FAIL**.
- **Live account detected** — detected id looks live (starts with `U`, not a
  paper `DU…`/`D…` prefix) → **HARD FAIL** (never touch a live account here).
- **Read-only assurance** — the adapter exposes no order methods (structural).
  The TWS "Read-Only API" toggle is not reliably reported back over the API, so
  if it cannot be confirmed programmatically the check emits a **WARNING** (not a
  hard fail) and relies on the structural guarantee + the operator having enabled
  it. (See OQ-3.)
- **Timeout** — connection/reads bounded by `timeout_seconds`; on timeout →
  FAIL with a clear message, never hang.
- Any exception during connect/read → captured, reported, non-zero exit; no
  partial state written anywhere.

## 5. Config

- `host` = `127.0.0.1`
- `port` = `7497` (paper TWS)
- `client_id` = a **separate** id for the read-only check (proposed `102`, so it
  never collides with the runner, OQ-2)
- `expected_account_id` = your paper account id (`DU…`) — **required**
- `mode` = `paper`
- `timeout_seconds` (proposed default 15)

A config file (e.g. `config/broker_readonly_paper.json`) plus CLI overrides.

## 6. Outputs

- `broker_connection_check_<timestamp>.md` — human-readable: PASS/FAIL, account
  id + paper/live verdict, equity/cash, positions table, open-orders count,
  connection metadata, warnings, errors.
- `broker_connection_check_<timestamp>.json` — same data, machine-readable, for
  audit / later wiring.

Both are audit artifacts; nothing else is written (no state, no journal in this
step — see OQ-6).

## 7. Placement

Proposed new subpackage `mle_paper_01/broker/`: `interface.py` (Protocol),
`ib_readonly.py` (real adapter), `fake.py` (test double), `check.py` (logic +
report), and a CLI `python -m mle_paper_01.broker_check`. Isolating broker code
in its own subpackage eases the later migration to `TradingRuntime` with a
separate live-guard layer. (Alternative: a single `mle_paper_01/broker_check.py`
— OQ-5.)

## 8. Tests (no live connection)

- Fake-adapter unit tests for the full check path.
- **Account mismatch** → HARD FAIL.
- **Live account detected** (`U…`) → HARD FAIL.
- **Missing `expected_account_id`** → FAIL.
- **Timeout** → FAIL, no hang.
- **Empty positions** → PASS, positions empty.
- **Positions present** → parsed correctly (symbol/conid/qty/avg cost).
- **Cash / equity parse** → numeric fields parsed from the account summary.
- **No order-submission methods used** — AST scan asserts `placeOrder`,
  `cancelOrder`, `modifyOrder`, `reqGlobalCancel` never appear in the broker
  modules; the interface exposes no order methods.
- Report renders PASS and FAIL variants; JSON matches MD.

## 9. OQ resolutions (architect 2026-07-15)

- **OQ-1** — use native **`ibapi`**, not `ib_async` (consistency with the IBKR/MDSM
  direction; fewer deps; same environment as the later execution layer). The
  `BrokerReadOnly` Protocol is unchanged; only the real adapter binds to `ibapi`.
- **OQ-2** — `client_id = 102` (separate from the runner). Approved.
- **OQ-3** — Read-Only API toggle unconfirmable → WARNING (not hard fail); the
  report states the operator-checklist message verbatim (§4).
- **OQ-4** — exact `expected_account_id` match required; live `U…` → HARD FAIL;
  paper prefix `DU` (only DU for now; no other prefixes added blind).
- **OQ-5** — `mle_paper_01/broker/` subpackage.
- **OQ-6** — read + report only; no `PortfolioState` mutation and no journal event
  in this step.
