# IRCPersistenceEdge — v1.0.0

**Run ID:** `918dfab9-7da8-4c18-b540-86d219b77be6`
**Datum spuštění:** 2026-06-30 07:04:26 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Industries persistentne v IRC TOP10 (6-15 dni za poslednich 20 obchodnich dni) maji vyssi median 30D alpha nez nove vstoupive industries (1-2 dny).

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0006: IRC Persistence Edge (industry-level, bez MLE)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_records_total | 1950 |
| n_eligible_dates | 195 |
| n_unique_industries | 44 |
| primary_window_d | 30 |
| primary_metric | alpha_vs_spy |
| new_top10_median_alpha | -1.0868 |
| persistent_top10_median_alpha | -0.0021 |
| diff_persistent_vs_new | 1.0847 |
| h_supported | True |
| NEW_TOP10_n | 209 |
| NEW_TOP10_median_alpha_30d | -1.0868 |
| NEW_TOP10_wr_alpha_30d | 0.4115 |
| EMERGING_TOP10_n | 302 |
| EMERGING_TOP10_median_alpha_30d | -0.6639 |
| EMERGING_TOP10_wr_alpha_30d | 0.4536 |
| PERSISTENT_TOP10_n | 887 |
| PERSISTENT_TOP10_median_alpha_30d | -0.0021 |
| PERSISTENT_TOP10_wr_alpha_30d | 0.4994 |
| EXTENDED_TOP10_n | 552 |
| EXTENDED_TOP10_median_alpha_30d | -0.0717 |
| EXTENDED_TOP10_wr_alpha_30d | 0.4909 |

## Tabulky

- `tables/bucket_stats.csv`

## Summary

IRC Persistence Edge (industry-level, bez MLE)
Question: Do persistently strong industries have higher forward alpha?

IRC TOP10 dnes, persistence okno 20d  |  Metrika: alpha vs SPY  |  Window: 30D

Buckety:
  NEW_TOP10          alpha=-1.09%  WR=41.1%  N=209
  EMERGING_TOP10     alpha=-0.66%  WR=45.4%  N=302
  PERSISTENT_TOP10   alpha=-0.00%  WR=49.9%  N=887
  EXTENDED_TOP10     alpha=-0.07%  WR=49.1%  N=552

Diff (PERSISTENT vs NEW): +1.08%

H (PERSISTENT_TOP10 > NEW_TOP10 + 0.5pp alpha): SUPPORTED

N celkem: 1,950 | Unikatni industries: 44 | Datumy: 195
Rozsah: 2025-07-09 -> 2026-06-29

## Reprodukovatelnost

**Result hash:** `c0af728e714e357362a1d1f2b35a14bf54ea44345560bfbcc13c0c39c4d4888c`
