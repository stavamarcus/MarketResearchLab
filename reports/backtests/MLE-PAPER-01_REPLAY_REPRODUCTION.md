# MLE-PAPER-01 — Replay Reproduction Report (Faze 1B)

**VERDICT: PASS**

Sim: 2021-07-01..2026-07-02 (1256 dni), pandas 3.0.3

| metrika | target (BT-04R) | replay | golden (in-process) |
|---|---|---|---|
| total_return_pct | 337.652 | 337.652 | 337.652 |
| cagr_pct | 34.504 | 34.504 | 34.504 |
| max_drawdown_pct | -32.7 | -32.7 | -32.7 |
| sharpe | 1.182 | 1.182 | 1.182 |
| trades | 990 | 990 | 990 |
| avg_exposure | 0.787 | 0.787 | 0.787 |

- sanity anchor (golden == publikovane): True
- equity identicka den-po-dni: True
- trades identicke: True (replay 990 / golden 990)
- warnings: 0

## Vyhrady

- Reprodukce = validace IMPLEMENTACE, ne strategie.
- Golden reference = import BT-04R (soubor nezmenen).
- Signaly/regime sdilene obema behy.
