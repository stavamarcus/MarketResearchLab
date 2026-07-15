# MLEIRCDependencyAudit — v1.1.0

**Run ID:** `23da9018-1a6f-4e24-8061-fd5bd24bb5e3`
**Datum spuštění:** 2026-06-30 01:34:17 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

MLE TOP20 (10D) kandidáti v TOP10 IRC industries dosahují vyšší median alpha vs SPY (30D) než MLE TOP20 kandidáti v slabších industries.

## Konfigurace

_(žádné parametry)_

**Poznámky:** MLE x IRC Dependency Audit v1.1.0 - reprodukce Test 7

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 4380 |
| n_eligible_days | 219 |
| mle_rank_field | MLE_Rank_10d |
| mle_rank_max | 20 |
| irc_rank_max | 10 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| mle_all_median_alpha_30d | 0.6221 |
| mle_irc_top10_median_alpha | 1.4129 |
| mle_headwind_median_alpha | 0.1298 |
| mle_irc_top10_wr_alpha | 0.5509 |
| mle_headwind_wr_alpha | 0.505 |
| diff_top10_vs_headwind | 1.2831 |
| h_supported | True |
| MLE_IRC_TOP10_n | 1984 |
| MLE_IRC_TOP10_median_alpha_30d | 1.4129 |
| MLE_IRC_TOP10_wr_alpha_30d | 0.5509 |
| MLE_HEADWIND_n | 2396 |
| MLE_HEADWIND_median_alpha_30d | 0.1298 |
| MLE_HEADWIND_wr_alpha_30d | 0.505 |

## Tabulky

- `tables/group_stats.csv`

## Summary

MLE x IRC Dependency Audit v1.1.0
Reprodukce metodiky IRC Audit Test 7

MLE: rank_10d <= 20  |  IRC: TOP10  |  Metrika: alpha vs SPY
Primary: 30D median alpha

Skupiny:
  MLE+IRC_TOP10        alpha=+1.41%  WR=55.1%  N=1984
  MLE_HEADWIND         alpha=+0.13%  WR=50.5%  N=2396

MLE all (bez IRC filtru): +0.62%
Diff (TOP10 vs HEADWIND): +1.28%

H (TOP10 > HEADWIND + 0.5pp alpha): SUPPORTED

N celkem: 4,380 | Dny: 219
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `4a2c2c01c538f9309268162e62c18f3c8aeed1ded198fd30b7d2c69d8bc2b0bf`
