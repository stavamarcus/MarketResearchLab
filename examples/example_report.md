# IMSScoreBucketEdge — v1.0.0

**Run ID:** `b7159986-8a49-49ae-95b1-8b76f8459976`
**Datum spuštění:** 2026-06-29 23:12:04 UTC
**Datový rozsah:** 2025-07-09 → 2026-04-30
**Universum:** sp500_rank_calendar

## Hypotéza

Akcie s IMS skóre >= 90 (ELITE bucket) dosahují vyššího median 30D forward
returnu než akcie s IMS skóre 60–69 (RADAR bucket).

## Konfigurace

_(žádné parametry)_

**Poznámky:** Reference Experiment #2 — IMS Score Bucket Edge

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_signals_total | 17408 |
| n_eligible_days | 188 |
| n_unique_tickers | 457 |
| hypothesis_window_d | 30 |
| hypothesis_spread_threshold | 0.5 |
| elite_median_ret_30d | 0.017146 |
| radar_median_ret_30d | 0.005813 |
| elite_minus_radar_30d | 0.011333 |
| h001_supported | True |

## Tabulky

- `tables/bucket_stats.csv`

## Summary

IMS Score Bucket Edge — 30D forward return

Hypotéza H-001: ✓ SUPPORTED
  ELITE (90–94) median 30D: +1.71%
  RADAR (60–69) median 30D: +0.58%
  Spread (ELITE–RADAR):       +1.12% (threshold: +0.5%)
  H95+ median 30D:           +2.24%

N signálů celkem: 17,408 | Unikátní tickery: 457
Datový rozsah: 2025-07-09 → 2026-04-30
Universe: sp500_rank_calendar

## Reprodukovatelnost

**Result hash:** `692c6f0a7821ada269168cba3649e6db...`
