# MLE-RECON-02B — data06_only_ranked Diagnostics

## Souhrn

- total_data06_only_observations: 5549
- unique_tickers: 6
- count_by_reason: {'MDSM_insufficient_45d_window': 4352, 'MDSM_cache_gap': 1197}
- worsens_with_lookback: True
- insufficient_history_share (EXE/PSKY/Q/SNDK): 0.9941 (5516/5549)
- n_dates_affected: 168

## Count by lookback

- L1: 487
- L2: 490
- L3: 493
- L4: 496
- L5: 499
- L6: 502
- L7: 505
- L8: 508
- L9: 511
- L10: 514
- L20: 544

## Top affected tickers

- SNDK: 1703
- PSKY: 1703
- EXE: 1703
- Q: 407
- HON: 22
- XOM: 11

## Unique ticker list (sample)

['EXE', 'HON', 'PSKY', 'Q', 'SNDK', 'XOM']

## Cases sample (prvnich 50)

| date | lb | ticker | conid | reason | mdsm_range | data06_range |
|---|---|---|---|---|---|---|
| 2025-07-09 | 1 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 1 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 1 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 2 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 2 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 2 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 3 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 3 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 3 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 4 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 4 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 4 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 5 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 5 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 5 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 6 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 6 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 6 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 7 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 7 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 7 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 8 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 8 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 8 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 9 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 9 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 9 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 10 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 10 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 10 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-09 | 20 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-09 | 20 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-09 | 20 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 1 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 1 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-10 | 1 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 2 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 2 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-10 | 2 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 3 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 3 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-10 | 3 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 4 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 4 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-10 | 4 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 5 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 5 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |
| 2025-07-10 | 5 | EXE | 470458975 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2021-02-10..2026-07-02 |
| 2025-07-10 | 6 | SNDK | 760250490 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 2025-02-24..2026-07-02 |
| 2025-07-10 | 6 | PSKY | 804144296 | MDSM_insufficient_45d_window | 2025-12-15..2026-05-12 | 1997-12-31..2026-07-02 |

## Zaver (interpretace)

- pokud vetsina reason = MDSM_insufficient_45d_window / MDSM_missing_close_past / MDSM_cache_gap / MDSM_file_missing:
  MDSM cache NENI kompletni rank oracle -> rank recon proti MDSM
  cache je metodicky omezena.
- pokud reason = ticker_mapping_issue: bug v mapovani -> opravit.
- pokud koncentrace na EXE/PSKY/Q/SNDK: znama insufficient history.
- pokud sirsi mnozina: MDSM cache coverage limit obecne.

## Vyhrady

- reason klasifikace z MDSM cache serie v 45d okne.
- data06_only = rank v DATA-06 compute, ne v MDSM compute.
- 45d okno, engine z MLE.
