# MLERankCumulative — v1.0.0

**Run ID:** `243c07cc-5466-4236-b7b2-178115da1687`
**Datum spuštění:** 2026-06-30 08:03:30 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Median 30D alpha vs SPY klesa s rostoucim kumulativnim MLE rank thresholdem (TOP10 > TOP20 > TOP30 > TOP50 > TOP70 > TOP100), protoze sirsi vyber zahrnuje slabsi kandidaty (viz MLERankBuckets_v1 discrete profil).

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0007 doplnek: MLE Rank Cumulative Thresholds

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 21900 |
| n_eligible_days | 219 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| n_transitions_monotonic | 5 |
| n_transitions_total | 5 |
| pct_monotonic | 1.0 |
| h_supported | True |
| last_positive_alpha_threshold | 30 |
| TOP10_n | 2190 |
| TOP10_median_alpha_30d | 1.108 |
| TOP10_wr_alpha_30d | 0.5484 |
| TOP20_n | 4380 |
| TOP20_median_alpha_30d | 0.6221 |
| TOP20_wr_alpha_30d | 0.5258 |
| TOP30_n | 6570 |
| TOP30_median_alpha_30d | 0.233 |
| TOP30_wr_alpha_30d | 0.5102 |
| TOP50_n | 10950 |
| TOP50_median_alpha_30d | -0.0893 |
| TOP50_wr_alpha_30d | 0.4965 |
| TOP70_n | 15330 |
| TOP70_median_alpha_30d | -0.4265 |
| TOP70_wr_alpha_30d | 0.482 |
| TOP100_n | 21900 |
| TOP100_median_alpha_30d | -0.6971 |
| TOP100_wr_alpha_30d | 0.467 |

## Tabulky

- `tables/cumulative_stats.csv`

## Summary

MLE Rank Cumulative Thresholds
Question: How does edge change as selection widens (rank <= N)?

Metrika: alpha vs SPY  |  Primary window: 30D

Profil (kumulativni, ne discrete buckety):
  TOP10    alpha=+1.11%  WR=54.8%  N=2190
  TOP20    alpha=+0.62%  WR=52.6%  N=4380
  TOP30    alpha=+0.23%  WR=51.0%  N=6570
  TOP50    alpha=-0.09%  WR=49.6%  N=10950
  TOP70    alpha=-0.43%  WR=48.2%  N=15330
  TOP100   alpha=-0.70%  WR=46.7%  N=21900

Monotonni prechody: 5/5 (100%)
Posledni TOP-N s kladnou alfou: TOP30

H: SUPPORTED

N celkem (TOP100): 21,900 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `fa22235943b7c4af3aba56fc7277af4a0b77f31fcda1e3f7476b259fe3f8ab2d`
