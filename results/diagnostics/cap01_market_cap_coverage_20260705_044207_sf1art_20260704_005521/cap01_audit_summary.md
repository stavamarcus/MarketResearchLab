# CAP-01 Market Cap Coverage Audit Summary

CAP-01 není performance test — žádné forward returns, žádná profitabilita.

- generated_at_utc: 2026-07-05T04:42:07.910140+00:00
- run_id: `cap01_market_cap_coverage_20260705_044207_sf1art_20260704_005521`
- input: `results\diagnostics\fund03_candidate_days_20260704_225140\candidate_days.csv`
- snapshot_id: `sf1art_20260704_005521` (data_hash `8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0`)
- sharefactor available: True
- sanity anchor available: True
- tolerance (pre-registrováno): 25.0 % | boundary band ±10.0 %

## Coverage

- candidate-days: 1144 | unique conids: 151
- date range: 2025-07-09 → 2026-06-27
- market_cap_available (OK): 651
- missing (price/shares): 3 / 0
- suspect: 490 | invalid: 0 | unknown: 0
- coverage_pct: 56.91
- candidate-days per date: min=1 median=5.0 max=10
- boundary sensitivity (±10.0 % od hranice): 81 OK řádků

## Reason code distribution

| reason_code | count |
|---|---|
| MARKET_CAP_OK | 651 |
| MARKET_CAP_PRICE_MISSING | 3 |
| MARKET_CAP_SHARES_MISSING | 0 |
| MARKET_CAP_SUSPECT | 490 |
| MARKET_CAP_INVALID | 0 |
| UNKNOWN_ERROR | 0 |

## Bucket distribution

| market_cap_bucket | candidate_days | unique_conids | unique_dates |
|---|---|---|---|
| Large-high | 223 | 53 | 152 |
| Large-low | 293 | 72 | 170 |
| Mega | 118 | 26 | 90 |
| Mid | 17 | 7 | 15 |
| UNBUCKETED | 493 | 77 | 180 |

## Top repeated conids per bucket

| bucket | conid | ticker | count |
|---|---|---|---|
| Large-high | 402783527 | VRT | 15 |
| Large-high | 491932113 | STX | 14 |
| Large-high | 70236214 | FTNT | 11 |
| Large-high | 11520 | RCL | 9 |
| Large-high | 7655 | GLW | 9 |
| Large-low | 6607708 | FIX | 15 |
| Large-low | 7890 | HAL | 13 |
| Large-low | 271568 | MCHP | 13 |
| Large-low | 72529783 | GNRC | 13 |
| Large-low | 12729 | TER | 11 |
| Mega | 9939 | MU | 16 |
| Mega | 4391 | AMD | 14 |
| Mega | 270639 | INTC | 12 |
| Mega | 13272 | UNH | 10 |
| Mega | 9160 | LLY | 8 |
| Mid | 474515500 | APA | 6 |
| Mid | 120643512 | NCLH | 4 |
| Mid | 2730877 | CRL | 2 |
| Mid | 3655640 | HSIC | 2 |
| Mid | 88292752 | MOS | 1 |
| UNBUCKETED | 270639 | INTC | 40 |
| UNBUCKETED | 9939 | MU | 34 |
| UNBUCKETED | 4391 | AMD | 30 |
| UNBUCKETED | 201113895 | LITE | 22 |
| UNBUCKETED | 9282 | LUV | 15 |

## Sanity anchor

- relative_diff_pct: median=21.52 p95=78.15 max=1293.77
- median(computed/vendor) ratio: 1.215

## RESULT: STOP

Důvody:

- coverage 56.91 < 90
