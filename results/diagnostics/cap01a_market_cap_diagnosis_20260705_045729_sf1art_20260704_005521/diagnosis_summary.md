# CAP-01A Market Cap Diagnosis Summary

Read-only diagnóza příčiny MARKET_CAP_SUSPECT. Nemění produkční CAP-01 formuli, bucket logiku ani tolerance.

- generated_at_utc: 2026-07-05T04:57:29.525604+00:00
- snapshot_id: `sf1art_20260704_005521`
- candidate-days: 1144 | suspect: 493
- tolerance (CAP-01, referenční): 25.0 %

## DIAGNOSIS RESULT: ANCHOR_DATE_MISMATCH

- suspect ratio_candidate ≈1: 0.0%
- anchor_adjusted ≈1: 96.3%
- sharefactor× ≈1: 0.0% | sharefactor/ ≈1: 0.0%

## Ratio summary (suspect vs all)

| metric | scope | n | median | p05 | p95 | min | max |
|---|---|---|---|---|---|---|---|
| ratio_candidate | suspect | 493 | 1.4192 | 1.2608 | 2.6893 | 1.2501 | 13.9377 |
| ratio_candidate | all | 1143 | 1.2154 | 1.0 | 1.7804 | 0.8266 | 13.9377 |
| ratio_sharefactor_mult | suspect | 493 | 1.4192 | 1.2608 | 2.6893 | 1.2501 | 13.9377 |
| ratio_sharefactor_mult | all | 1143 | 1.2154 | 1.0 | 1.7804 | 0.8266 | 13.9377 |
| ratio_sharefactor_div | suspect | 493 | 1.4192 | 1.2608 | 2.6893 | 1.2501 | 13.9377 |
| ratio_sharefactor_div | all | 1143 | 1.2154 | 1.0 | 1.7804 | 0.8266 | 13.9377 |
| price_ratio | suspect | 493 | 1.4021 | 1.258 | 1.9495 | 1.137 | 2.9766 |
| price_ratio | all | 1143 | 1.2139 | 1.0 | 1.7157 | 0.8266 | 2.9766 |
| anchor_adjusted_ratio | suspect | 493 | 1.0 | 1.0 | 1.0 | 1.0 | 10.0 |
| anchor_adjusted_ratio | all | 1143 | 1.0 | 1.0 | 1.0 | 0.9367 | 10.0 |
| relative_diff_pct | suspect | 493 | 41.92 | 26.08 | 168.924 | 25.01 | 1293.77 |
| relative_diff_pct | all | 1143 | 21.54 | 0.664 | 78.036 | 0.0 | 1293.77 |

## Korelace

- relative_diff_pct~staleness_days: 0.2132
- ratio_candidate~price_ratio: 0.2717

## Suspect podle staleness bucketu

- 0-90: 459
- 91-180: 34
- >180: 0

## Top 30 suspect conidů

| conid | ticker | suspect_count |
|---|---|---|
| 270639 | INTC | 40 |
| 9939 | MU | 34 |
| 4391 | AMD | 30 |
| 201113895 | LITE | 22 |
| 9282 | LUV | 15 |
| 13681 | WDC | 15 |
| 491932113 | STX | 14 |
| 732440574 | LRCX | 14 |
| 12729 | TER | 13 |
| 41045553 | CIEN | 13 |
| 8677881 | ON | 12 |
| 266093 | AMAT | 12 |
| 584127832 | COHR | 12 |
| 474515500 | APA | 11 |
| 346218218 | DELL | 11 |
| 370757467 | CRWD | 10 |
| 731466419 | SMCI | 9 |
| 49921110 | NTAP | 8 |
| 47965865 | SATS | 8 |
| 10880 | OXY | 8 |
| 270957 | KLAC | 8 |
| 72529783 | GNRC | 8 |
| 292491487 | TPR | 8 |
| 12200 | SLB | 7 |
| 4347 | ALB | 7 |
| 481863646 | APP | 7 |
| 79498203 | UAL | 6 |
| 76792991 | TSLA | 6 |
| 77791077 | NXPI | 6 |
| 7655 | GLW | 5 |

## Interpretace testů

- anchor_adjusted_ratio ≈ 1 → vendor marketcap vztažen k datekey, ne candidate_date (anchor-date mismatch; market cap výpočet OK)
- ratio_sharefactor_mult/div ≈ 1 → chybějící sharefactor korekce
- žádný ≈ 1 → cena/shares nekompatibilní (source change)
