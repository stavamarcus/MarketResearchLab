# MLE-RECON-00 — Universe Preflight

## Verdikt: WARN

## 1. Universe CSV

- columns: ['conid', 'ticker', 'exchange', 'currency', 'instrument_type', 'sector', 'industry', 'subcategory', 'active_flag']
- row_count: 503
- active_flag_values: {'1': 503}
- active_count: 503
- inactive_count: 0
- duplicate_conid: 0
- duplicate_ticker: 0
- missing_conid: 0
- missing_ticker: 0
- order_preserved: True (read_csv bez sortu)
- first_5_order: [{'order': 0, 'conid': '9720', 'ticker': 'MMM'}, {'order': 1, 'conid': '12225', 'ticker': 'AOS'}, {'order': 2, 'conid': '4065', 'ticker': 'ABT'}, {'order': 3, 'conid': '118089500', 'ticker': 'ABBV'}, {'order': 4, 'conid': '67889930', 'ticker': 'ACN'}]

## 2. DATA-06 coverage

- view_files: 503
- active_covered_in_view: 503
- active_missing_in_view: 0
- missing_sample: []

## 3. Archive coverage

- archive_rows: 124247
- unique_tickers: 499
- date_range: 2025-07-09..2026-07-04
- rows_per_date: min=493 median=497 max=499
- archive_tickers_not_in_active_universe (0): []
- active_universe_not_in_archive (4): ['EXE', 'PSKY', 'Q', 'SNDK']
- archive_tickers_not_in_view (0): []

## 4. Order check

- order_index = poradi radku v universe_csv (read_csv bez sortu).
- MLE-RECON-01 MUSI plnit close_prices dict v tomto poradi
  (tie-break pri shodnem returnu zavisi na poradi).

## 5. Alias / manual-review vyjimky (z PRICE-RECON-01C)

- alias 129348130 (NWS->NWSA): in_active_universe=True
- alias 208813720 (GOOG->GOOGL): in_active_universe=True
- alias 356858007 (FOX->FOXA): in_active_universe=True
- manual_review 4886 (BDX boundary 2026-02-10): in_active_universe=True

## Vyhrady

- active_flag filtr: hodnota v {1,true,yes,y} (replikuje MLE).
- coverage FAIL prah: >5% active conid chybi v DATA-06.
- alias/BDX se reportuji, NEblokuji preflight.
