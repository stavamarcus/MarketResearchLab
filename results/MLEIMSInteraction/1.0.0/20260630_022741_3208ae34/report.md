# MLEIMSInteraction — v1.0.0

**Run ID:** `3208ae34-0c6d-4fd4-b865-53f679cb5c4b`
**Datum spuštění:** 2026-06-30 02:27:41 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

MLE TOP20 akcie s IMS score >= 90 (ELITE) dosahuji vyssi median 30D alpha vs SPY nez MLE TOP20 samotne nebo IMS samotne.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0002: MLE x IMS Signal Interaction

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 7446 |
| n_eligible_days | 219 |
| mle_rank_max | 20 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| mle_only_median_alpha | 1.4344 |
| ims_only_median_alpha | -0.7289 |
| mle_ims_90_94_median_alpha | 0.4591 |
| mle_ims_80_89_median_alpha | 0.043 |
| mle_ims_70_79_median_alpha | 0.1946 |
| h001_supported | False |
| h002_supported | False |
| h003_supported | False |
| MLE_ONLY_n | 2061 |
| MLE_ONLY_median_alpha_30d | 1.4344 |
| MLE_ONLY_wr_alpha_30d | 0.5454 |
| IMS_ONLY_n | 3066 |
| IMS_ONLY_median_alpha_30d | -0.7289 |
| IMS_ONLY_wr_alpha_30d | 0.4609 |
| MLE_IMS_70_79_n | 907 |
| MLE_IMS_70_79_median_alpha_30d | 0.1946 |
| MLE_IMS_70_79_wr_alpha_30d | 0.5105 |
| MLE_IMS_80_89_n | 1201 |
| MLE_IMS_80_89_median_alpha_30d | 0.043 |
| MLE_IMS_80_89_wr_alpha_30d | 0.5037 |
| MLE_IMS_90_94_n | 211 |
| MLE_IMS_90_94_median_alpha_30d | 0.4591 |
| MLE_IMS_90_94_wr_alpha_30d | 0.5261 |

## Tabulky

- `tables/group_stats.csv`

## Summary

MLE x IMS Signal Interaction
Question: Does MLE+IMS combination beat each module alone?

MLE: rank_10d <= 20  |  Metrika: alpha vs SPY  |  Window: 30D

Skupiny:
  MLE_ONLY         alpha=+1.43%  WR=54.5%  N=2061
  IMS_ONLY         alpha=-0.73%  WR=46.1%  N=3066
  MLE+IMS_70-79    alpha=+0.19%  WR=51.0%  N=907
  MLE+IMS_80-89    alpha=+0.04%  WR=50.4%  N=1201
  MLE+IMS_90-94    alpha=+0.46%  WR=52.6%  N=211

H-001 (MLE+IMS_90-94 > MLE_only + 0.5pp): NOT SUPPORTED
H-002 (kombinace > kazdy modul samostatne):        NOT SUPPORTED
H-003 (monotonni rust 70-79 < 80-89 < 90-94):       NOT SUPPORTED

N celkem: 7,446 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `6a943627d8511e252334fb0b0192412cd08a199d5dbce17e30dd7f8e35928360`
