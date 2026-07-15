# RSAccelEdge — v1.0.0

**Run ID:** `c1c68a1f-d11d-49cf-bd34-e8fc7b940f54`
**Datum spuštění:** 2026-07-01 04:01:06 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

H1: vyšší RS Acceleration (5D RS − 20D RS vs SPY) koreluje s vyšším 20D forward return nad MLE×IRC kandidáty. H0: nepřidává edge. Spojitý vztah (Spearman), žádný práh, žádný window sweep.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0010: RS Acceleration Edge (F002, 5D-20D, spojitý target)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 976 |
| unique_tickers | 142 |
| spearman_rho | -0.0905 |
| rho_ci_lo | -0.1993 |
| rho_ci_hi | 0.032 |
| rho_significant | False |
| H1_supported | False |
| H0_rejected | False |
| quantile_spread_top_minus_bottom_pp | -5.264 |
| rs_accel_min | -1.6015 |
| rs_accel_median | -0.1439 |
| rs_accel_max | 0.3406 |

## Tabulky

- `tables/quantile_buckets.csv`

## Summary

RS Acceleration vs 20D fwd (spojitý): Spearman rho=-0.0905 CI[-0.1993,0.032] sig=False → H1 NOT SUPPORTED (H0 nezamítnuta). POZOR: rho je ZÁPORNÉ (-0.0905) — náznak jde OPAČNĚ než H1 (decelerace → vyšší fwd), ale nesignifikantně (CI přes nulu). Exploratorní, ne nález. Kvantilový spread (Q5-Q1): -5.264pp (JEN interpretace, ne edge). KNOWN LIMITATION: RS_Accel se překrývá s MLE selection → i případný signifikantní výsledek NEčíst automaticky jako nezávislý edge. DEPENDENCE: nominal N=976, tickerů=142 (poměr 0.15) → efektivní N << nominal. Signifikance jen z ticker-clustered bootstrapu; naivní p ignorovat. REGIME SPLIT DEFERRED.

## Reprodukovatelnost

**Result hash:** `fa6e751a0d7e0c466ad51af621252ac52c81e292239e523ab61bbda8bf7ac88a`
