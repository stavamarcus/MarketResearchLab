# FUND-03 Coverage Audit Summary

FUND-03 není edge test a neříká nic o profitabilitě fundamentals.
Měří pouze datové pokrytí PIT SF1 ART snapshotu nad candidate-days.

- generated_at_utc: 2026-07-04T22:53:16.025132+00:00
- run_id: `fund03_coverage_20260704_225314_sf1art_20260704_005521`
- input: `results\diagnostics\fund03_candidate_days_20260704_225140\candidate_days.csv`
- snapshot_id: `sf1art_20260704_005521`
- snapshot_data_hash: `8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0`
- contract_versions: `{'identity_contract_version': 'v1.0', 'provider_contract_version': 'v1.0'}`

## Coverage

- candidate-days count: 1144
- unique conids: 151
- date range: 2025-07-09 → 2026-06-27
- included: 1144
- excluded: 0
- coverage_pct: 100.0
- alias_count: 1
- alias_pct: 0.09
- stale_warnings (>180d): 0
- identity_excluded: 0
- missing_sf1: 0
- no_asof_date: 0
- UNKNOWN_ERROR: 0

## Reason code distribution

| reason_code | count |
|---|---|
| IDENTITY_MISSING | 0 |
| IDENTITY_AMBIGUOUS | 0 |
| IDENTITY_TIER_NOT_ALLOWED | 0 |
| NO_SF1_ROWS | 0 |
| NO_SF1_ASOF_DATE | 0 |
| ALIAS_PRICE_FIELD_FORBIDDEN | 0 |
| CACHE_MISSING | 0 |
| SCHEMA_MISMATCH | 0 |
| UNKNOWN_ERROR | 0 |

## Staleness buckets

| bucket | count |
|---|---|
| 0-90d | 1100 |
| 91-180d | 44 |
| >180d | 0 |
| missing/excluded | 0 |

## RESULT: PASS
