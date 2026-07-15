# MLEBucketsIRCGrid — v1.0.0

**Run ID:** `7893a553-54c8-4997-a118-2f182a26c11c`
**Datum spuštění:** 2026-06-30 08:33:15 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

MLE TOP10 ma kladnou alpha i bez IRC. MLE 11-30 potrebuje IRC TOP10 potvrzeni pro kladnou alpha. MLE 51+ zustava negativni i s IRC potvrzenim.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0008: MLE Rank Buckets x IRC Tailwind

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 21900 |
| n_eligible_days | 219 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| h001_top10_positive_without_irc | True |
| h001_top10_headwind_alpha | 0.2301 |
| h002_some_bucket_needs_irc | True |
| h003_51plus_dead_even_with_irc | True |
| MLE_1_10_IRC_TOP_n | 1017 |
| MLE_1_10_IRC_TOP_median_alpha_30d | 2.4919 |
| MLE_1_10_IRC_TOP_wr_alpha_30d | 0.591 |
| MLE_1_10_HEADWIND_n | 1173 |
| MLE_1_10_HEADWIND_median_alpha_30d | 0.2301 |
| MLE_1_10_HEADWIND_wr_alpha_30d | 0.5115 |
| MLE_11_20_IRC_TOP_n | 967 |
| MLE_11_20_IRC_TOP_median_alpha_30d | 0.1225 |
| MLE_11_20_IRC_TOP_wr_alpha_30d | 0.5088 |
| MLE_11_20_HEADWIND_n | 1223 |
| MLE_11_20_HEADWIND_median_alpha_30d | -0.0574 |
| MLE_11_20_HEADWIND_wr_alpha_30d | 0.4988 |
| MLE_21_30_IRC_TOP_n | 856 |
| MLE_21_30_IRC_TOP_median_alpha_30d | -0.5757 |
| MLE_21_30_IRC_TOP_wr_alpha_30d | 0.4766 |
| MLE_21_30_HEADWIND_n | 1334 |
| MLE_21_30_HEADWIND_median_alpha_30d | -0.4246 |
| MLE_21_30_HEADWIND_wr_alpha_30d | 0.4805 |
| MLE_31_50_IRC_TOP_n | 1620 |
| MLE_31_50_IRC_TOP_median_alpha_30d | -0.4381 |
| MLE_31_50_IRC_TOP_wr_alpha_30d | 0.4778 |
| MLE_31_50_HEADWIND_n | 2760 |
| MLE_31_50_HEADWIND_median_alpha_30d | -0.6024 |
| MLE_31_50_HEADWIND_wr_alpha_30d | 0.475 |
| MLE_51_70_IRC_TOP_n | 1515 |
| MLE_51_70_IRC_TOP_median_alpha_30d | -1.4655 |
| MLE_51_70_IRC_TOP_wr_alpha_30d | 0.4416 |
| MLE_51_70_HEADWIND_n | 2865 |
| MLE_51_70_HEADWIND_median_alpha_30d | -1.1106 |
| MLE_51_70_HEADWIND_wr_alpha_30d | 0.4478 |
| MLE_71_100_IRC_TOP_n | 1986 |
| MLE_71_100_IRC_TOP_median_alpha_30d | -1.0035 |
| MLE_71_100_IRC_TOP_wr_alpha_30d | 0.4411 |
| MLE_71_100_HEADWIND_n | 4584 |
| MLE_71_100_HEADWIND_median_alpha_30d | -1.3163 |
| MLE_71_100_HEADWIND_wr_alpha_30d | 0.4282 |

## Tabulky

- `tables/grid_stats.csv`

## Summary

MLE Rank Buckets x IRC Tailwind
Question: Can IRC rescue weaker MLE buckets, or does it mainly help strong ones?

Metrika: alpha vs SPY  |  Primary: 30D  |  IRC TOP10

Bucket              HEADWIND       IRC_TOP      Diff
MLE_1_10              +0.23%        +2.49%    +2.26%
MLE_11_20             -0.06%        +0.12%    +0.18%
MLE_21_30             -0.42%        -0.58%    -0.15%
MLE_31_50             -0.60%        -0.44%    +0.16%
MLE_51_70             -1.11%        -1.47%    -0.35%
MLE_71_100            -1.32%        -1.00%    +0.31%

H-001 (TOP10 kladna i bez IRC): ANO  [+0.23%]
H-002 (11-30 potrebuje IRC):    ANO
   MLE_11_20: HEADWIND=-0.06%, IRC_TOP=+0.12%, potrebuje_IRC=ANO
   MLE_21_30: HEADWIND=-0.42%, IRC_TOP=-0.58%, potrebuje_IRC=NE
H-003 (51+ mrtve i s IRC):      ANO

N celkem: 21,900 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `1313f957268e0379718094f0cd2679f2ca0485ba1b935907079d032b9fcfb352`
