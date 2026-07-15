# Cap02MarketCapPerformance — v1.0.0

**Run ID:** `c9369fc7-ecec-4478-971d-9cb2476f3179`
**Datum spuštění:** 2026-07-05 05:24:21 UTC
**Datový rozsah:** 2025-07-09 → 2026-08-01
**Universum:** sp500_rank_calendar

## Hypotéza

Market-cap bucket MLE × IRC candidate-days diferencuje forward returns (median 20D) oproti celkovému vzorku.

## Konfigurace

- `market_cap_output_csv`: C:\Users\stava\Projects\MarketResearchLab\results\diagnostics\cap01_market_cap_coverage_20260705_050531_sf1art_20260704_005521\market_cap_output.csv
- `market_cap_sha256`: 70d392b4d242c3f832c4f446579774d51572fa7e4aeee98fdc34110fcd1acb26

**Poznámky:** MRL-CAP-02 signal-level market-cap performance

## Metriky

| Metrika | Hodnota |
|---------|---------|
| overall_result | COMPLETED |
| candidate_days | 1144 |
| baseline_median_20d | 2.4037 |
| baseline_hit_20d | 0.5995 |
| entry_price_missing | 3 |
| status_Mega | PASS |
| status_Large-high | FAIL |
| status_Large-low | PASS |
| status_Mid | INCONCLUSIVE |
| status_Small | NOT_INTERPRETED |
| status_UNBUCKETED | NOT_INTERPRETED |
| median_20d_Mega | 6.8871 |
| median_20d_Large-high | 3.6541 |
| median_20d_Large-low | 0.0652 |
| median_20d_Mid | 4.8227 |

## Tabulky

- `tables/bucket_performance.csv`
- `tables/dependence.csv`
- `tables/forward_returns.csv`

## Summary

CAP-02 signal-level — COMPLETED. Mega:PASS; Large-high:FAIL; Large-low:PASS; Mid:INCONCLUSIVE. Není strategie; PASS = kandidát na DR výzkum.

## Reprodukovatelnost

**Result hash:** `549e9584dcaf5a246c168b7b8cb25e18940adbfb20f1f71239bd64b4d0795645`
