# MLE-RECON-01D — Archive-Ranked Intersection

## Verdikt: WARN

Range: 2025-07-09 .. 2026-07-04

Metoda: recon rank prepocitan JEN mezi archive-ranked tickery
per date/lookback. Tie-break: universe order.

## A) archive_ranked_raw

- compared_cells: 1366717
- archive_ranked: min=493 median=497 max=499
- recon_missing: 0
- ret_exact_rate: 0.975064
- ret_micro_rate: 0.002384
- ret_mismatch_rate: 0.022552
- rank_exact_rate: 0.778613
- gate10_rank_exact_rate: 0.751914
- top10_overlap_rate: 0.9908
- mismatch_by_category: {'corporate_action_cache_artifact': 330, 'clean': 29723, 'needs_manual_review_or_unmapped_adjustment_artifact': 73, 'identity_alias_class_mismatch': 698}

### Top mismatches (gate10)

- 2026-06-24 DD L10: arch_rank=1 recon_rank=338 arch_ret=192.86 recon_ret=-2.38 [corporate_action_cache_artifact]
- 2026-06-25 DD L10: arch_rank=1 recon_rank=251 arch_ret=192.86 recon_ret=1.94 [corporate_action_cache_artifact]
- 2026-06-22 KLAC L10: arch_rank=497 recon_rank=5 arch_ret=-86.05 recon_ret=39.52 [corporate_action_cache_artifact]
- 2026-06-12 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.75 recon_ret=32.45 [corporate_action_cache_artifact]
- 2026-06-13 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.75 recon_ret=32.45 [corporate_action_cache_artifact]
- 2026-06-15 KLAC L10: arch_rank=497 recon_rank=1 arch_ret=-86.78 recon_ret=32.17 [corporate_action_cache_artifact]
- 2026-06-25 KLAC L10: arch_rank=497 recon_rank=18 arch_ret=-88.76 recon_ret=21.18 [corporate_action_cache_artifact]
- 2026-06-18 KLAC L10: arch_rank=497 recon_rank=5 arch_ret=-87.82 recon_ret=21.8 [corporate_action_cache_artifact]
- 2026-06-23 KLAC L10: arch_rank=497 recon_rank=8 arch_ret=-88.4 recon_ret=15.98 [corporate_action_cache_artifact]
- 2026-06-16 KLAC L10: arch_rank=497 recon_rank=4 arch_ret=-86.78 recon_ret=16.04 [corporate_action_cache_artifact]
- 2026-06-24 KLAC L10: arch_rank=497 recon_rank=19 arch_ret=-88.76 recon_ret=12.41 [corporate_action_cache_artifact]
- 2026-06-17 KLAC L10: arch_rank=497 recon_rank=15 arch_ret=-88.77 recon_ret=12.34 [corporate_action_cache_artifact]
- 2026-06-26 KLAC L10: arch_rank=493 recon_rank=219 arch_ret=-89.69 recon_ret=3.1 [corporate_action_cache_artifact]
- 2026-06-27 KLAC L10: arch_rank=496 recon_rank=220 arch_ret=-89.69 recon_ret=3.1 [corporate_action_cache_artifact]
- 2026-07-04 CRWD L10: arch_rank=497 recon_rank=32 arch_ret=-71.6 recon_ret=13.61 [corporate_action_cache_artifact]
- 2025-11-13 DD L10: arch_rank=4 recon_rank=497 arch_ret=19.17 recon_ret=-50.17 [corporate_action_cache_artifact]
- 2025-11-05 DD L10: arch_rank=13 recon_rank=497 arch_ret=18.9 recon_ret=-50.28 [corporate_action_cache_artifact]
- 2025-11-12 DD L10: arch_rank=8 recon_rank=497 arch_ret=18.71 recon_ret=-50.35 [corporate_action_cache_artifact]
- 2025-11-10 DD L10: arch_rank=9 recon_rank=497 arch_ret=18.25 recon_ret=-50.55 [corporate_action_cache_artifact]
- 2025-11-11 DD L10: arch_rank=10 recon_rank=497 arch_ret=17.96 recon_ret=-50.67 [corporate_action_cache_artifact]

## B) exception_neutral_clean

- compared_cells: 1342011
- archive_ranked: min=486 median=488 max=490
- recon_missing: 0
- ret_exact_rate: 0.982796
- ret_micro_rate: 0.001759
- ret_mismatch_rate: 0.015445
- rank_exact_rate: 0.963704
- gate10_rank_exact_rate: 0.96214
- top10_overlap_rate: 0.9964
- mismatch_by_category: {'clean': 4619}

### Top mismatches (gate10)

- 2026-06-25 SMCI L10: arch_rank=484 recon_rank=97 arch_ret=-20.15 recon_ret=8.23 [clean]
- 2026-06-25 TECH L10: arch_rank=50 recon_rank=5 arch_ret=8.22 recon_ret=34.67 [clean]
- 2025-07-10 FTV L10: arch_rank=372 recon_rank=487 arch_ret=0.49 recon_ret=-24.29 [clean]
- 2025-07-09 FTV L10: arch_rank=368 recon_rank=487 arch_ret=-0.47 recon_ret=-25.02 [clean]
- 2026-06-16 COHR L10: arch_rank=10 recon_rank=452 arch_ret=14.04 recon_ret=-10.33 [clean]
- 2025-07-11 FTV L10: arch_rank=412 recon_rank=487 arch_ret=-1.81 recon_ret=-26.02 [clean]
- 2026-06-25 MU L10: arch_rank=20 recon_rank=2 arch_ret=12.03 recon_ret=36.07 [clean]
- 2025-07-14 FTV L10: arch_rank=448 recon_rank=487 arch_ret=-3.28 recon_ret=-27.14 [clean]
- 2026-06-16 LITE L10: arch_rank=122 recon_rank=475 arch_ret=5.77 recon_ret=-14.94 [clean]
- 2026-06-25 TER L10: arch_rank=10 recon_rank=3 arch_ret=15.71 recon_ret=35.78 [clean]
- 2026-06-25 CASY L10: arch_rank=97 recon_rank=468 arch_ret=5.28 recon_ret=-14.3 [clean]
- 2026-06-30 FOXA L10: arch_rank=486 recon_rank=377 arch_ret=-23.48 recon_ret=-4.75 [clean]
- 2026-06-16 HPE L10: arch_rank=196 recon_rank=470 arch_ret=4.3 recon_ret=-13.84 [clean]
- 2026-06-30 WDC L10: arch_rank=15 recon_rank=333 arch_ret=15.8 recon_ret=-2.27 [clean]
- 2026-06-16 GLW L10: arch_rank=99 recon_rank=464 arch_ret=6.33 recon_ret=-11.47 [clean]
- 2026-06-25 GLW L10: arch_rank=5 recon_rank=4 arch_ret=18.33 recon_ret=35.58 [clean]
- 2026-06-25 AMAT L10: arch_rank=7 recon_rank=6 arch_ret=17.98 recon_ret=34.4 [clean]
- 2026-06-16 MPWR L10: arch_rank=81 recon_rank=442 arch_ret=7.13 recon_ret=-7.77 [clean]
- 2026-06-25 CAT L10: arch_rank=49 recon_rank=14 arch_ret=8.72 recon_ret=23.46 [clean]
- 2026-06-25 GNRC L10: arch_rank=48 recon_rank=15 arch_ret=8.87 recon_ret=23.44 [clean]

## Interpretace

- CLEAN gate10_rank_exact vysoky + ret_exact/micro >=99.5% ->
  MLE rank logika + Sharadar ceny sedi mimo znale artefakty.
- zbytkove clean mismatchy (kategorie 'clean') = nevysvetlene,
  nutna dalsi analyza.

## Vyhrady

- recon rank pocitan zde (ne compute_rank_matrix), vzorec
  identicky s MLE engine, ranking universe = archive_set.
- tie-break: universe order (replikace MLE dict order).
- close_past: spolecny index z DATA-06 union (ne per-ticker).
  Muze se lisit od MLE price_matrix pri chybejicich dnech.
