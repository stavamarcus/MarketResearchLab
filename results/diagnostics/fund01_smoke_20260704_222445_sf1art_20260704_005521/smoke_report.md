# MRL-FUND-01 Fundamental Smoke Integration Report

- generated_at_utc: 2026-07-04T22:24:45.473165+00:00
- run_id: `fund01_smoke_20260704_222445_sf1art_20260704_005521`
- snapshot_id: `sf1art_20260704_005521`
- snapshot_data_hash: `8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0`
- contract_versions: `{'identity_contract_version': 'v1.0', 'provider_contract_version': 'v1.0'}`
- candidate_date: 2026-07-04
- candidate-days count: 6
- included: 4
- excluded: 2
- coverage_pct: 66.67
- alias_count: 1
- staleness warnings: 0

## Reason code distribution

| reason_code | count |
|---|---|
| IDENTITY_MISSING | 1 |
| IDENTITY_AMBIGUOUS | 0 |
| IDENTITY_TIER_NOT_ALLOWED | 0 |
| NO_SF1_ROWS | 0 |
| NO_SF1_ASOF_DATE | 1 |
| ALIAS_PRICE_FIELD_FORBIDDEN | 0 |
| CACHE_MISSING | 0 |
| SCHEMA_MISMATCH | 0 |
| UNKNOWN_ERROR | 0 |

## Checks

| check | status | detail |
|---|---|---|
| 1:1 řádky (včetně duplicity) | PASS | output rows=6 |
| AAPL/GOOG/LYB OK (4 řádky) | PASS | OK=4 |
| PIT: sf1_datekey <= candidate_date | PASS | - |
| alias flag zachován (GOOG) | PASS | - |
| EXCLUDED reason codes | PASS | reasons=['IDENTITY_MISSING', 'NO_SF1_ASOF_DATE'] |
| EXCLUDED řádky nedropnuty, NaN fundamentals | PASS | - |
| coverage requested = 6 | PASS | requested=6 |
| coverage returned = 4 | PASS | returned=4 |
| UNKNOWN_ERROR == 0 | PASS | - |
| price-derived pole mimo output | PASS | - |

- coverage report: `C:\Users\stava\Projects\MarketResearchLab\results\diagnostics\fund01_smoke_20260704_222445_sf1art_20260704_005521\coverage_fund01_smoke_20260704_222445_sf1art_20260704_005521.md`

## RESULT: PASS
