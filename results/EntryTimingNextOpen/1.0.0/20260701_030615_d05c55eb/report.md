# EntryTimingNextOpen — v1.0.0

**Run ID:** `d05c55eb-df93-4ca2-8efe-97d38fc5fe57`
**Datum spuštění:** 2026-07-01 03:06:15 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Vstup na open(D+1) dává stejný forward return jako vstup na close(D) nad MLE×IRC kandidáty (matched alpha ~0) → next-open je produkčně realizovatelná náhrada za close-entry baseline.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0009: Entry Timing Next-Open (close D vs open D+1)

## Metriky

| Metrika | Hodnota |
|---------|---------|
| N_candidate_days | 1049 |
| unique_tickers | 147 |
| fill_pct | 100.0 |
| entry_001_mean_ret_pct | 7.167 |
| entry_001_median_pct | 4.336 |
| entry_001_win_pct | 64.92 |
| entry_004_mean_ret_pct | 7.141 |
| entry_004_median_pct | 4.489 |
| entry_004_win_pct | 65.11 |
| matched_alpha_004_minus_001_pp | -0.026 |
| matched_alpha_ci_lo | -0.3 |
| matched_alpha_ci_hi | 0.234 |
| matched_alpha_significant | False |

## Tabulky

- `tables/per_variant.csv`

## Summary

close(D) vs open(D+1): matched alpha -0.026pp CI[-0.3,0.234] sig=False → PRAKTICKY EKVIVALENTNÍ. ENTRY_004 (open D+1) je první realizovatelná cena po signálu; ENTRY_001 (close D) nese look-ahead caveat. Žádný prakticky významný rozdíl nenalezen → next-open je produkčně použitelná náhrada za close-entry research baseline v dostupném období. DEPENDENCE WARNING: nominal N=1049, unikátních tickerů=147 (poměr 0.14). Efektivní N << nominal. Signifikance výhradně z ticker-clustered bootstrapu. REGIME SPLIT DEFERRED: jedno běhové období (pravděpodobně bull/momentum). Verdikt vázaný na období. CAVEAT: CI vylučuje jen rozdíly > ~0.3pp; 'ekvivalentní' = 'žádný prakticky významný rozdíl nenalezen', ne 'identické'.

## Reprodukovatelnost

**Result hash:** `8f3a1ebd2960165c22ff7d18301bb35aeea67a2ce2549ca1e8f3dfe5ecb0bf7e`
