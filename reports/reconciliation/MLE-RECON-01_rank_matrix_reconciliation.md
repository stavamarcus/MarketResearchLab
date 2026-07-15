# MLE-RECON-01 — Rank Matrix Reconciliation (Cesta B)

## Verdikt: FAIL

Range: 2025-07-09 .. 2026-07-04
Dni: 250

## Metoda

- puvodni MLE compute_rank_matrix + Sharadar DATA-06 ceny
- universe: 503 active, poradi zachovano (tie-break reprodukce)
- lookbacks: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]

## Souhrn

- compared_cells: 1366717
- close_prices_loaded: 503
- close_prices_missing: 0 []

### Rank

- rank_exact: 100650
- rank_mismatch: 1266067
- gross_rank_mismatch_rate: 0.926356
- clean_rank_mismatch_rate: 0.918654
- expected_exception_rank_mismatches: 10527

### Return

- ret_exact (<=0.0001): 1332637
- ret_micro (<=0.01): 3258
- ret_mismatch (>0.01): 30822

### Gate (lookback 10, strategie rank_10d<=10)

- gate_rank10_exact: 8476
- gate_rank10_mismatch: 115771
- gate10_clean_mismatch (non-exception): 114810
- gate10_clean_mismatch_rate: 0.924046

## Expected exceptions (NWS/GOOG/FOX/BDX)

- FOX: rank_mismatch=2704 ret_mismatch=2724
- NWS: rank_mismatch=2712 ret_mismatch=2731
- GOOG: rank_mismatch=2519 ret_mismatch=2648
- BDX: rank_mismatch=2592 ret_mismatch=343

## Excluded (insufficient history, ve vypoctu, ne v porovnani)

- ['EXE', 'PSKY', 'Q', 'SNDK']

## Top gate10 non-exception mismatches

- 2026-06-24 DD L10: arch_rank=1 recon_rank=343 arch_ret=192.86 recon_ret=-2.38
- 2026-06-25 DD L10: arch_rank=1 recon_rank=254 arch_ret=192.86 recon_ret=1.94
- 2026-06-22 KLAC L10: arch_rank=497 recon_rank=6 arch_ret=-86.05 recon_ret=39.52
- 2026-06-12 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.75 recon_ret=32.45
- 2026-06-13 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.75 recon_ret=32.45
- 2026-06-15 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.78 recon_ret=32.17
- 2026-06-25 KLAC L10: arch_rank=497 recon_rank=19 arch_ret=-88.76 recon_ret=21.18
- 2026-06-18 KLAC L10: arch_rank=497 recon_rank=6 arch_ret=-87.82 recon_ret=21.8
- 2026-06-23 KLAC L10: arch_rank=497 recon_rank=9 arch_ret=-88.4 recon_ret=15.98
- 2026-06-16 KLAC L10: arch_rank=497 recon_rank=4 arch_ret=-86.78 recon_ret=16.04
- 2026-06-24 KLAC L10: arch_rank=497 recon_rank=20 arch_ret=-88.76 recon_ret=12.41
- 2026-06-17 KLAC L10: arch_rank=497 recon_rank=15 arch_ret=-88.77 recon_ret=12.34
- 2026-06-26 KLAC L10: arch_rank=493 recon_rank=223 arch_ret=-89.69 recon_ret=3.1
- 2026-06-27 KLAC L10: arch_rank=496 recon_rank=223 arch_ret=-89.69 recon_ret=3.1
- 2026-07-04 CRWD L10: arch_rank=497 recon_rank=32 arch_ret=-71.6 recon_ret=13.61
- 2025-11-13 DD L10: arch_rank=4 recon_rank=502 arch_ret=19.17 recon_ret=-50.17
- 2025-11-05 DD L10: arch_rank=13 recon_rank=502 arch_ret=18.9 recon_ret=-50.28
- 2025-11-12 DD L10: arch_rank=8 recon_rank=502 arch_ret=18.71 recon_ret=-50.35
- 2025-11-10 DD L10: arch_rank=9 recon_rank=502 arch_ret=18.25 recon_ret=-50.55
- 2025-11-11 DD L10: arch_rank=10 recon_rank=502 arch_ret=17.96 recon_ret=-50.67
- 2025-11-07 DD L10: arch_rank=10 recon_rank=502 arch_ret=17.47 recon_ret=-50.87
- 2025-11-14 DD L10: arch_rank=4 recon_rank=502 arch_ret=16.28 recon_ret=-51.37
- 2025-11-06 DD L10: arch_rank=14 recon_rank=502 arch_ret=15.15 recon_ret=-51.84
- 2025-11-04 DD L10: arch_rank=17 recon_rank=502 arch_ret=11.29 recon_ret=-53.46
- 2025-11-03 DD L10: arch_rank=121 recon_rank=502 arch_ret=2.48 recon_ret=-57.15
- 2026-06-30 HON L10: arch_rank=175 recon_rank=503 arch_ret=3.4 recon_ret=-50.77
- 2026-06-25 SMCI L10: arch_rank=491 recon_rank=101 arch_ret=-20.15 recon_ret=8.23
- 2026-06-25 TECH L10: arch_rank=51 recon_rank=6 arch_ret=8.22 recon_ret=34.67
- 2025-07-10 FTV L10: arch_rank=380 recon_rank=501 arch_ret=0.49 recon_ret=-24.29
- 2025-07-09 FTV L10: arch_rank=376 recon_rank=501 arch_ret=-0.47 recon_ret=-25.02

## Vyhrady

- tie-break: close_prices poradi = universe_csv poradi.
- EXE/PSKY/Q/SNDK: ve vypoctu, vyloucene z porovnani.
- NWS/GOOG/FOX/BDX: expected exceptions, pocitane zvlast.
- ret tolerance: exact<=0.0001, micro<=0.01, mismatch>0.01.
- gate: rank_10d exact + ret_10d exact/micro.
