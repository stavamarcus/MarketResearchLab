# IMSScoreBucketEdge — v1.0.0

**Run ID:** `79e0a69b-5bba-4b19-96a1-6f961c7d00e1`
**Datum spuštění:** 2026-06-30 00:38:09 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Akcie s IMS skóre >= 90 (ELITE bucket) dosahují vyššího median 30D forward returnu než akcie s IMS skóre 60–69 (RADAR bucket).

## Konfigurace

_(žádné parametry)_

**Poznámky:** First real run on local data after GDU

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_signals_total | 20853 |
| n_eligible_days | 219 |
| n_unique_tickers | 466 |
| hypothesis_window_d | 30 |
| hypothesis_spread_threshold | 0.5 |
| elite_median_ret_30d | 2.7711 |
| radar_median_ret_30d | 0.6316 |
| h95_median_ret_30d | 4.535 |
| elite_minus_radar_30d | 2.1395 |
| h001_supported | True |
| RADAR_5d_n | 8722 |
| RADAR_5d_median_ret | 0.0946 |
| RADAR_5d_win_rate | 0.514 |
| RADAR_10d_n | 8722 |
| RADAR_10d_median_ret | 0.2179 |
| RADAR_10d_win_rate | 0.5256 |
| RADAR_20d_n | 8722 |
| RADAR_20d_median_ret | 0.4352 |
| RADAR_20d_win_rate | 0.5308 |
| RADAR_30d_n | 8722 |
| RADAR_30d_median_ret | 0.6316 |
| RADAR_30d_win_rate | 0.5346 |
| H70-79_5d_n | 7644 |
| H70-79_5d_median_ret | 0.0397 |
| H70-79_5d_win_rate | 0.505 |
| H70-79_10d_n | 7644 |
| H70-79_10d_median_ret | 0.1382 |
| H70-79_10d_win_rate | 0.5145 |
| H70-79_20d_n | 7644 |
| H70-79_20d_median_ret | 0.2966 |
| H70-79_20d_win_rate | 0.5215 |
| H70-79_30d_n | 7644 |
| H70-79_30d_median_ret | 0.6298 |
| H70-79_30d_win_rate | 0.536 |
| H80-89_5d_n | 4106 |
| H80-89_5d_median_ret | 0.2764 |
| H80-89_5d_win_rate | 0.5363 |
| H80-89_10d_n | 4106 |
| H80-89_10d_median_ret | 0.4605 |
| H80-89_10d_win_rate | 0.5395 |
| H80-89_20d_n | 4106 |
| H80-89_20d_median_ret | 0.4355 |
| H80-89_20d_win_rate | 0.5343 |
| H80-89_30d_n | 4106 |
| H80-89_30d_median_ret | 0.6783 |
| H80-89_30d_win_rate | 0.5436 |
| H90-94_5d_n | 366 |
| H90-94_5d_median_ret | 0.8467 |
| H90-94_5d_win_rate | 0.6148 |
| H90-94_10d_n | 366 |
| H90-94_10d_median_ret | 1.336 |
| H90-94_10d_win_rate | 0.5984 |
| H90-94_20d_n | 366 |
| H90-94_20d_median_ret | 1.6673 |
| H90-94_20d_win_rate | 0.612 |
| H90-94_30d_n | 366 |
| H90-94_30d_median_ret | 2.7711 |
| H90-94_30d_win_rate | 0.6011 |
| H95+_5d_n | 15 |
| H95+_5d_median_ret | -0.0381 |
| H95+_5d_win_rate | 0.4667 |
| H95+_10d_n | 15 |
| H95+_10d_median_ret | 0.6841 |
| H95+_10d_win_rate | 0.6667 |
| H95+_20d_n | 15 |
| H95+_20d_median_ret | 1.5757 |
| H95+_20d_win_rate | 0.6667 |
| H95+_30d_n | 15 |
| H95+_30d_median_ret | 4.535 |
| H95+_30d_win_rate | 0.6 |

## Tabulky

- `tables/bucket_stats.csv`

## Summary

IMS Score Bucket Edge — 30D forward return

Hypotéza H-001: ✓ SUPPORTED
  ELITE (90–94) median 30D: +2.77%
  RADAR (60–69) median 30D: +0.63%
  Spread (ELITE–RADAR):       +2.14% (threshold: +0.5%)
  H95+ median 30D:           +4.54%

N signálů celkem: 20,853 | Unikátní tickery: 466
Datový rozsah: 2025-07-09 → 2026-06-29
Universe: sp500_rank_calendar

## Reprodukovatelnost

**Result hash:** `c1a5e9ac3a13f3f51efe83fb2206289b260cad8cf3c816fb2f7cfc3e778af371`
