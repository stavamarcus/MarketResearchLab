# MLE-RECON-01B — Rank Diagnostics

## clean_day (2026-03-20)
- archive_ranked_count: 497
- recon_ranked_count: 503
- intersection_count: 497
- archive_only_ranked: []
- recon_only_ranked: ['BF.B', 'BRK.B', 'EXE', 'PSKY', 'Q', 'SNDK']
- ret_exact_but_rank_mismatch: 492
- ret_mismatch_and_rank_mismatch: 4
- rank_diff_distribution: {'min': -32, 'max': 51, 'mean': 3.3, 'abs_le_1': 106, 'abs_le_5': 493, 'abs_gt_50': 1, 'zero': 0}

### Clean re-ranking (bez exceptions)
- clean_ticker_count: 488
- clean_rank_match: 192
- clean_rank_mismatch: 296
- clean_match_rate: 0.3934

- top clean mismatch:
  - NEM: arch=480 recon=482 diff=2
  - KHC: arch=464 recon=466 diff=2
  - CVNA: arch=456 recon=458 diff=2
  - BA: arch=477 recon=479 diff=2
  - LOW: arch=446 recon=448 diff=2
  - SJM: arch=445 recon=447 diff=2
  - PSA: arch=472 recon=474 diff=2
  - OTIS: arch=447 recon=449 diff=2
  - TTD: arch=481 recon=483 diff=2
  - ADBE: arch=467 recon=469 diff=2
  - CEG: arch=459 recon=461 diff=2
  - SBAC: arch=454 recon=456 diff=2
  - DG: arch=475 recon=477 diff=2
  - EXR: arch=449 recon=451 diff=2
  - CTAS: arch=462 recon=464 diff=2

### Top 15 rank_diff (s exceptions)

- NWS: arch_rank=96 recon_rank=147 diff=51 arch_ret=-1.12 recon_ret=-2.32 [identity_alias_class_mismatch]
- FOX: arch_rank=215 recon_rank=183 diff=-32 arch_ret=-3.92 recon_ret=-3.28 [identity_alias_class_mismatch]
- SMCI: arch_rank=497 recon_rank=503 diff=6 arch_ret=-34.43 recon_ret=-34.43 [clean]
- GOOG: arch_rank=65 recon_rank=59 diff=-6 arch_ret=0.16 recon_ret=0.83 [identity_alias_class_mismatch]
- NEM: arch_rank=489 recon_rank=494 diff=5 arch_ret=-17.62 recon_ret=-17.62 [clean]
- FTV: arch_rank=208 recon_rank=213 diff=5 arch_ret=-3.78 recon_ret=-3.78 [clean]
- ARES: arch_rank=206 recon_rank=211 diff=5 arch_ret=-3.76 recon_ret=-3.76 [clean]
- MCK: arch_rank=195 recon_rank=200 diff=5 arch_ret=-3.64 recon_ret=-3.64 [clean]
- KHC: arch_rank=473 recon_rank=478 diff=5 arch_ret=-12.1 recon_ret=-12.1 [clean]
- CVNA: arch_rank=465 recon_rank=470 diff=5 arch_ret=-11.46 recon_ret=-11.46 [clean]
- BA: arch_rank=486 recon_rank=491 diff=5 arch_ret=-15.57 recon_ret=-15.57 [clean]
- LOW: arch_rank=455 recon_rank=460 diff=5 arch_ret=-10.82 recon_ret=-10.82 [clean]
- SJM: arch_rank=454 recon_rank=459 diff=5 arch_ret=-10.65 recon_ret=-10.65 [clean]
- PSA: arch_rank=481 recon_rank=486 diff=5 arch_ret=-13.74 recon_ret=-13.74 [clean]
- OTIS: arch_rank=456 recon_rank=461 diff=5 arch_ret=-10.85 recon_ret=-10.85 [clean]

## contaminated_day (2026-06-12)
- archive_ranked_count: 497
- recon_ranked_count: 503
- intersection_count: 497
- archive_only_ranked: []
- recon_only_ranked: ['BF.B', 'BRK.B', 'EXE', 'PSKY', 'Q', 'SNDK']
- ret_exact_but_rank_mismatch: 484
- ret_mismatch_and_rank_mismatch: 12
- rank_diff_distribution: {'min': -496, 'max': 51, 'mean': 2.93, 'abs_le_1': 52, 'abs_le_5': 404, 'abs_gt_50': 2, 'zero': 0}

### Clean re-ranking (bez exceptions)
- clean_ticker_count: 488
- clean_rank_match: 72
- clean_rank_mismatch: 416
- clean_match_rate: 0.1475

- top clean mismatch:
  - FITB: arch=17 recon=66 diff=49
  - NEM: arch=455 recon=457 diff=2
  - MCO: arch=365 recon=367 diff=2
  - CCI: arch=306 recon=308 diff=2
  - IQV: arch=342 recon=344 diff=2
  - BMY: arch=335 recon=337 diff=2
  - CVX: arch=226 recon=228 diff=2
  - KHC: arch=273 recon=275 diff=2
  - REGN: arch=343 recon=345 diff=2
  - VTR: arch=325 recon=327 diff=2
  - PPL: arch=287 recon=289 diff=2
  - LII: arch=259 recon=261 diff=2
  - MLM: arch=351 recon=353 diff=2
  - HIG: arch=262 recon=264 diff=2
  - CMG: arch=293 recon=295 diff=2

### Top 15 rank_diff (s exceptions)

- KLAC: arch_rank=497 recon_rank=1 diff=-496 arch_ret=-86.75 recon_ret=32.45 [corporate_action_cache_artifact]
- FITB: arch_rank=17 recon_rank=68 diff=51 arch_ret=9.61 recon_ret=6.99 [clean]
- FOX: arch_rank=225 recon_rank=209 diff=-16 arch_ret=2.67 recon_ret=3.02 [identity_alias_class_mismatch]
- GOOG: arch_rank=420 recon_rank=436 diff=16 arch_ret=-4.85 recon_ret=-5.43 [identity_alias_class_mismatch]
- TYL: arch_rank=416 recon_rank=424 diff=8 arch_ret=-4.57 recon_ret=-4.57 [clean]
- NEM: arch_rank=463 recon_rank=470 diff=7 arch_ret=-8.72 recon_ret=-8.72 [clean]
- CRWD: arch_rank=446 recon_rank=453 diff=7 arch_ret=-6.59 recon_ret=-6.59 [corporate_action_cache_artifact]
- ORCL: arch_rank=492 recon_rank=499 diff=7 arch_ret=-18.45 recon_ret=-18.45 [clean]
- NTAP: arch_rank=454 recon_rank=461 diff=7 arch_ret=-7.28 recon_ret=-7.28 [clean]
- PLTR: arch_rank=491 recon_rank=498 diff=7 arch_ret=-18.24 recon_ret=-18.24 [clean]
- CVNA: arch_rank=478 recon_rank=485 diff=7 arch_ret=-12.19 recon_ret=-12.19 [clean]
- TTD: arch_rank=470 recon_rank=477 diff=7 arch_ret=-10.58 recon_ret=-10.58 [clean]
- FSLR: arch_rank=479 recon_rank=486 diff=7 arch_ret=-12.87 recon_ret=-12.87 [clean]
- CEG: arch_rank=476 recon_rank=483 diff=7 arch_ret=-11.81 recon_ret=-11.81 [clean]
- TRMB: arch_rank=471 recon_rank=478 diff=7 arch_ret=-10.62 recon_ret=-10.62 [clean]

## Interpretace

- clean_match_rate ~1.0 -> rank mismatch = amplification efekt
  exception tickeru (ne bug).
- clean_match_rate nizky -> bug v universe/rank/porovnani.
- ranked counts nesedi -> ranking universe / NaN / missing price.
- ret sedi ale rank ne i po clean -> comparator bug.
