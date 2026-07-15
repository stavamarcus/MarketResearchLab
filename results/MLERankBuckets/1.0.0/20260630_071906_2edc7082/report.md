# MLERankBuckets — v1.0.0

**Run ID:** `2edc7082-ec69-4c2e-b2c9-adc83db37747`
**Datum spuštění:** 2026-06-30 07:19:06 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Median 30D alpha vs SPY monotonne klesa s rostoucim MLE rank_10d bucketem (Elite > Strong > Good > Moderate > Watch > Weak > Tail).

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0007: MLE Rank Buckets kompletni profil 1-150

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 32850 |
| n_eligible_days | 219 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| n_transitions_monotonic | 5 |
| n_transitions_total | 6 |
| pct_monotonic | 0.8333 |
| h_supported | True |
| last_positive_alpha_bucket | Strong |
| Elite_n | 2190 |
| Elite_median_alpha_30d | 1.108 |
| Elite_wr_alpha_30d | 0.5484 |
| Strong_n | 2190 |
| Strong_median_alpha_30d | 0.0527 |
| Strong_wr_alpha_30d | 0.5032 |
| Good_n | 3285 |
| Good_median_alpha_30d | -0.6361 |
| Good_wr_alpha_30d | 0.4725 |
| Moderate_n | 3285 |
| Moderate_median_alpha_30d | -0.3625 |
| Moderate_wr_alpha_30d | 0.4816 |
| Watch_n | 4380 |
| Watch_median_alpha_30d | -1.2257 |
| Watch_wr_alpha_30d | 0.4457 |
| Weak_n | 6570 |
| Weak_median_alpha_30d | -1.2315 |
| Weak_wr_alpha_30d | 0.4321 |
| Tail_n | 10950 |
| Tail_median_alpha_30d | -1.2577 |
| Tail_wr_alpha_30d | 0.4321 |

## Tabulky

- `tables/bucket_stats.csv`

## Summary

MLE Rank Buckets — kompletni profil 1-150
Question: How fast does MLE rank information value decay?

Metrika: alpha vs SPY  |  Primary window: 30D

Profil:
  Elite      (  1-10 ) alpha=+1.11%  WR=54.8%  N=2190
  Strong     ( 11-20 ) alpha=+0.05%  WR=50.3%  N=2190
  Good       ( 21-35 ) alpha=-0.64%  WR=47.2%  N=3285
  Moderate   ( 36-50 ) alpha=-0.36%  WR=48.2%  N=3285
  Watch      ( 51-70 ) alpha=-1.23%  WR=44.6%  N=4380
  Weak       ( 71-100) alpha=-1.23%  WR=43.2%  N=6570
  Tail       (101-150) alpha=-1.26%  WR=43.2%  N=10950

Monotonni prechody: 5/6 (83%)
Posledni bucket s kladnou alfou: Strong

H (alespon 5/6 prechodu monotonnich): SUPPORTED

N celkem: 32,850 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `321441d9fc609574f1e92d4872b8c05b8567d458a86e98d11d90f7e01b862608`
