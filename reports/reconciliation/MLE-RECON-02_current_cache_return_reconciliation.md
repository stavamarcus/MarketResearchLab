# MLE-RECON-02 — Current-Cache Return Reconciliation

## Verdikt: FAIL

Range: 2025-07-09 .. 2026-07-04 (250 dni)

Hlavni reference: SOUCASNA MDSM cache vs DATA-06 (stejny MLE engine).
Archiv jen sekundarni audit.

- top10_overlap_rate: 0.9628
- mdsm_only_ranked_total: 5
- data06_only_ranked_total: 514

## Per-lookback (MDSM current vs DATA-06)

| lookback | compared | ret_exact | ret_micro | ret_mismatch | rank_exact |
|---|---|---|---|---|---|
| 1d | 125180 | 0.987889 | 0.00143 | 0.010681 | 0.434135 |
| 2d | 125176 | 0.987697 | 0.00171 | 0.010593 | 0.431584 |
| 3d | 125172 | 0.987465 | 0.002021 | 0.010514 | 0.435201 |
| 4d | 125168 | 0.987409 | 0.002221 | 0.01037 | 0.42725 |
| 5d | 125164 | 0.987337 | 0.002349 | 0.010314 | 0.414496 |
| 6d | 125160 | 0.9874 | 0.002325 | 0.010275 | 0.410019 |
| 7d | 125156 | 0.987376 | 0.002461 | 0.010163 | 0.401435 |
| 8d | 125152 | 0.987096 | 0.002621 | 0.010283 | 0.39166 |
| 9d | 125148 | 0.98684 | 0.002709 | 0.010452 | 0.373869 |
| 10d | 125144 | 0.986831 | 0.002997 | 0.010172 | 0.367225 |
| 20d | 125104 | 0.986148 | 0.003245 | 0.010607 | 0.329558 |

## Gate (lookback 10)

- mismatch_total: 79188
- mismatch_by_category: {'corporate_action_cache_artifact': 786, 'clean': 77444, 'needs_manual_review_or_unmapped_adjustment_artifact': 155, 'identity_alias_class_mismatch': 713, 'insufficient_history_not_in_archive': 90}

### Top mismatches (DATA-06 vs MDSM current)

- 2026-06-22 KLAC: mdsm_rank=499 data06_rank=6 mdsm_ret=-86.05 data06_ret=39.52 [corporate_action_cache_artifact]
- 2026-06-12 KLAC: mdsm_rank=499 data06_rank=1 mdsm_ret=-86.75 data06_ret=32.45 [corporate_action_cache_artifact]
- 2026-06-13 KLAC: mdsm_rank=499 data06_rank=1 mdsm_ret=-86.75 data06_ret=32.45 [corporate_action_cache_artifact]
- 2026-06-15 KLAC: mdsm_rank=499 data06_rank=1 mdsm_ret=-86.78 data06_ret=32.17 [corporate_action_cache_artifact]
- 2026-06-18 KLAC: mdsm_rank=499 data06_rank=6 mdsm_ret=-87.82 data06_ret=21.8 [corporate_action_cache_artifact]
- 2026-06-25 KLAC: mdsm_rank=499 data06_rank=19 mdsm_ret=-87.88 data06_ret=21.18 [corporate_action_cache_artifact]
- 2026-06-16 KLAC: mdsm_rank=499 data06_rank=4 mdsm_ret=-88.4 data06_ret=16.04 [corporate_action_cache_artifact]
- 2026-06-23 KLAC: mdsm_rank=499 data06_rank=9 mdsm_ret=-88.4 data06_ret=15.98 [corporate_action_cache_artifact]
- 2026-06-24 KLAC: mdsm_rank=499 data06_rank=20 mdsm_ret=-88.76 data06_ret=12.41 [corporate_action_cache_artifact]
- 2026-06-17 KLAC: mdsm_rank=499 data06_rank=15 mdsm_ret=-88.77 data06_ret=12.34 [corporate_action_cache_artifact]
- 2026-06-26 KLAC: mdsm_rank=499 data06_rank=223 mdsm_ret=-89.69 data06_ret=3.1 [corporate_action_cache_artifact]
- 2026-06-27 KLAC: mdsm_rank=499 data06_rank=223 mdsm_ret=-89.69 data06_ret=3.1 [corporate_action_cache_artifact]
- 2026-07-04 CRWD: mdsm_rank=497 data06_rank=32 mdsm_ret=-71.6 data06_ret=13.61 [corporate_action_cache_artifact]
- 2025-11-13 DD: mdsm_rank=4 data06_rank=502 mdsm_ret=19.17 data06_ret=-50.17 [corporate_action_cache_artifact]
- 2025-11-05 DD: mdsm_rank=13 data06_rank=502 mdsm_ret=18.89 data06_ret=-50.28 [corporate_action_cache_artifact]
- 2025-11-12 DD: mdsm_rank=8 data06_rank=502 mdsm_ret=18.71 data06_ret=-50.35 [corporate_action_cache_artifact]
- 2025-11-10 DD: mdsm_rank=9 data06_rank=502 mdsm_ret=18.24 data06_ret=-50.55 [corporate_action_cache_artifact]
- 2025-11-11 DD: mdsm_rank=10 data06_rank=502 mdsm_ret=17.96 data06_ret=-50.67 [corporate_action_cache_artifact]
- 2025-11-07 DD: mdsm_rank=10 data06_rank=502 mdsm_ret=17.47 data06_ret=-50.87 [corporate_action_cache_artifact]
- 2025-11-14 DD: mdsm_rank=4 data06_rank=502 mdsm_ret=16.29 data06_ret=-51.37 [corporate_action_cache_artifact]

## Archive audit (sekundarni)

- archive_compute_mismatch (computed_mdsm==data06, arch se lisi): 1512
- arch_matches_mdsm: 122715
- arch_matches_data06: 121459
- arch_matches_neither: 17

## Interpretace

- ret/rank DATA-06 vs MDSM current cache vysoke -> Sharadar view
  reprodukuje soucasnou MDSM cache (cenova kompatibilita).
- archive_compute_mismatch > 0 -> archiv zastaraly vuci re-adjusted
  cache (ocekavane, ne chyba recon).

## Vyhrady

- MDSM cache range omezeny; dny bez 45d okna v cache preskoceny.
- porovnava se prunik tickeru ranked v OBOU compute.
- 45d okno, tie-break universe order, engine z MLE.
