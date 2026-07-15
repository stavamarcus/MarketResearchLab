# MLEIMSInteraction — v1.1.0

**Run ID:** `86302a5a-9ff8-494e-bf96-f59e3fc1a602`
**Datum spuštění:** 2026-06-30 02:46:02 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

MLE TOP20 kandidati s vyssim IMS skore maji vyssi 30D alpha vs SPY nez MLE TOP20 kandidati s nizkym nebo chybejicim IMS skore.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0003: IMS prioritization within MLE TOP20

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 4380 |
| n_eligible_days | 219 |
| mle_rank_max | 20 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| hypothesis_definition | IMS_<70 vs IMS_90_94 (IMS_95plus EXCLUDED — exploratory only) |
| ims_low_median_alpha | -0.3811 |
| ims_high_median_alpha | 0.4591 |
| diff_high_vs_low | 0.8402 |
| h_supported | True |
| is_monotonic | False |
| ims_95plus_n_exploratory_only | 9 |
| IMS_MISSING_n | 1605 |
| IMS_MISSING_median_alpha_30d | 1.9095 |
| IMS_MISSING_wr_alpha_30d | 0.5595 |
| IMS_lt_70_n | 447 |
| IMS_lt_70_median_alpha_30d | -0.3811 |
| IMS_lt_70_wr_alpha_30d | 0.4899 |
| IMS_70_79_n | 907 |
| IMS_70_79_median_alpha_30d | 0.1946 |
| IMS_70_79_wr_alpha_30d | 0.5105 |
| IMS_80_89_n | 1201 |
| IMS_80_89_median_alpha_30d | 0.043 |
| IMS_80_89_wr_alpha_30d | 0.5037 |
| IMS_90_94_n | 211 |
| IMS_90_94_median_alpha_30d | 0.4591 |
| IMS_90_94_wr_alpha_30d | 0.5261 |
| IMS_95plus_n | 9 |
| IMS_95plus_median_alpha_30d | 7.9512 |
| IMS_95plus_wr_alpha_30d | 0.7778 |

## Tabulky

- `tables/group_stats.csv`

## Summary

MLE x IMS Interaction v1.1.0
Question: Does IMS help RANK candidates WITHIN MLE TOP20?

Zakladni mnozina: MLE rank_10d <= 20  |  Metrika: alpha vs SPY  |  Window: 30D
Vsechny skupiny nize jsou PODMNOZINY teto zakladni mnoziny.

Skupiny:
  IMS_MISSING    alpha=+1.91%  WR=56.0%  N=1605
  IMS_<70        alpha=-0.38%  WR=49.0%  N=447
  IMS_70_79      alpha=+0.19%  WR=51.0%  N=907
  IMS_80_89      alpha=+0.04%  WR=50.4%  N=1201
  IMS_90_94      alpha=+0.46%  WR=52.6%  N=211
  IMS_95plus     alpha=+7.95%  WR=77.8%  N=9

HLAVNI HYPOTEZA: IMS_<70 vs IMS_90_94 (oba buckety N>200)
Diff (IMS_90_94 vs IMS_<70): +0.84%
Monotonni rust pres IMS<70 -> 70-79 -> 80-89 -> 90-94: False

H (IMS_90_94 > IMS_<70 + 0.5pp alpha): SUPPORTED

POZNAMKA: IMS_95plus (N=9) je EXPLORATORY ONLY — nevstupuje do hypotezy kvuli malemu vzorku (viz KR-2026-06-IMS-missing-diagnosis).

N celkem: 4,380 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `f279707f856dc2eaaefec415bf7ae2a940c4301af3d8e6ca378c286cefacae4b`
