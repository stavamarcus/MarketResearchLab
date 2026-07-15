# MRL Fundamental Policy Gate

**Fáze:** MRL-FUND-02. Konsoliduje závazné politiky fundamentals vrstvy
před coverage auditem (FUND-03) a budoucím edge testem.
**Nadřazené dokumenty:** MRL_FUNDAMENTAL_PROVIDER_CONTRACT.md,
MRL_FUNDAMENTAL_EDGE_TEST_GATE.md (edge-specifické detaily).
**Status jednotlivých politik:** LOCKED = schváleno architektem (FUND-01/02
rozhodnutí); DRAFT = čeká na schválení.

---

## 1. Feature whitelist policy — DRAFT

- Do experimentu vstupují POUZE explicitně vyjmenovaná pole; žádné
  automatické `fields=None` v edge testech.
- Návrh whitelist v1 (NENÍ finální edge model):
  ```text
  revenue, netinc, eps, fcf, roe, grossmargin, netmargin, de
  ```
- Mimo whitelist v1: debt, assets, equity samostatně (pouze uvnitř `de`).
- Odvozené metriky (growth, buckety, composite) se počítají výhradně
  v experimentu z PIT snapshotů — nikdy ve wrapperu.
- Finální whitelist schvaluje architekt v zadání edge testu.

## 2. Price-derived field ban — LOCKED

- `marketcap, pe, ps, pb` a jakékoli price-derived ratios: globálně
  zakázány v MRL fundamentals vrstvě (vynuceno wrapperem — konstrukce
  s price polem selže).
- Canonical price source = MDSM/IBKR pipeline. Sharadar SF1 slouží
  výhradně pro fundamentals.
- Pole bez jasně non-price PIT původu se nepovoluje.

## 3. PIT alignment rule — LOCKED

- `sf1_datekey <= candidate_date` (garantuje adapter, zamčené pravidlo).
- candidate_date fundamentals = signal_date experimentu; žádný lag/offset.
- Zákaz jakéhokoli pole odvozeného z dat po candidate_date.
- Growth: pouze z polí jednoho snapshotu, nebo dva PIT lookupy
  s candidate_date_2 < candidate_date_1.

## 4. Staleness policy — LOCKED (pro FUND-02/03)

- Warning-only pass-through (adapter default 180d); ŽÁDNÝ hard-exclude.
- Reporting povinný: buckety `0–90d / 91–180d / >180d` (coverage audit
  harness je počítá) + stale_warnings count.
- Hard-exclude >180d smí být testován později jako VARIANTA edge testu,
  ne jako default — rozhodnutí architekta nad reálnou distribucí.

## 5. Alias policy — LOCKED

- GOOG/FOX/NWS (COMPANY_LEVEL_ALIAS): company-level fundamentals povoleny;
  `is_alias=True` v datech; alias záznamy se NEVYLUČUJÍ.
- Price-derived asymetrie neexistuje (bod 2 — pole zakázána globálně).
- `alias_count` povinný v každém coverage reportu.

## 6. Coverage threshold policy — DRAFT (rámec schválen)

- Platí pro edge test, NE pro diagnostické smoke/audit runy:
  ```text
  coverage_pct >= 95 %   PASS
  coverage_pct 90–95 %   CONDITIONAL — povinná reason analýza
  coverage_pct < 90 %    BLOCKED pro edge test
  ```
- Audit runy pouze měří — interpretace prahů až v edge gate.
- Coverage-po-čase: žádný souvislý úsek eligible dnů s coverage < 90 %
  (kontrola ve FUND-03 nad reálnými candidate-days).

## 7. Reason_code policy — LOCKED

- Missing fundamentals = explicitní `EXCLUDED` řádek + reason_code;
  NIKDY tichý drop (1:1 invarianta wrapperu).
- Kódy 1:1 s adapter coverage vrstvou (9 kódů vč. UNKNOWN_ERROR).
- `UNKNOWN_ERROR > 0` ⇒ investigace před jakoukoli interpretací výsledků.
- Setup-level faily (CACHE_MISSING, SCHEMA_MISMATCH při store load)
  ⇒ celý run FAILED, ne per-řádek exclusion.
- Coverage report povinný per run; bez něj je výsledek NEVALIDNÍ.

## 8. Sample-size policy — DRAFT (rámec schválen)

- `N >= 30` per buňka = absolutní minimum; `N < 30` se nepoužívá
  pro závěr.
- N=30 NENÍ robustní důkaz edge — pouze hranice, pod kterou je výsledek
  bezcenný. Preferováno `N >= 100` per bucket/variantu, pokud data dovolí.
- Povinný reporting: N, unikátní conids, unikátní dny (dependence warning).

## 9. Co blokuje edge test

```text
1. finální feature whitelist neschválen (bod 1 je DRAFT)
2. coverage audit nad REÁLNÝMI MLE × IRC candidate-days neproveden (FUND-03)
3. leakage review neprovedeno (bod 3 checklist nad konkrétním designem)
4. sample-size review nad reálnými počty neprovedeno
5. staleness distribuce nad reálnými candidate-days nezměřena
6. explicitní edge-test protokol (hypotéza, varianty, prahy, interpretační
   pravidla) neschválen architektem
+ obecné gate podmínky A.1–A.12 v MRL_FUNDAMENTAL_EDGE_TEST_GATE.md
```

## 10. Co umožňuje přechod na FUND-03 (coverage audit)

```text
1. FUND-02 CLOSED/ACCEPTED (wiring + testy + tento dokument)
2. schválený zdroj reálných candidate-days pro audit
   (MLE × IRC výběr BEZ forward returns — pouze množina (conid, date))
3. coverage audit harness k dispozici (run_fundamental_coverage_audit.py)
4. pinned snapshot pro audit určen architektem/PM
```

---

## Stav politik

| # | Politika | Status |
|---|---|---|
| 1 | Feature whitelist | DRAFT |
| 2 | Price-derived ban | LOCKED |
| 3 | PIT alignment | LOCKED |
| 4 | Staleness | LOCKED (FUND-02/03 scope) |
| 5 | Alias | LOCKED |
| 6 | Coverage thresholds | DRAFT (rámec schválen) |
| 7 | Reason codes | LOCKED |
| 8 | Sample size | DRAFT (rámec schválen) |
