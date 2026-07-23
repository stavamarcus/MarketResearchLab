"""Import states. Blocking states leave the ticket untouched (rule 12)."""
from dataclasses import dataclass, field
from typing import List, Optional


# --- broker order group states -------------------------------------------
MATCHED = "MATCHED"
PARTIAL_FINAL = "PARTIAL_FINAL"

# --- blocking ------------------------------------------------------------
AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
UNMATCHED_BROKER_ORDER = "UNMATCHED_BROKER_ORDER"
QUANTITY_OVER_PLAN = "QUANTITY_OVER_PLAN"
SIDE_MISMATCH = "SIDE_MISMATCH"
TICKER_CONID_MISMATCH = "TICKER_CONID_MISMATCH"
FOREIGN_ACCOUNT = "FOREIGN_ACCOUNT"
WRONG_SESSION = "WRONG_SESSION"
CROSS_SESSION_ORDER = "CROSS_SESSION_ORDER"
COMMISSION_PENDING = "COMMISSION_PENDING"
INCOMPLETE_IMPORT = "INCOMPLETE_IMPORT"
PARTIAL_UNRESOLVED = "PARTIAL_UNRESOLVED"
CONFLICTING_EXISTING_TICKET = "CONFLICTING_EXISTING_TICKET"
DUPLICATE_EXEC_ID = "DUPLICATE_EXEC_ID"
INVALID_FILL_IDENTITY = "INVALID_FILL_IDENTITY"
NORMALIZED_ARTIFACT_CONFLICT = "NORMALIZED_ARTIFACT_CONFLICT"
GROUP_INCONSISTENT = "GROUP_INCONSISTENT"
PLAN_TICKET_QUANTITY_MISMATCH = "PLAN_TICKET_QUANTITY_MISMATCH"
PLAN_ROW_MISSING_IN_TICKET = "PLAN_ROW_MISSING_IN_TICKET"
TICKET_ROW_NOT_IN_PLAN = "TICKET_ROW_NOT_IN_PLAN"
DUPLICATE_PLAN_ROW = "DUPLICATE_PLAN_ROW"
DUPLICATE_TICKET_ROW = "DUPLICATE_TICKET_ROW"

BLOCKING = frozenset({
    AMBIGUOUS_MATCH, UNMATCHED_BROKER_ORDER, QUANTITY_OVER_PLAN,
    SIDE_MISMATCH, TICKER_CONID_MISMATCH, FOREIGN_ACCOUNT, WRONG_SESSION,
    CROSS_SESSION_ORDER, COMMISSION_PENDING, INCOMPLETE_IMPORT,
    PARTIAL_UNRESOLVED, CONFLICTING_EXISTING_TICKET, DUPLICATE_EXEC_ID,
    INVALID_FILL_IDENTITY, NORMALIZED_ARTIFACT_CONFLICT, GROUP_INCONSISTENT,
    PLAN_TICKET_QUANTITY_MISMATCH, PLAN_ROW_MISSING_IN_TICKET,
    TICKET_ROW_NOT_IN_PLAN, DUPLICATE_PLAN_ROW, DUPLICATE_TICKET_ROW,
})

# --- warning (import proceeds) -------------------------------------------
PRICE_CAP_EXCEEDED = "PRICE_CAP_EXCEEDED"
LATE_ENTRY = "LATE_ENTRY"
PLAN_PRICE_DEVIATION = "PLAN_PRICE_DEVIATION"
DERIVED_FIELD_STALE = "DERIVED_FIELD_STALE"
MISSING_REF_PRICE = "MISSING_REF_PRICE"
MISSING_MAX_PRICE_FOR_QTY = "MISSING_MAX_PRICE_FOR_QTY"

WARNING = frozenset({PRICE_CAP_EXCEEDED, LATE_ENTRY, PLAN_PRICE_DEVIATION,
                     DERIVED_FIELD_STALE, MISSING_REF_PRICE,
                     MISSING_MAX_PRICE_FOR_QTY})

# Uplnost strojove citelne plan reference. Zdroj a uplnost jsou dve ruzne
# veci: plan muze mit nove sloupce, a presto u nekterych radku hodnotu
# nemit. Chybejici hodnota nesmi zablokovat vypocet u radku, kde je.
COMPLETENESS_FULL = "FULL"
COMPLETENESS_PARTIAL = "PARTIAL"
COMPLETENESS_NONE = "NONE"

# --- plan row states ------------------------------------------------------
FILLED = "FILLED"
PARTIAL = "PARTIAL"
MISSING = "MISSING"


class ImportError_(Exception):
    """Blocking import condition. Carries the diagnostics for the artifact."""

    def __init__(self, code: str, message: str, **context):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.context = context


@dataclass
class Diagnostic:
    code: str
    message: str
    plan_row_index: Optional[int] = None
    perm_id: str = ""
    exec_id: str = ""

    def sort_key(self):
        # decision 7: fixed, stable ordering; missing parts as empty string
        return (self.code,
                "" if self.plan_row_index is None else f"{self.plan_row_index:06d}",
                self.perm_id, self.exec_id)

    def to_dict(self):
        return {"code": self.code, "message": self.message,
                "plan_row_index": self.plan_row_index,
                "perm_id": self.perm_id, "exec_id": self.exec_id}


@dataclass
class OrderGroupState:
    perm_id: str
    state: str
    plan_row_index: Optional[int] = None
    diagnostics: List[Diagnostic] = field(default_factory=list)


@dataclass
class PlanRowState:
    ticker: str
    state: str


@dataclass
class ImportResult:
    ok: bool
    artifact: dict
    diagnostics: List[Diagnostic] = field(default_factory=list)
    ticket_changes: List[dict] = field(default_factory=list)
