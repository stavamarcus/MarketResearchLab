# LeadershipLossEdge — v1.0.0

**Run ID:** `008f4f12-ef5d-4ece-9c90-1ea5e28ef82c`
**Datum spuštění:** 2026-07-02 07:13:44 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

H1a: exit při ztrátě leadership statusu (MLE_Rank_10d > 50, signal close, fill next open) zvyšuje mean return uvnitř fixního 20D okna proti fixed 20D hold, nad MLE×IRC kandidáty.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0012: Leadership Loss Exit (pre-registered, PM approved 2026-07-02)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 1044 |
| unique_tickers | 147 |
| censored_missing_rank_n | 0 |
| censored_missing_rank_pct | 0.0 |
| censoring_investigate | False |
| excluded_price_data | 0 |
| H1a_paired_diff_pp | -4.353 |
| H1a_ci_lo_pp | -6.32 |
| H1a_ci_hi_pp | -2.256 |
| H1a_pass | False |
| baseline_mean_pct | 7.233 |
| rank_50_paired_diff_pp | -4.353 |
| rank_50_early_exit_pct | 98.08 |
| rank_50_hold_mean_d | 8.23 |
| rank_25_paired_diff_pp | -4.939 |
| rank_25_early_exit_pct | 98.95 |
| rank_25_hold_mean_d | 6.94 |
| rank_100_paired_diff_pp | -3.494 |
| rank_100_early_exit_pct | 93.97 |
| rank_100_hold_mean_d | 9.85 |
| surv50_after_5d_pct | 61.49 |
| surv50_after_10d_pct | 17.72 |
| surv50_after_15d_pct | 5.27 |
| surv50_after_20d_pct | 1.63 |
| surv50_loss_pct | 98.37 |
| surv50_median_time_to_loss_d | 7.0 |

## Tabulky

- `tables/per_variant.csv`
- `tables/survival.csv`
- `tables/trades.csv`

## Summary

H1a NOT SUPPORTED — Leadership Loss exit nezlepšuje fixní 20D okno. Primární paired diff -4.353pp CI[-6.32, -2.256] (baseline mean 7.233%). Varianty: RANK_50: -4.353pp (early 98.08%); RANK_25: -4.939pp (early 98.95%); RANK_100: -3.494pp (early 93.97%). SURVIVAL TOP50: 5d 61.49% | 10d 17.72% | 15d 5.27% | 20d 1.63% | loss 98.37% (median t-to-loss 7.0d). CENSORING: 0 trades (0.00 %) vyloučeno pro chybějící rank (bez imputace). Pod prahem investigace. DEPENDENCE WARNING: nominal N=1044, 147 unikátních tickerů (poměr 0.14). Signifikance výhradně ticker-clustered bootstrap. REGIME SPLIT DEFERRED: leadership loss frekvence je režimově závislá (rotace vs trvalý trend). Výsledek vázán na období běhu. CAVEATS: (1) Entry close(D) look-ahead — sdílený párem. (2) RANK_25/100 sensitivity, NE hypotézy. (3) Survival = deskriptivní interpretace, bez kritéria. (4) Reinvestice uvolněného kapitálu → MSL, ne sem.

## Reprodukovatelnost

**Result hash:** `2ad1d862a8d9f4bf6906a616ce0d595084ede88edd011c2e7cca94a03b4b3309`
