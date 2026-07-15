# PRICE-RECON-01 — Full Price Reconciliation

## Overall: FAIL

Overlap: 2025-07-09 -> 2026-06-27

## Souhrn

- tested_files: 503
- matched_files: 503
- missing_old_mdsm: 0
- missing_new_view: 0
- total_overlap_rows: 122193
- exact_match_files: 354
- pass_micro_files: 125
- warn_files: 15
- fail_candidate_files: 9
- corporate_action_cache_artifact_files: 0
- true_reconciliation_fail_files: 9

## TRUE RECONCILIATION FAILS

- 129348130_D1.parquet
- 208813720_D1.parquet
- 270957_D1.parquet
- 356858007_D1.parquet
- 370757467_D1.parquet
- 4350_D1.parquet
- 4886_D1.parquet
- 748351585_D1.parquet
- 887235923_D1.parquet

## Top 20 largest close diffs

- 270957_D1.parquet: mean=1149.483578 max=2170.476 match=0.041 [true_reconciliation_fail]
- 370757467_D1.parquet: mean=365.051238 max=586.628 match=0.0 [true_reconciliation_fail]
- 4350_D1.parquet: mean=221.652705 max=253.1 match=0.0 [true_reconciliation_fail]
- 887235923_D1.parquet: mean=44.85 max=143.4 match=0.6639 [true_reconciliation_fail]
- 4886_D1.parquet: mean=23.325246 max=41.94 match=0.3893 [true_reconciliation_fail]
- 748351585_D1.parquet: mean=8.965 max=13.56 match=0.2459 [true_reconciliation_fail]
- 356858007_D1.parquet: mean=6.125984 max=9.21 match=0.0 [true_reconciliation_fail]
- 129348130_D1.parquet: mean=3.719631 max=4.82 match=0.0 [true_reconciliation_fail]
- 208813720_D1.parquet: mean=1.130656 max=4.19 match=0.1516 [true_reconciliation_fail]
- 269315_D1.parquet: mean=0.01 max=2.43 match=0.9959 [WARN]
- 267748_D1.parquet: mean=0.989713 max=2.26 match=0.4918 [WARN]
- 269318_D1.parquet: mean=0.011619 max=1.31 match=0.9877 [WARN]
- 491932113_D1.parquet: mean=0.002377 max=0.55 match=1.0 [WARN]
- 95703740_D1.parquet: mean=0.001762 max=0.43 match=0.9959 [WARN]
- 47965865_D1.parquet: mean=0.002377 max=0.42 match=0.9959 [WARN]
- 691984365_D1.parquet: mean=0.0025 max=0.25 match=1.0 [WARN]
- 274499_D1.parquet: mean=0.000922 max=0.21 match=1.0 [WARN]
- 10672_D1.parquet: mean=0.000783 max=0.191 match=0.9959 [WARN]
- 265598_D1.parquet: mean=0.000484 max=0.118 match=1.0 [WARN]
- 8377_D1.parquet: mean=0.001025 max=0.09 match=1.0 [WARN]

## Volume (zvlast, ne FAIL gate)

- prumer volume_mean_abs_pct_diff: 175.300386
- nejvyssi volume_max_abs_pct_diff: 2769.937724 (129348130_D1.parquet)

## Prahy

- PASS: close mean<0.01 AND max<0.05
- WARN: mean<0.01 ale max>=0.05, nebo 0.01<=mean<1.0
- FAIL_CANDIDATE: mean>=1.0 nebo max>=5.0
  -> artifact (CA poblizu) nebo true_reconciliation_fail

## Vyhrady

- CA okno: +-ca_window kalendarnich dni (ne trading).
- artifact detekce zavisi na ACTIONS labelech + identity most.
- volume rozdily = vendor rozdil, ne cenovy nesoulad.
