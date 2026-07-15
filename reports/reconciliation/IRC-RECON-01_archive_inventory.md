# IRC-RECON-01 — Archive Inventory

## Verdikt: PASS

## 1. Schema

- columns: ['date', 'lookback', 'rank', 'industry', 'sector', 'median_return', 'mean_return', 'member_count', 'advance_ratio', 'top_1_ticker', 'top_1_return', 'top_2_ticker', 'top_2_return', 'top_3_ticker', 'top_3_return', 'status']
- row_count: 63720
- has_lookback_col: True
- has_rank_col: True
- has_rank_20d_wide: False

## 2. Date

- range: 2025-06-02 .. 2026-06-27
- unique_dates: 270
- overlap (2025-07-09..2026-06-27): 245 dni, 57820 radku

## 3. Rows per date

- {'min': 236, 'median': 236, 'max': 236}

## 4. Taxonomy

- unique_industry: 59
- unique_sector: 9
- has_subcategory: False
- unique_subcategory: None
- industry_sample: ['Advertising', 'Aerospace/Defense', 'Agriculture', 'Airlines', 'Apparel', 'Auto Manufacturers', 'Auto Parts&Equipment', 'Banks', 'Beverages', 'Biotechnology', 'Building Materials', 'Chemicals', 'Commercial Services', 'Computers', 'Cosmetics/Personal Care', 'Distribution/Wholesale', 'Diversified Finan Serv', 'Electric', 'Electrical Compo&Equip', 'Electronics', 'Energy-Alternate Sources', 'Engineering&Construction', 'Entertainment', 'Environmental Control', 'Food', 'Forest Products&Paper', 'Gas', 'Hand/Machine Tools', 'Healthcare-Products', 'Healthcare-Services']
- sector_sample: ['Basic Materials', 'Communications', 'Consumer, Cyclical', 'Consumer, Non-cyclical', 'Energy', 'Financial', 'Industrial', 'Technology', 'Utilities']

## 5. Duplicates

- {'by_date_industry_lookback': 0}

## 6. Missing dates (vs MLE overlap)

- mle_overlap_dates: 248
- irc_overlap_dates: 245
- in_mle_not_irc (3): ['2026-05-31', '2026-06-06', '2026-06-13']
- in_irc_not_mle (0): []

## 7. rank_20d availability

- {'format': 'long (lookback col)', 'rank20_rows': 15930, 'rank20_dates': 270}

## 8. TOP10 industry per date (rank_20d <= 10)

- {'per_date_min': 10, 'per_date_median': 10, 'per_date_max': 10, 'dates_with_top10': 245, 'unique_industries_in_top10': 44}

## 9. IRC <-> MLE join (industry)

- mle_unique_industries: 59
- irc_unique_industries: 59
- common_industries: 59
- industry_join_rate: 1.0
- irc_only_industries: []
- mle_only_industries: []

## 10. Mismatch risks

- zadne

## Vyhrady

- IRC schema detekovan z hlavicky; lookback long vs rank_20d wide.
- industry join = textova shoda IRC industry vs MLE industry.
- NEPOUZITA Sharadar TICKERS industry (dle zadani).
- industry_rank_calendar projekt necten (jen archive CSV).
