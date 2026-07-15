# FUND-05 Edge Protocol Report

**Signal-level research. TOTO NENÍ obchodovatelná strategie** — žádné náklady, slippage, sizing, portfolio konstrukce.

- snapshot_id: `sf1art_20260704_005521`
- snapshot_data_hash: `8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0`
- candidate-days source: `C:\Users\stava\Projects\MarketResearchLab\results\diagnostics\fund03_candidate_days_20260704_225140\candidate_days.csv` (sha256 `31747e692a7ab72c38ea5e88569c949ea91038b1e5f692da937583c09e186dd1`)
- candidate-days: 1144
- feature whitelist: None
- forward return method: close-to-close, kalendářní offset [5, 10, 20] dní + nearest trading day do +5d (konvence MLEBucketsIRCGrid)
- SPY-relative method: stock_fwd - SPY_fwd (týž postup), SEKUNDÁRNÍ diagnostika (regime kontrola), ne acceptance metrika
- entry_price_missing: 3
- coverage base: pct=100.0 (excluded=0)
- coverage prior-year lookup: pct=100.0 (NO_SF1_ASOF_DATE=0 — očekávané u starých dat, jde do field_null_excluded C/F)
- financial-like names ve variantě E: 0 (E je sektorově citlivá)

## Variant definitions & výsledky

| v | rule | status | n_members | field_null_excluded | n_ret_20d | median_20d | hit_20d | spyrel_median_20d | median_5d | median_10d | nonoverlap_n | nonoverlap_median_20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | baseline only | BASELINE | 1144 | 0 | 1111 | 2.4037 | 0.5995 | 1.8638 | 0.6579 | 1.4147 | 266 | 1.9699 |
| B | netinc > 0 AND fcf > 0 | FAIL | 918 | 9 | 897 | 1.8445 | 0.5842 | 1.2435 | 0.5773 | 1.4044 | 221 | 1.739 |
| C | revenue_yoy > 0 | FAIL | 868 | 21 | 840 | 2.766 | 0.606 | 2.178 | 0.644 | 1.3531 | 201 | 2.0953 |
| D | roe > 0.15 AND equity > 0 | FAIL | 614 | 8 | 593 | 2.3155 | 0.6121 | 2.0324 | 0.7019 | 1.4954 | 148 | 1.8433 |
| E | exclude de > 2.0 OR equity <= 0 (sektorově citlivá) | FAIL | 725 | 0 | 708 | 2.7516 | 0.6158 | 2.1564 | 1.1166 | 1.7788 | 168 | 1.7906 |
| F | composite >= 4/5 | FAIL | 726 | 38 | 705 | 2.7474 | 0.6128 | 2.2422 | 0.831 | 1.6557 | 174 | 1.8433 |

## Dependence

- nominal_N: 1144
- unique_conids: 151
- unique_dates: 244
- avg_candidate_days_per_conid: 7.58
- per_date_min: 1
- per_date_median: 5.0
- per_date_max: 10
- window_overlap_note: okna [5, 10, 20] kalendářních dní se překrývají u conidů s opakovanými candidate-days; efektivní N < nominální N

## Statusy

- A: **BASELINE** — referenční
- B: **FAIL** — median20 1.8445 vs A 2.4037; hit20 0.5842 vs 0.5995; 5/10D diff ['-0.08', '-0.01']; non-overlap median20 1.739 vs A 1.9699
- C: **FAIL** — median20 2.766 vs A 2.4037; hit20 0.606 vs 0.5995; 5/10D diff ['-0.01', '-0.06']; non-overlap median20 2.0953 vs A 1.9699
- D: **FAIL** — median20 2.3155 vs A 2.4037; hit20 0.6121 vs 0.5995; 5/10D diff ['+0.04', '+0.08']; non-overlap median20 1.8433 vs A 1.9699
- E: **FAIL** — median20 2.7516 vs A 2.4037; hit20 0.6158 vs 0.5995; 5/10D diff ['+0.46', '+0.36']; non-overlap median20 1.7906 vs A 1.9699
- F: **FAIL** — median20 2.7474 vs A 2.4037; hit20 0.6128 vs 0.5995; 5/10D diff ['+0.17', '+0.24']; non-overlap median20 1.8433 vs A 1.9699

## Overall RESULT: COMPLETED

PASS = candidate for OOS/robustness validation, nic víc. Zakázaná tvrzení: edge confirmed / production-ready / tradable strategy.
