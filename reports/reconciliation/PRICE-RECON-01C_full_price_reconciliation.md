# PRICE-RECON-01C — Full Price Reconciliation (opraveny classifier)

## Overall: WARN

Overlap: 2025-07-09 -> 2026-06-27

## Kategorie

- exact_match: 354
- pass_micro: 125
- warn: 15
- corporate_action_cache_artifact: 5
- identity_alias_class_mismatch: 3
- needs_manual_review_or_unmapped_adjustment_artifact: 1
- true_reconciliation_fail: 0

## Souhrn

- tested_files: 503
- matched_files: 503
- total_overlap_rows: 122193
- missing_old_mdsm: 0
- missing_new_view: 0

## Flagged soubory (FAIL_CANDIDATE + WARN)

- 270957_D1.parquet: mean=1149.483578 max=2170.476 match=0.041 [corporate_action_cache_artifact] CA={'action': 'split', 'date': '2026-06-12', 'value': '10.0'}
- 370757467_D1.parquet: mean=365.051238 max=586.628 match=0.0 [corporate_action_cache_artifact] CA={'action': 'split', 'date': '2026-07-02', 'value': '4.0'}
- 4350_D1.parquet: mean=221.652705 max=253.1 match=0.0 [corporate_action_cache_artifact] CA={'action': 'split', 'date': '2026-06-29', 'value': '0.5'}
- 887235923_D1.parquet: mean=44.85 max=143.4 match=0.6639 [corporate_action_cache_artifact] CA={'action': 'spinoffdividend', 'date': '2025-11-03', 'value': '142.50014'}
- 4886_D1.parquet: mean=23.325246 max=41.94 match=0.3893 [needs_manual_review_or_unmapped_adjustment_artifact] boundary=2026-02-10
- 748351585_D1.parquet: mean=8.965 max=13.56 match=0.2459 [corporate_action_cache_artifact] CA={'action': 'spinoffdividend', 'date': '2026-04-01', 'value': '10.6167'}
- 356858007_D1.parquet: mean=6.125984 max=9.21 match=0.0 [identity_alias_class_mismatch] alias=FOX->FOXA
- 129348130_D1.parquet: mean=3.719631 max=4.82 match=0.0 [identity_alias_class_mismatch] alias=NWS->NWSA
- 208813720_D1.parquet: mean=1.130656 max=4.19 match=0.1516 [identity_alias_class_mismatch] alias=GOOG->GOOGL

## Volume (zvlast, ne FAIL gate)

- prumer volume_mean_abs_pct_diff: 175.3004

## CA logika (opravena)

- price-impact CA: ['split', 'adrratiosplit', 'spinoff', 'spinoffdividend', 'merger', 'acquisition']
- dividend NENI price-impact pro scale diff.
- CA okno: +-15 dni od diff dat nebo boundary.
- CA lookup okno: 2025-01-01..2026-07-15 (presah za overlap).
- alias: alias_flag neprazdny nebo ticker!=sharadar_ticker.

## Vyhrady

- true_reconciliation_fail se NEudeluje unahleene; large diff
  bez alias/CA -> needs_manual_review (BDX case).
- volume rozdil = vendor, ne FAIL gate.
