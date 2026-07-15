# CAP-01 Market Cap Coverage Audit Summary

CAP-01 není performance test — žádné forward returns, žádná profitabilita.

- generated_at_utc: 2026-07-05T05:05:31.505428+00:00
- run_id: `cap01_market_cap_coverage_20260705_050531_sf1art_20260704_005521`
- input: `results\diagnostics\fund03_candidate_days_20260704_225140\candidate_days.csv`
- snapshot_id: `sf1art_20260704_005521` (data_hash `8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0`)
- sharefactor available: True
- sanity anchor available: True
- tolerance (pre-registrováno): 25.0 % | boundary band ±10.0 %

## Coverage

- candidate-days: 1144 | unique conids: 151
- date range: 2025-07-09 → 2026-06-27
- market_cap_available (OK): 1123
- missing (price/shares): 3 / 0
- suspect: 18 | invalid: 0 | unknown: 0
- coverage_pct: 98.16
- candidate-days per date: min=1 median=5.0 max=10
- boundary sensitivity (±10.0 % od hranice): 145 OK řádků

## Reason code distribution

| reason_code | count |
|---|---|
| MARKET_CAP_OK | 1123 |
| MARKET_CAP_PRICE_MISSING | 3 |
| MARKET_CAP_SHARES_MISSING | 0 |
| MARKET_CAP_SUSPECT | 18 |
| MARKET_CAP_INVALID | 0 |
| UNKNOWN_ERROR | 0 |

## Bucket distribution

| market_cap_bucket | candidate_days | unique_conids | unique_dates |
|---|---|---|---|
| Large-high | 355 | 64 | 189 |
| Large-low | 487 | 77 | 215 |
| Mega | 263 | 32 | 129 |
| Mid | 18 | 7 | 16 |
| UNBUCKETED | 21 | 5 | 19 |

## Top repeated conids per bucket

| bucket | conid | ticker | count |
|---|---|---|---|
| Large-high | 491932113 | STX | 21 |
| Large-high | 402783527 | VRT | 19 |
| Large-high | 270639 | INTC | 16 |
| Large-high | 7655 | GLW | 14 |
| Large-high | 32106121 | MPWR | 12 |
| Large-low | 12729 | TER | 22 |
| Large-low | 72529783 | GNRC | 21 |
| Large-low | 201113895 | LITE | 20 |
| Large-low | 8677881 | ON | 19 |
| Large-low | 731466419 | SMCI | 18 |
| Mega | 4391 | AMD | 44 |
| Mega | 9939 | MU | 43 |
| Mega | 270639 | INTC | 38 |
| Mega | 732440574 | LRCX | 14 |
| Mega | 9160 | LLY | 13 |
| Mid | 474515500 | APA | 6 |
| Mid | 120643512 | NCLH | 4 |
| Mid | 2730877 | CRL | 3 |
| Mid | 3655640 | HSIC | 2 |
| Mid | 88292752 | MOS | 1 |
| UNBUCKETED | 370757467 | CRWD | 10 |
| UNBUCKETED | 270957 | KLAC | 8 |
| UNBUCKETED | 9282 | LUV | 1 |
| UNBUCKETED | 79498203 | UAL | 1 |
| UNBUCKETED | 344809106 | MRNA | 1 |

## Sanity anchor

- relative_diff_pct: median=0.00 p95=0.00 max=900.00
- median(computed/vendor) ratio: 1

## RESULT: PASS
