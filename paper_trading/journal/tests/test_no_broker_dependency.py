"""Static guard: the journal package must not import any broker /
order-execution machinery. Enforced by AST-scanning every module's
imports, so it holds regardless of runtime code paths.
"""
import ast
from pathlib import Path

FORBIDDEN = {
    "broker", "execution", "order_execution", "ib_insync", "ibapi",
    "ibkr", "tws", "order_router", "trading_runtime.broker",
}

PKG_ROOT = Path(__file__).resolve().parents[1]  # the journal/ package dir


def _imported_names(source: str):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_journal_does_not_import_broker_or_execution():
    py_files = [p for p in PKG_ROOT.rglob("*.py") if "tests" not in p.parts]
    assert py_files
    offenders = []
    for f in py_files:
        for name in _imported_names(f.read_text(encoding="utf-8")):
            head = name.split(".")[0]
            if head in FORBIDDEN or name in FORBIDDEN:
                offenders.append((f.name, name))
    assert not offenders, f"forbidden imports found: {offenders}"
