# VolumeRatioEdge — v1.0.0

**Run ID:** `f517acad-4b9f-4f53-8488-0e00a6556cfd`
**Datum spuštění:** 2026-07-01 03:36:00 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

H1: vyšší Volume Ratio (Volume(D)/SMA20(Volume)) koreluje s vyšším 20D forward return nad MLE×IRC kandidáty. H0: nepřidává edge. Spojitý vztah (Spearman), žádný binární práh.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0010: Volume Ratio Edge (F001, spojitý target, žádný práh)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 978 |
| unique_tickers | 142 |
| spearman_rho | 0.0747 |
| rho_ci_lo | -0.0063 |
| rho_ci_hi | 0.1457 |
| rho_significant | False |
| H1_supported | False |
| H0_rejected | False |
| quantile_spread_top_minus_bottom_pp | 5.702 |
| vol_ratio_min | 0.219 |
| vol_ratio_median | 1.065 |
| vol_ratio_max | 8.77 |

## Tabulky

- `tables/quantile_buckets.csv`

## Summary

Volume Ratio vs 20D fwd (spojitý): Spearman rho=0.0747 CI[-0.0063,0.1457] sig=False → H1 NOT SUPPORTED (H0 nezamítnuta). Kvantilový spread (Q5-Q1): 5.702pp (JEN interpretace, ne edge definice). POZOR: kvantilové jevy jsou exploratorní pozorování — nepromovat bez vlastního předregistrovaného testu (data snooping). DEPENDENCE: nominal N=978, tickerů=142 (poměr 0.15) → efektivní N << nominal. Signifikance jen z ticker-clustered bootstrapu; naivní p ignorovat. REGIME SPLIT DEFERRED.

## Reprodukovatelnost

**Result hash:** `ee5684c0de9cd6ed537b4ab7c6b825a7ff4d73419dffa3247367e30ad62291cf`
