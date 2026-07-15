# MLEIMSInteraction — v1.0.0

**Run ID:** `a8f8b709-864d-4749-9ae5-43ddc995acc3`
**Datum spuštění:** 2026-06-30 02:20:31 UTC
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
| n_records_total | 4377 |
| n_eligible_days | 219 |
| mle_rank_max | 20 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| mle_only_median_alpha | 1.3996 |
| ims_only_median_alpha | -11.7247 |
| mle_ims_90_94_median_alpha | 0.4591 |
| mle_ims_80_89_median_alpha | 0.043 |
| mle_ims_70_79_median_alpha | 0.1946 |
| h001_supported | False |
| h002_supported | False |
| h003_supported | False |
| MLE_ONLY_n | 2052 |
| MLE_ONLY_median_alpha_30d | 1.3996 |
| MLE_ONLY_wr_alpha_30d | 0.5443 |
| IMS_ONLY_n | 6 |
| IMS_ONLY_median_alpha_30d | -11.7247 |
| IMS_ONLY_wr_alpha_30d | 0.3333 |
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
  MLE_ONLY         alpha=+1.40%  WR=54.4%  N=2052
  IMS_ONLY         alpha=-11.72%  WR=33.3%  N=6
  MLE+IMS_70-79    alpha=+0.19%  WR=51.0%  N=907
  MLE+IMS_80-89    alpha=+0.04%  WR=50.4%  N=1201
  MLE+IMS_90-94    alpha=+0.46%  WR=52.6%  N=211

H-001 (MLE+IMS_90-94 > MLE_only + 0.5pp): NOT SUPPORTED
H-002 (kombinace > kazdy modul samostatne):        NOT SUPPORTED
H-003 (monotonni rust 70-79 < 80-89 < 90-94):       NOT SUPPORTED

N celkem: 4,377 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `4bf7a830393a2299f191665bb34a1e72b11f3042723d1817c87a6aa53e32e30b`
