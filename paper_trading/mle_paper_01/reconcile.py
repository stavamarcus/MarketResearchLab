"""reconcile.py — CLI entry point for manual fill reconciliation.

Thin wrapper so `python -m mle_paper_01.reconcile ...` works (spec §11).
All logic lives in reconciliation.py.
"""
import sys

from .reconciliation import main

if __name__ == "__main__":
    sys.exit(main())
