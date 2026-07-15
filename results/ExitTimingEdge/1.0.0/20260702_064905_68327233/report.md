# ExitTimingEdge — v1.0.0

**Run ID:** `68327233-5340-4f3c-847b-78e3f9dbbc37`
**Datum spuštění:** 2026-07-02 06:49:05 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

H1a: EMA20 exit (signal close<EMA20, fill next open) zvyšuje mean return uvnitř fixního 20D okna proti fixed 20D hold, nad MLE×IRC kandidáty — matched comparison, po exitu cash 0 %.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0011: Exit Timing Edge (pre-registered, PM approved 2026-07-02)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 620 |
| unique_tickers | 116 |
| excluded_warmup | 424 |
| excluded_price_data | 0 |
| common_warmup_bars | 90 |
| H1a_paired_diff_pp | -2.719 |
| H1a_ci_lo_pp | -4.548 |
| H1a_ci_hi_pp | -1.112 |
| H1a_pass | False |
| baseline_mean_pct | 8.572 |
| ema_20_paired_diff_pp | -2.719 |
| ema_20_early_exit_pct | 63.23 |
| ema_20_hold_mean_d | 14.61 |
| ema_10_paired_diff_pp | -4.471 |
| ema_10_early_exit_pct | 89.68 |
| ema_10_hold_mean_d | 10.62 |
| ema_30_paired_diff_pp | -1.868 |
| ema_30_early_exit_pct | 42.9 |
| ema_30_hold_mean_d | 16.59 |
| H1b_N | 395 |
| H1b_censored_excluded | 225 |
| H1b_ret_mean_pct | 0.173 |
| H1b_ret_per_day_bps | -49.41 |
| H1b_hold_mean_d | 16.01 |
| H1b_hold_median_d | 13.0 |
| H1b_timestop_pct | 1.52 |

## Tabulky

- `tables/per_variant.csv`
- `tables/trades.csv`
- `tables/h1b_trades.csv`

## Summary

H1a NOT SUPPORTED — EMA20 exit nezlepšuje fixní 20D okno. Primární paired diff -2.719pp CI[-4.548, -1.112] (baseline mean 8.572%). Sensitivity: EMA_20: -2.719pp; EMA_10: -4.471pp; EMA_30: -1.868pp. H1b (exploratorní): N=395, ret/den -49.41bps, hold mean 16.01d, time-stop 1.52%. DEPENDENCE WARNING: nominal N=620 candidate-days, 116 unikátních tickerů (poměr 0.19). Efektivní N << nominal N (překrývající se okna). Signifikance výhradně ticker-clustered bootstrap. REGIME SPLIT DEFERRED: exit pravidla jsou režimově citlivější než selection (EMA exit systematicky vyhrává v choppy/klesajícím trhu, prohrává v trendu). Výsledek vázán na období běhu. Re-run po Regime Engine. CAVEATS: (1) Entry close(D) look-ahead — sdílený oběma větvemi páru, paired diff nezkresluje. (2) Sensitivity EMA10/30 NEJSOU hypotézy — žádný a-posteriori výběr periody. (3) H1b čistě deskriptivní. (4) Fixed-window design: exit realokuje kapitál do cash 0 % — reinvestiční hodnota uvolněného kapitálu patří do MSL STR-0002, ne sem.

## Reprodukovatelnost

**Result hash:** `863cdaf03cef893913a52b91cadb641d029cfcede4f614c0293d0f96e783bcc7`
