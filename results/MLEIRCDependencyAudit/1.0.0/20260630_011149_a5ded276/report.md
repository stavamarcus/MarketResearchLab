# MLEIRCDependencyAudit — v1.0.0

**Run ID:** `a5ded276-85dd-4c03-9eb2-9e5979202c1b`
**Datum spuštění:** 2026-06-30 01:11:49 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

MLE kandidáti v silných IRC industries (rank <= 20) dosahují vyššího median 30D forward returnu než MLE kandidáti bez IRC podpory.

## Konfigurace

_(žádné parametry)_

**Poznámky:** MLE x IRC Dependency Audit — first run

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 47023 |
| n_eligible_days | 219 |
| mle_rank_max | 50 |
| irc_lookback | 20 |
| primary_window_d | 30 |
| mle_all_median_30d | 2.0199 |
| mle_irc_top_median_30d | 2.2355 |
| mle_irc_weak_median_30d | None |
| mle_irc_miss_median_30d | None |
| irc_strong_only_median_30d | 0.6132 |
| mle_irc_top_wr_30d | 0.5996 |
| mle_irc_weak_wr_30d | None |
| h002_supported | False |
| h003_supported | False |
| h004_supported | True |
| MLE_IRC_TOP_n | 7810 |
| MLE_IRC_TOP_median_30d | 2.2355 |
| MLE_IRC_TOP_wr_30d | 0.5996 |
| MLE_IRC_MID_n | 3140 |
| MLE_IRC_MID_median_30d | 1.2879 |
| MLE_IRC_MID_wr_30d | 0.549 |
| IRC_strong_only_n | 36073 |
| IRC_strong_only_median_30d | 0.6132 |
| IRC_strong_only_wr_30d | 0.5339 |

## Tabulky

- `tables/group_stats.csv`

## Summary

MLE × IRC Dependency Audit
Question: Does IRC context improve MLE forward returns?

Primary metric: 30D median forward return

Groups:
  MLE+IRC_TOP            median=+2.24%  WR=60.0%  N=7810
  MLE+IRC_MID            median=+1.29%  WR=54.9%  N=3140
  IRC_strong_only        median=+0.61%  WR=53.4%  N=36073

MLE all (bez IRC filtru): +2.02%

H-002 (MLE+IRC_TOP > MLE_all + 0.5pp): ✗ NOT SUPPORTED
         diff=0.22pp (2.24% vs 2.02%)
H-003 (WR TOP vs WEAK > 3pp):          ✗ NOT SUPPORTED
H-004 (MLE+IRC_TOP > IRC_only):        ✓ SUPPORTED

N celkem: 47,023 | Dny: 219
Rozsah: 2025-07-09 → 2026-06-29

## Reprodukovatelnost

**Result hash:** `f98b4c0a62ee7e494cf69e61a0d345e3ef3f5285385b60271c07c137e7815d7b`
