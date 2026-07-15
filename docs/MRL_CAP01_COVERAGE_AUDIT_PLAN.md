# CAP-01 Coverage Audit Plan (plán — nespouštět v CAP-00)

**Účel:** dostupnost a distribuce market cap nad MLE × IRC candidate-days.
ŽÁDNÉ výnosy, žádná profitabilita.

## Vstupy

```text
candidate-days: FUND-03 extraction (deterministic; poslední známý stav
    1 144 | 151 conidů | 2025-07-09 → 2026-06-27); re-extraction povolena
    pouze deterministicky, bez forward-return sloupců, bez edge metrik
snapshot: sf1art_20260704_005521 (pinned) — PODMÍNĚNO ověřením sharesbas
    (source review §2; krok 0 auditu)
MDSM close ceny (canonical price source)
bucket policy: MRL_CAP00_BUCKET_POLICY.md (fixní)
```

## Krok 0 (gate auditu)

Read-only ověření `sharesbas` (+ `sharefactor`) v snapshotu přes
StoreHandle. Chybí → STOP, zpět k PM (nový build = samostatné schválení).

## Metriky (povinné, úplný výčet zadání)

```text
candidate-days count | unique conids | date range
market_cap_available count | missing market_cap count | coverage_pct
bucket distribution (vč. UNBUCKETED a prázdných bucketů)
unique conids per bucket | unique dates per bucket
top repeated conids per bucket
candidate-days per date distribution (min/median/max)
source quality issues: MARKET_CAP_PRICE_MISSING, MARKET_CAP_SHARES_MISSING,
    MARKET_CAP_SUSPECT (sanity anchor mimo pásmo), boundary sensitivity
    (±10 % od hranice)
reason_code distribution (adapter kódy + CAP-interní kategorie výše)
```

## Zakázané

forward returns, hit rate, Sharpe, CAGR, drawdown, jakákoli
profitability interpretace, Decision Resolver scoring.

## PASS / CONDITIONAL / STOP

```text
PASS:        market_cap coverage >= 95 % AND UNKNOWN_ERROR == 0
             AND reprodukovatelné zdroje (hashe) AND žádný current-cap leak
CONDITIONAL: coverage 90–95 %, NEBO approximation risk vyžaduje review
             (MARKET_CAP_SUSPECT > 0, boundary koncentrace)
STOP:        coverage < 90 % | current market cap použit historicky |
             nereprodukovatelný zdroj | silent drop (porušení 1:1) |
             forward-return leakage
```

## Výstupy

```text
results/diagnostics/cap01_coverage_<run_id>/
    candidate_days.csv (echo) | marketcap_rows.csv (bez cen forward)
    bucket_distribution tabulky | audit_summary.md | source_manifest.json
```

## Implementační poznámka (CAP-01, ne CAP-00)

Očekávané dotčené soubory: nový runner (vzor run_fundamental_coverage_audit),
schemas.py append-only (+sharesbas[, sharefactor]) — vyžaduje schválení,
testy. Provider/store/coverage/MLE/IRC/MDSM beze změny.
