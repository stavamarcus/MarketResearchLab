# EntryTimingEdge — v1.0.0

**Run ID:** `df22ba65-4b2d-47c8-b77b-907f91e5eb7a`
**Datum spuštění:** 2026-07-01 02:10:10 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Čekání na cenový pullback (ENTRY_002 / ENTRY_003) přidává inkrementální forward-return edge nad baseline close-entry (ENTRY_001) nad množinou MLE×IRC kandidátů — měřeno matched i strategy-level, s opportunity cost přeskočených obchodů.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0009: Entry Timing Edge (pre-registered ENTRY_001/002/003)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 1015 |
| unique_tickers | 142 |
| S2_filled | 990 |
| K2_skipped | 25 |
| fill_002_pct | 97.5 |
| S3_filled | 699 |
| K3_skipped | 316 |
| fill_003_pct | 68.9 |
| entry_alpha_002_pp | 0.129 |
| entry_alpha_002_ci_lo | -0.486 |
| entry_alpha_002_ci_hi | 0.818 |
| entry_alpha_002_significant | False |
| entry_alpha_003_pp | 3.192 |
| entry_alpha_003_ci_lo | 1.98 |
| entry_alpha_003_ci_hi | 4.425 |
| entry_alpha_003_significant | True |
| direct_003_minus_002_pp_on_intersection | 2.795 |
| intersection_N | 694 |
| strategy_net_baseline_pct | 7.145 |
| strategy_net_002_pct | 6.721 |
| strategy_net_002_delta_pp | -0.424 |
| strategy_net_003_pct | 4.768 |
| strategy_net_003_delta_pp | -2.377 |
| skipped_K2_baseline_ret_mean_pct | 22.31 |
| entered_S2_baseline_ret_mean_pct | 6.76 |
| skipped_K3_baseline_ret_mean_pct | 14.7 |
| entered_S3_baseline_ret_mean_pct | 3.73 |
| win_001_pct | 64.73 |
| win_002_pct | 64.75 |
| win_003_pct | 66.67 |
| median_001_pct | 4.336 |
| median_002_pct | 3.941 |
| median_003_pct | 4.776 |
| pf_001 | 3.675 |
| pf_002 | 3.55 |
| pf_003 | 3.811 |
| entry_delay_002_days | 1.91 |
| entry_delay_003_days | 3.89 |

## Tabulky

- `tables/per_variant.csv`

## Summary

ENTRY_002: žádný entry edge + strategy-level horší. ENTRY_003: conditional entry alpha ANO, ale strategy-level HORŠÍ (míjí movery). Skipped baseline ret (K3 14.7% vs S3 entered 3.73%) → pullback míjí nejsilnější movery. DEPENDENCE WARNING: nominal N=1015 candidate-days, ale jen 142 unikátních tickerů (poměr 0.14). Efektivní N << nominal N (překrývající se 20D okna + opakovaný výskyt tickeru). Signifikance výhradně z ticker-clustered bootstrapu (resample tickerů). Naivní t-test/win-rate NEPOUŽÍVAT. REGIME SPLIT DEFERRED: chybí schválené režimové štítky. Až vznikne schválený Regime Engine / režimové štítky, entry-edge je nutné stratifikovat (pullback edge je režimově citlivý — v silném trendu míjí movery, v choppy/mean-reverting režimu se verdikt může obrátit). Tento výsledek je vázaný na období běhu (pravděpodobně jeden režim). CAVEATS: (1) Baseline close look-ahead — ENTRY_001 vstup na close signálu (konzistentní s předchozími MRL audity, mírně nadhodnocuje baseline). (2) Jedno běhové období, regime deferred. (3) matched entry alpha a strategy-level net mohou protiřečit — obojí reportováno odděleně; strategy-level zahrnuje opportunity cost přeskočených jako 0/cash.

## Reprodukovatelnost

**Result hash:** `5bf2b910868f0e7bf6c87b9a104490a0d85502f1319656b1e85d52c2d90bad8f`
