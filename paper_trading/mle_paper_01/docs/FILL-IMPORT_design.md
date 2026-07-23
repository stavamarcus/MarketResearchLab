# Fill Import (broker executions -> ticket) - design specification v1.3

**v1.3 changes (final round):** canonical ticket provenance uses the planned
projection, ticket schema detection is all-five-or-none, and the P2 identity
flow drops the order_id fallback.

## v1.3 corrections

**1. Canonical ticket provenance.** `ticket_sha256_before_import` does NOT enter
the canonical hash: the first import writes the fill columns, so a second run
over the same dump would otherwise produce a different hash. Canonical content
uses `ticket_planned_projection_sha256`, computed only from the planned columns
(`target_date, ticker, conid, side, planned_quantity, order_timing,
order_type`), which are immutable across imports. The full
`ticket_sha256_before_import` is kept in `non_canonical_metadata`.

**2. Ticket schema detection.** All five P2 columns present -> `P2`. None
present -> `LEGACY`. A partial header -> `INVALID_TICKET_SCHEMA`, apply blocked.
A half-migrated header means someone broke the schema; guessing which column is
missing is worse than refusing.

**3. Identity flow.** For a P2 ticket there is no `order_id` fallback:

    P2 broker fill    -> ibkr:<broker_account>:perm:<perm_id>
    P2 manual recovery-> fill:<fill_id>
    otherwise         -> INVALID_FILL_IDENTITY, apply blocked

`order_id` remains a stored broker fact. The `order_id` fallback and the legacy
hash survive only for pre-P2 tickets - and the legacy branch keeps its original
`order:<id>` / `hash:...` form, unscoped, so keys already written to the journal
still match.

---

# (v1.2 body follows)

**Status:** PROPOSAL rev.3 - awaiting approval to implement. Nothing implemented.
**Phase:** P2. Depends on P1 (whole-ticket verdict, FILL-RECONCILIATION_design.md 6b).
**Date:** 2026-07-22
**Changes in v1.2:** second-round decisions 1-11 incorporated.

Layer contract (decision 11):

    importer:        dump + plan + ticket        -> artifact + ticket
    reconciliation:  ticket + state + journal    -> VALIDATE / ALREADY_APPLIED / APPLY

No journal dependency in the importer. No broker dependency in reconciliation.
No state or journal write from the importer.

---

## 0. BLOCKING FINDING - no machine-readable source for the plan price fields

Decision 5 asks for the authoritative plan artifact carrying `max_price_for_qty`
and the plan reference price. Searched every artifact:

| Artifact | Carries them? |
|---|---|
| `orders_plan_<date>.csv` | **no** - columns are `date, ticker, conid, action, quantity, target_value, reason, price_source`; `quantity` is empty |
| `manual_order_ticket_<date>.csv` | **no** (correct - decision 5 says it must not) |
| journal `CAPITAL_FEASIBILITY` event | **no** per-ticker prices - only aggregates (`min_operational_capital_estimate`, `estimated_remaining_cash_after_buys`, `estimated_rounding_drag`, `no_ref_price` as a name list) |
| `manual_report_<date>.md` | **yes - and it is the only place** |

The only source is a **markdown presentation table** produced by
`manual_report.py`. That is a rendering, not a data artifact, and the importer
must not parse it: a column reorder or a formatting change would silently alter
computed deviations.

A second problem: journal events for 2026-07-22 do not exist. The 07-22 run was
filed under business date 2026-07-21 (D), so nothing can be recovered by date
lookup either.

**Proposal.** Treat the two fields as **optional importer inputs**:

- The authoritative plan artifact is `orders_plan_<date>.csv`, referenced by
  `plan_path_relative` + `plan_sha256`. It supplies ticker, conid, action,
  target_value, reason, price_source.
- `max_price_for_qty` and `ref_price` are read only if a machine-readable source
  is configured. None exists today, so the artifact records
  `plan_reference_source: "UNAVAILABLE"` and both `PRICE_CAP_EXCEEDED` and
  `PLAN_PRICE_DEVIATION` are simply **not computed**. Absence is recorded, never
  guessed.
- For the 2026-07-22 cycle only, the values may be supplied as an **explicit
  operator assertion** (same category as decision 10's terminality assertion),
  recorded with `plan_reference_source: "OPERATOR_ASSERTION"` and the values
  inline. The report table values are already known: FANG cap 199.8501, fill
  202.81.

Making the Trade Plan generator emit these fields machine-readably is the
correct long-term fix, but it is a `daily_runner` / `manual_report.py` change,
outside P2, and it cannot retroactively produce them for 07-22.

**Related:** `planned_quantity` also does not live in the plan - the plan's
`quantity` column is empty and the value exists only in the **ticket**
(`planned_quantity = 53` for PYPL). The importer therefore reads
`planned_quantity` from the ticket it is about to write, never modifies it, and
covers the audit gap via `ticket_sha256_before_import`.

---

## 1. Final ticket schema

Planned columns - never touched by the importer:

    target_date, ticker, conid, side, planned_quantity, order_timing, order_type

Fill columns written by the importer:

| Column | Source | Notes |
|---|---|---|
| `actual_quantity` | sum of `shares` in the permId group | Decimal |
| `actual_fill_price` | `gross_notional / actual_quantity` | **derived**, full precision |
| `gross_notional` | exact sum of `shares * price` per execution | Decimal |
| `commission_fees` | exact sum of per-execId commissions | Decimal, summed before rounding |
| `timestamp` | `last_fill_timestamp` | both times kept in the artifact |
| `status` | `filled` / `partial` / `cancelled` / `rejected` / `not_submitted` | `partial` only when `PARTIAL_FINAL` |
| `broker_account` | dump account, cross-checked per execution | **new** |
| `perm_id` | IBKR `permId` | **new** |
| `order_id` | real IBKR `orderId` | stored as a broker fact; `0` is kept, never an identity |
| `fill_id` | UUID, manual recovery only | **new** |
| `execution_ids` | `;`-separated `execId`, canonical order | **new** |

**Five new columns** (decision 3): `broker_account`, `perm_id`, `fill_id`,
`execution_ids`, `gross_notional`.

`import_state` is **removed** (decision 2). The importer neither determines nor
records `already_applied`; that state is derived by reconciliation from the
journal, and the importer never reads the journal at all.

---

## 2. Identity flow - no legacy fallback for P2 tickets

### 2.1 Ticket generation detection

A ticket is a **P2 ticket** when its header contains any of the five new
columns. No extra marker column is needed.

### 2.2 Key construction

```python
def fill_key(row, target_date, p2_ticket: bool):
    acct = (row.broker_account or "").strip()

    if acct and _valid_id(row.perm_id):
        return f"ibkr:{acct}:perm:{row.perm_id}"

    if row.fill_id:
        return f"fill:{row.fill_id}"

    if acct and _valid_id(row.order_id):
        return f"ibkr:{acct}:order:{row.order_id}"

    if p2_ticket:
        raise InvalidFillIdentity(row)          # -> INVALID_FILL_IDENTITY
    return "hash:" + sha256(...)                # pre-P2 tickets only
```

```python
def _valid_id(v):
    s = str(v).strip()
    if not s:
        return False
    try:
        return int(s) != 0
    except ValueError:
        return False
```

Decision 4: a P2 ticket must never reach the legacy hash. A broker row must
carry `broker_account` + a valid `perm_id`; a manual recovery row must carry
`fill_id`. Otherwise the row is `INVALID_FILL_IDENTITY` and **APPLY is blocked**.
The legacy hash survives only for tickets written before P2.

`order_id = 0` is preserved in the ticket as a broker fact and is excluded from
every identity by `_valid_id`. Without that guard today's data produces
`order:0` ten times: one row applies, nine are classified as duplicates and
silently skipped.

### 2.3 fill_id lifecycle

Generated once at manual entry as `uuid4()`, written to ticket and artifact,
read and reused on every later run. Never regenerated, never placed in
`order_id`. A manual row whose `fill_id` has gone missing is an error, not a cue
to mint a new one.

---

## 3. Cash math (decision 1)

```
BUY :  cash_delta = -(gross_notional + commission_fees)
SELL:  cash_delta =   gross_notional - commission_fees
```

`quantity`, `price`, `gross_notional` and `commission_fees` stay `Decimal`
through ticket parsing and through the whole of reconciliation. Values are built
with `Decimal(str(v))`, never `Decimal(float)`.

The Decimal-to-float boundary is crossed at exactly two points, both at the
PortfolioState write:

1. `Position(shares=..., entry_price=...)` - float-typed dataclass
2. `state.cash` / `state.equity`

Everything upstream is exact. Verified for 2026-07-22: gross_notional
28833.4800, commissions 10.0007, debit 28843.4807, resulting cash 1156.5193.

`actual_fill_price` is derived (`gross_notional / actual_quantity`) and is
written for readability, not used for cash math.

---

## 4. Normalized artifact

Path: `order_plans/<strategy>/<mode>/normalized_fills_<target_date>.json`

Provenance block (decision 5) - **relative paths only**, no machine-specific
absolute paths in canonical content:

```json
"source": {
  "dump_path_relative": "order_plans/mle_paper_01/paper_manual/broker_executions_2026-07-22_cid102_run2.json",
  "dump_sha256": "2dfe9fc3...",
  "plan_path_relative": "order_plans/mle_paper_01/paper_manual/orders_plan_2026-07-22.csv",
  "plan_sha256": "...",
  "ticket_path_relative": "order_plans/mle_paper_01/paper_manual/manual_order_ticket_2026-07-22.csv",
  "ticket_sha256_before_import": "...",
  "plan_reference_source": "UNAVAILABLE",
  "account": "DUQ199078"
}
```

Paths are relative to the `paper_trading` root. Absolute paths, if reported at
all, live outside canonical content.

**Journal independence (decision 6).** Canonical content is a pure function of
raw dump + Trade Plan + explicit operator assertions. It contains no
`already_applied`, no `import_state`, and nothing derived from the journal.
Those belong to the reconciliation report.

Monetary values are stored as strings to avoid JSON float round-tripping.

---

## 5. Canonical ordering (decision 7)

`sort_keys=True` orders object keys but leaves arrays in insertion order, so
array order is specified explicitly:

| Array | Sort key |
|---|---|
| `executions` (within a group) | `(timestamp_et, exec_id)` |
| `orders` (order groups) | plan row index, i.e. the order of `orders_plan_<date>.csv` |
| `execution_ids` | same canonical order as `executions` |
| `diagnostics` | `(code, plan_row_index, perm_id, exec_id)`, each missing component as an empty string |
| `unmatched_orders` | `(perm_id, first_fill_timestamp)` |
| `unmatched_plan_rows` | plan row index |

An unmatched broker group has no plan row index; those sort after all matched
groups, ordered by `(perm_id)`.

Canonical serialisation: `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=False`, monetary values as strings, `generated_at_utc` and
`canonical_sha256` removed. `canonical_sha256` is the SHA-256 of that byte
string.

---

## 6. Artifact conflict policy (decision 8)

| Situation | Action |
|---|---|
| artifact does not exist | create it |
| exists, same `canonical_sha256` | **no-op** - not rewritten, mtime untouched |
| exists, different `canonical_sha256` | `NORMALIZED_ARTIFACT_CONFLICT` - **stop**, previous artifact untouched |

On conflict the run stops by default. With `--conflict-artifact` a versioned
diagnostic copy is written to
`normalized_fills_<target_date>.conflict_<utc_timestamp>.json` and the run
**still stops**. The previous audit artifact is never overwritten and never
silently replaced.

---

## 7. Existing-ticket conflict detection (decision 9)

Conflict is judged on **broker facts only**:

    actual_quantity, gross_notional, commission_fees,
    broker_account, perm_id, execution_ids

Exact Decimal equality for the numeric fields, string equality for the rest.

`actual_fill_price` is a derived field and is **not** a source of identity or
conflict. It is recomputed as `gross_notional / actual_quantity`; a stored value
that disagrees with the recomputation is reported as a warning
(`DERIVED_FIELD_STALE`), not as a conflict.

Note the interaction with decision 2: since the importer no longer reads the
journal, it cannot know that a row was already applied. It therefore compares
against whatever the ticket holds and writes broker data into blank rows
unconditionally. Reconciliation is the layer that later recognises the key as
already applied and skips the second write. This is the correct split, and it
means a blank row belonging to an already-applied fill gets its audit fields
completed as a side effect of a normal import - which is the behaviour the
previous round asked for, now achieved without a journal dependency.

---

## 8. Partial terminality assertion (decision 10)

`PARTIAL_FINAL` requires all four fields, recorded in the artifact and in the
operator assertions block:

    terminality_asserted     = true
    terminality_source       = OPERATOR
    terminality_asserted_at_utc = <ISO 8601 UTC>
    terminality_reason       = <non-empty free text>

Without a non-empty `terminality_reason` the group stays `PARTIAL_UNRESOLVED`
and apply is blocked. The importer cannot infer terminality: execution records
do not carry it and the importer may not call TWS (decision 11), so it cannot
query open orders. Terminality is an operator assertion, never an inference.

Operator assertions are part of canonical content - they are an input, like the
dump and the plan, not a derived state.

---

## 9. Blocking vs warning

**Blocking** - artifact written with diagnostics, **ticket unchanged** (rule 12):

`AMBIGUOUS_MATCH`, `UNMATCHED_BROKER_ORDER`, `QUANTITY_OVER_PLAN`,
`SIDE_MISMATCH`, `TICKER_CONID_MISMATCH`, `FOREIGN_ACCOUNT`, `WRONG_SESSION`,
`CROSS_SESSION_ORDER`, `COMMISSION_PENDING` / `INCOMPLETE_IMPORT`,
`PARTIAL_UNRESOLVED`, `CONFLICTING_EXISTING_TICKET`, `DUPLICATE_EXEC_ID`,
`INVALID_FILL_IDENTITY`, `NORMALIZED_ARTIFACT_CONFLICT`.

**Warning** - import proceeds, ticket written, deviation recorded:

`PRICE_CAP_EXCEEDED`, `LATE_ENTRY`, `PLAN_PRICE_DEVIATION`,
`DERIVED_FIELD_STALE`. The first three are only computed when a plan reference
source is available (section 0).

**Passing:** `MATCHED`, `PARTIAL_FINAL`.
`ALREADY_APPLIED` is no longer an importer state - it belongs to reconciliation.

`commission = 0.0` is a real zero and does not block. `commission = null` is a
missing report and blocks. The two are distinct values and are never conflated.

Plan rows with no broker order stay **blank**; the importer never invents
`not_submitted`. P1 turns any blank row into `INCOMPLETE_TICKET`.

---

## 10. Session validation (decision 10, previous round)

Per execution, not per group:

1. every `execId` resolves to an ET session date
2. all must be identical, else `CROSS_SESSION_ORDER`
3. the common session must equal `target_date`, else `WRONG_SESSION`

`timestamp_et = null` is a hard error - a session is never assumed.

---

## 11. Tests

### Changed from v1.1

| Test | Change |
|---|---|
| `test_already_applied_*` | **removed** - importer no longer knows this state (decision 2) |
| `test_import_state_column` | **removed** - column not approved (decision 3) |
| `test_cash_delta_uses_gross_notional` | split into BUY and SELL variants (decision 1) |
| `test_legacy_ticket_without_new_columns` | narrowed - legacy hash only for pre-P2 tickets (decision 4) |
| `test_conflicting_existing_ticket_fails` | conflict judged on broker facts only, `actual_fill_price` excluded (decision 9) |

### New in v1.2

| Decision | Test | Expected |
|---|---|---|
| 1 | `test_cash_delta_buy` | `-(gross_notional + commission)` |
| 1 | `test_cash_delta_sell` | `gross_notional - commission` |
| 1 | `test_decimal_survives_ticket_parsing` | four fields are `Decimal` after parse |
| 1 | `test_decimal_survives_reconciliation` | no float until the state write |
| 1 | `test_float_conversion_only_at_state_write` | exactly two conversion points |
| 2 | `test_importer_never_reads_journal` | AST scan, no journal import, no read |
| 2 | `test_artifact_has_no_already_applied` | key absent from canonical content |
| 3 | `test_ticket_has_exactly_five_new_columns` | schema locked |
| 4 | `test_p2_ticket_never_uses_legacy_hash` | `INVALID_FILL_IDENTITY` raised |
| 4 | `test_broker_row_without_perm_id_blocks` | apply blocked |
| 4 | `test_manual_row_without_fill_id_blocks` | apply blocked |
| 4 | `test_order_id_zero_stored_but_not_identity` | value kept, key unaffected |
| 4 | `test_pre_p2_ticket_still_uses_hash` | backward compatibility |
| 5 | `test_artifact_provenance_complete` | six provenance fields present |
| 5 | `test_no_absolute_paths_in_canonical` | no drive letters, no `/home`, no `\\Users` |
| 5 | `test_plan_reference_unavailable_skips_deviations` | no cap or deviation computed, absence recorded |
| 5 | `test_plan_reference_operator_assertion` | values used, source recorded |
| 6 | `test_canonical_is_function_of_inputs_only` | journal changes do not alter the hash |
| 7 | `test_executions_sorted_by_time_then_id` | canonical order |
| 7 | `test_order_groups_follow_plan_row_order` | canonical order |
| 7 | `test_execution_ids_match_executions_order` | identical ordering |
| 7 | `test_diagnostics_stable_sort` | shuffled input, identical output |
| 8 | `test_artifact_same_hash_is_noop` | file not rewritten, mtime unchanged |
| 8 | `test_artifact_different_hash_conflicts` | `NORMALIZED_ARTIFACT_CONFLICT`, original untouched |
| 8 | `test_conflict_artifact_is_versioned` | versioned copy written, run still stops |
| 9 | `test_conflict_uses_broker_facts_only` | `actual_fill_price` alone does not trigger |
| 9 | `test_derived_price_stale_is_warning` | `DERIVED_FIELD_STALE` |
| 10 | `test_partial_final_requires_all_four_fields` | missing reason -> `PARTIAL_UNRESOLVED` |
| 10 | `test_terminality_assertion_in_canonical` | assertion is an input |
| 11 | `test_importer_never_calls_tws` | AST scan, no ibapi |
| 11 | `test_importer_never_writes_state_or_journal` | writes only artifact and ticket |
| 11 | `test_reconciliation_has_no_broker_dependency` | existing AST scan extended |

### Retained from v1.1

The seventeen architect edge cases, the ambiguity pair, session validation,
commission precision, planned-column immutability, DO-NOT-BUY safety, and the
end-to-end run against the real 2026-07-22 dump (12 executions -> 10 groups ->
10 rows, cash 1156.5193).

---

## 12. Files

### New

`mle_paper_01/fills/__init__.py`, `normalize.py`, `matcher.py`,
`ticket_writer.py`, `manual_entry.py`, `artifact.py` (canonical form, hashing,
conflict policy); `mle_paper_01/import_fills.py` (CLI); tests
`test_fills_normalize.py`, `test_fills_matcher.py`, `test_fills_ticket_writer.py`,
`test_fills_identity.py`, `test_fills_artifact.py`, `test_fills_real_dump.py`;
this document.

### Changed

| Path | Change |
|---|---|
| `mle_paper_01/reconciliation.py` | `FillRow`: `broker_account`, `perm_id`, `fill_id`, `execution_ids`, `gross_notional`, Decimal parsing; `fill_key()` per section 2; `apply_to_state()` cash math per section 3; `_fill_row()` fills `account_id` |
| `mle_paper_01/tests/test_reconciliation.py` | identity, Decimal, BUY/SELL cash delta |
| `launcher.py` | menu entry 3, renumbering, orchestration of dump + importer |
| `mle_paper_01/docs/DAILY-PAPER-MANUAL-RUNBOOK_v1.1.md` -> v1.2 | section 6 replaced |

`dump_broker_executions.py` unmodified.

---

## 13. Remaining decision

**Section 0** - the plan price fields. Choose one:

- **(a)** importer treats them as unavailable; `PRICE_CAP_EXCEEDED` and
  `PLAN_PRICE_DEVIATION` are not computed for 07-22, absence recorded
- **(b)** operator assertion supplies them for 07-22 only
- **(c)** a separate task extends the Trade Plan generator to emit them
  machine-readably, and P2 waits for it

This document is written for (a) with (b) available as an explicit input.
