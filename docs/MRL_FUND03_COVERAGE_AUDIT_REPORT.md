# FUND-03 Coverage Audit Report

**Status: COMPLETED** — reálný run 2026-07-04 (run_id
`fund03_coverage_20260704_225314_sf1art_20260704_005521`).

> **FUND-03 není edge test a neříká nic o profitabilitě fundamentals.**
> Měří pouze datové pokrytí PIT SF1 ART snapshotu nad reálnými
> MLE × IRC candidate-days.

---

## Vstup

```text
candidate-days:  MLE TOP10 × IRC TOP10 (20d) — extraction
                 fund03_candidate_days_20260704_225140
                 1 144 candidate-days | 151 conidů | 2025-07-09 → 2026-06-27
snapshot:        sf1art_20260704_005521 (53 229 řádků, pinned,
                 hash verified při loadu)
```

## 1. FUND-03 výsledek

```text
RESULT: PASS
included=1144 / excluded=0 / coverage_pct=100.0
UNKNOWN_ERROR=0, CACHE_MISSING=0, SCHEMA_MISMATCH=0
```

## 2. Coverage kvalita

Coverage 100 % — všech 151 conidů má identity resolve i PIT SF1 řádek
pro každý candidate_date. Reason code distribuce: všech 9 kódů = 0
(plyne z excluded=0). Detailní tabulky: `audit_summary.md` +
`coverage_fund03_coverage_20260704_225314_*.md` v run adresáři.

Kontext (ne kruhový důkaz, ale očekávatelný výsledek): identity mapa
byla v Phase 1B postavena s pokrytím 503/503 S&P universe a MLE universe
je jeho podmnožina. Audit nicméně nezávisle potvrzuje, že přes 245
obchodních dní neexistuje žádná NO_SF1_ASOF_DATE díra (i nejstarší
candidate_date 2025-07-09 má dostupný starší datekey).

## 3. Hlavní exclusions

Žádné (excluded=0).

## 4. Staleness / alias rizika

```text
staleness buckety: 0–90d: 1100 | 91–180d: 44 | >180d: 0 | missing/excluded: 0
```

- 96,2 % záznamů má snapshot mladší 90 dní; 3,8 % v pásmu 91–180 d
  (konzistentní s kvartálním ART cyklem); žádný STALE_SNAPSHOT warning.
- alias_count: viz `audit_summary.md` (z konzole nečitelné); vzhledem
  k excluded=0 nemá vliv na coverage — pouze informativní podíl
  GOOG/FOX/NWS mezi included.

## 5. Dostatečnost pro FUND-04 edge protocol design

PASS s rezervou nad prahem 95 % → coverage NENÍ blokátor FUND-04.
Zbývající blokery edge testu jsou mimo data coverage (finální feature
whitelist, leakage review, sample-size review nad reálným N=1 144,
explicitní edge protokol) — viz MRL_FUNDAMENTAL_POLICY_GATE.md §9.

## 6. Explicitní poznámka

FUND-03 je čistě datový audit. Forward returns nebyly počítány ani
načteny (loader guard + kontraktní testy; manifest
`forward_returns_used: false`). Výsledek nevypovídá o edge ani
profitabilitě fundamentals.
