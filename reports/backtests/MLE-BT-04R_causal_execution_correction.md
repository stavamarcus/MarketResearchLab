# MLE-BT-04R — Causal Execution Correction (AUDIT)

Oprava MLE-BT-04: (D1) regime lookahead, (D2) cash/slot chronologie, (D3) regime data handling. ZADNA zmena strategie.

Sim: 2021-07-01..2026-07-02 (1256 dni), cost 15 bps, pandas 3.0.3

**current 503 universe, survivorship bias (dedeno z BT-04, tato oprava neresi).**

## Srovnani OLD (BT-04) vs NEW (BT-04R)

| variant | run | return% | CAGR% | maxDD% | sharpe | calmar | trades | avg_expo |
|---|---|---|---|---|---|---|---|---|
| baseline_hold10 | OLD | 325.796 | 33.765 | -36.583 | 1.034 | 8.906 | 1260 | 0.999 |
| baseline_hold10 | NEW | 464.351 | 41.55 | -44.485 | 1.267 | 10.438 | 1150 | 0.908 |
| regime200_hold10 | OLD | 375.283 | 36.751 | -25.431 | 1.197 | 14.757 | 1090 | 0.864 |
| regime200_hold10 | NEW | 337.652 | 34.504 | -32.7 | 1.182 | 10.326 | 990 | 0.787 |

## Regime rozdily

- D1 timing shift (ok[D] vs ok[D+1]) — dnu s rozdilnym gate: 54
  - dny: ['2022-01-21', '2022-01-24', '2022-01-25', '2022-01-31', '2022-02-14', '2022-02-15', '2022-02-17', '2022-03-17', '2022-04-12', '2022-04-13', '2022-04-22', '2022-08-11', '2022-08-22', '2022-08-25', '2022-08-26', '2022-11-10', '2022-12-16', '2022-12-21', '2022-12-22', '2022-12-29', '2022-12-30', '2023-01-04', '2023-01-05', '2023-01-06', '2023-03-13', '2023-03-14', '2023-03-15', '2023-03-16', '2023-03-17', '2023-03-20', '2023-03-22', '2023-03-24', '2023-09-26', '2023-09-28', '2023-10-02', '2023-10-10', '2023-10-12', '2023-10-16', '2023-10-18', '2023-11-03', '2023-11-06', '2023-11-14', '2025-03-11', '2025-03-17', '2025-03-18', '2025-03-19', '2025-03-21', '2025-03-24', '2025-03-28', '2025-04-02', '2025-04-03', '2025-05-12', '2026-03-27', '2026-03-31']
- D3 data handling (old vs new regime serie) — rozdilnych dnu: 0
  - dny: []
- valid constituents: {'min': 492, 'max': 503, 'median': 498.0, 'days_below_400': 0}

## baseline_hold10 — diagnostika NEW

- buys: 1150
- dny se signalem zablokovane regime gate (OFF): 0
- dny s plnym portfoliem vc. pending-exit pozic: 114
- kandidati nekoupitelni kvuli pending exitu tehoz dne: 90
- buys orezane dostupnym cashem (< 10% target): 115
- trade diff old/new: {'old_trades': 1260, 'new_trades': 1150, 'only_in_old': 1140, 'only_in_new': 1030}

### baseline_hold10 — rocni rozklad NEW

| rok | ret% | maxDD% | sharpe | trades | regime_on% |
|---|---|---|---|---|---|
| 2021 | 16.295 | -10.045 | 1.505 | 110 | 1.0 |
| 2022 | -8.792 | -24.947 | -0.108 | 230 | 0.339 |
| 2023 | 132.296 | -23.913 | 2.992 | 230 | 0.86 |
| 2024 | 51.217 | -15.731 | 1.722 | 230 | 1.0 |
| 2025 | -2.858 | -42.2 | 0.09 | 220 | 0.86 |
| 2026 | 63.984 | -15.222 | 2.758 | 130 | 0.984 |

## regime200_hold10 — diagnostika NEW

- buys: 990
- dny se signalem zablokovane regime gate (OFF): 238
- dny s plnym portfoliem vc. pending-exit pozic: 92
- kandidati nekoupitelni kvuli pending exitu tehoz dne: 87
- buys orezane dostupnym cashem (< 10% target): 99
- trade diff old/new: {'old_trades': 1090, 'new_trades': 990, 'only_in_old': 1010, 'only_in_new': 910}

### regime200_hold10 — rocni rozklad NEW

| rok | ret% | maxDD% | sharpe | trades | regime_on% |
|---|---|---|---|---|---|
| 2021 | 16.295 | -10.045 | 1.505 | 110 | 1.0 |
| 2022 | -25.402 | -28.439 | -1.291 | 110 | 0.339 |
| 2023 | 73.202 | -19.54 | 2.06 | 220 | 0.86 |
| 2024 | 43.22 | -17.267 | 1.453 | 230 | 1.0 |
| 2025 | 40.489 | -25.992 | 1.391 | 200 | 0.86 |
| 2026 | 47.637 | -16.362 | 1.981 | 120 | 0.984 |

## Vyhrady

- Auditni oprava, NE optimalizace. Strategie beze zmeny.
- OLD beh = import puvodniho bt04.run + bt04.build_regime (soubor BT-04 nezmenen).
- Signaly sdilene obema behy -> rozdil = exekuce + regime.
- SURVIVORSHIP: current 503 universe.
- Nuceny exit na konci dat zachovan (srovnatelnost trades).
