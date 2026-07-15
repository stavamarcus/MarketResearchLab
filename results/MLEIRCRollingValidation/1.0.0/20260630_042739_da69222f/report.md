# MLEIRCRollingValidation — v1.0.0

**Run ID:** `da69222f-0997-42aa-a42a-a9e813fe3a45`
**Datum spuštění:** 2026-06-30 04:27:39 UTC
**Datový rozsah:** 2025-07-09 → 2026-06-29
**Universum:** sp500_rank_calendar

## Hypotéza

Diff alpha (MLE+IRC_TOP10 vs MLE_HEADWIND) je kladny ve vetsine rolling oken (>=70%) napric dostupnou historii.

## Konfigurace

_(žádné parametry)_

**Poznámky:** RP-0005: MLE x IRC Rolling Validation

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_windows_total | 8 |
| n_windows_valid | 8 |
| n_windows_skipped | 0 |
| window_size_days | 60 |
| step_days | 20 |
| min_signals_per_window | 100 |
| n_windows_positive_diff | 6 |
| pct_windows_positive | 0.75 |
| median_window_diff | 1.4078 |
| min_window_diff | -0.6624 |
| max_window_diff | 2.8491 |
| h_pct_supported | True |
| h_median_supported | True |
| h_supported | True |

## Tabulky

- `tables/windows.csv`

## Summary

MLE x IRC Rolling Validation
Question: Does the MLE+IRC edge hold across time windows?

Config: MLE TOP20 (rank_10d) x IRC TOP10  |  alpha vs SPY 30D
Rolling: window=60d, step=20d, min_signals=100

Okna celkem: 8 | Validni: 8 | Preskoceno (malo signalu): 0

Okna (window_start -> diff):
  2025-07-09 -> 2025-10-01: diff=+2.69% (N=1200)
  2025-08-06 -> 2025-10-29: diff=+2.32% (N=1200)
  2025-09-04 -> 2025-11-26: diff=+1.32% (N=1200)
  2025-10-02 -> 2025-12-26: diff=-0.66% (N=1200)
  2025-10-30 -> 2026-01-27: diff=+0.39% (N=1200)
  2025-11-28 -> 2026-02-25: diff=+2.85% (N=1200)
  2025-12-29 -> 2026-03-25: diff=+1.49% (N=1200)
  2026-01-28 -> 2026-04-23: diff=-0.33% (N=1200)

Okna s kladnym diff: 6/8 (75%)
Median window diff: +1.41%
Rozsah diff: -0.66% az +2.85%

Kriterium 1 (>=70% oken kladnych): SUPPORTED
Kriterium 2 (median diff > 0.5pp):       SUPPORTED

CELKOVY ZAVER: SUPPORTED

## Reprodukovatelnost

**Result hash:** `344c5c909666f962820292e4754af1eedf978b9f27bf0ee93928a88b6461e979`
