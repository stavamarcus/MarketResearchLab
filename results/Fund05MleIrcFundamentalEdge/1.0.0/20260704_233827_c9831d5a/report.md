# Fund05MleIrcFundamentalEdge — v1.0.0

**Run ID:** `c9831d5a-340b-4132-937e-caac5ece8fed`
**Datum spuštění:** 2026-07-04 23:38:27 UTC
**Datový rozsah:** 2025-07-09 → 2026-08-01
**Universum:** sp500_rank_calendar

## Hypotéza

Fundamentální kvalita PIT SF1 snapshotu (quality/growth/profitability/leverage filtry s fixními pre-registrovanými prahy) zlepšuje median 20D forward return MLE TOP10 x IRC TOP10 candidate-days oproti baseline.

## Konfigurace

- `candidate_days_csv`: C:\Users\stava\Projects\MarketResearchLab\results\diagnostics\fund03_candidate_days_20260704_225140\candidate_days.csv
- `candidate_days_sha256`: 31747e692a7ab72c38ea5e88569c949ea91038b1e5f692da937583c09e186dd1

**Poznámky:** MRL-FUND-05 first signal-level MLE x IRC x fundamentals run

## Metriky

| Metrika | Hodnota |
|---------|---------|
| overall_result | COMPLETED |
| candidate_days | 1144 |
| coverage_pct_base | 100.0 |
| nominal_N | 1144 |
| unique_conids | 151 |
| unique_dates | 244 |
| status_A | BASELINE |
| status_B | FAIL |
| status_C | FAIL |
| status_D | FAIL |
| status_E | FAIL |
| status_F | FAIL |
| median_20d_A | 2.4037 |
| median_20d_B | 1.8445 |
| median_20d_C | 2.766 |
| median_20d_D | 2.3155 |
| median_20d_E | 2.7516 |
| median_20d_F | 2.7474 |
| spyrel_median_20d_A | 1.8638 |
| spyrel_median_20d_B | 1.2435 |
| spyrel_median_20d_C | 2.178 |
| spyrel_median_20d_D | 2.0324 |
| spyrel_median_20d_E | 2.1564 |
| spyrel_median_20d_F | 2.2422 |
| entry_price_missing | 3 |
| financial_like_in_E | 0 |

## Tabulky

- `tables/candidate_days.csv`
- `tables/fundamentals_output.csv`
- `tables/variant_membership.csv`
- `tables/forward_returns.csv`
- `tables/variant_summary.csv`
- `tables/dependence_top_conids.csv`
- `tables/coverage_base.csv`
- `tables/coverage_prior.csv`

## Summary

FUND-05 signal-level run — COMPLETED. A:BASELINE(med20=2.4037); B:FAIL(med20=1.8445); C:FAIL(med20=2.766); D:FAIL(med20=2.3155); E:FAIL(med20=2.7516); F:FAIL(med20=2.7474). Není obchodovatelná strategie; PASS = kandidát na OOS validaci.

## Reprodukovatelnost

**Result hash:** `22174b3870b80af58b4b07e2cfdd48021178822e3ad484af7fd3d4d96079bd75`
