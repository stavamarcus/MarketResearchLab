# MRL Fundamental Smoke Integration — test plán (návrh)

**Fáze:** MRL-FUND-00 (plán). Implementace a spuštění: MRL-FUND-01 po schválení.
**Toto NENÍ edge test.** Ověřuje se pouze tok dat a accounting, žádná interpretace výnosů.

---

## 1. Ověřovaný tok

```text
candidate-days (syntetické / minimální reálné)
→ MRLSharadarFundamentalSource.get_fundamentals()
→ SF1Provider.get_snapshot() nad pinovaným snapshotem
→ output DataFrame (kontrakt §3) + CoverageAccumulator
→ coverage_<run_id>.md + smoke summary
```

## 2. Dvě úrovně

**A. Unit/syntetická (povinná, bez reálných dat):** syntetický snapshot + identity
CSV (vzor adapter tests), monkeypatch pro UNKNOWN_ERROR scénář.

**B. Reálná (lokálně u PM, read-only):** pinovaný `sf1art_20260704_005521`,
malý fixní candidate-days vzorek (AAPL/GOOG/LYB + negativní případy).

## 3. Minimální scénáře

| # | Scénář | Očekávání | Úroveň |
|---|---|---|---|
| F1 | valid conid + valid date | řádek OK, sf1_datekey <= candidate_date, fundamentals ne-NaN | A+B |
| F2 | invalid conid | EXCLUDED, reason IDENTITY_MISSING, run pokračuje | A+B |
| F3 | date před prvním SF1 řádkem | EXCLUDED, reason NO_SF1_ASOF_DATE | A+B |
| F4 | alias conid (GOOG) | OK, is_alias=True, pouze fundamentals (žádná price pole ve výstupu — schema je ani neobsahuje) | A+B |
| F5 | coverage konzistence | requested = počet input řádků; returned = počet OK; reason_code_counts = počet EXCLUDED per kód; excluded = requested − returned | A+B |
| F6 | žádné API volání | statická kontrola: wrapper bez HTTP importů; runtime: žádný síťový přístup (adapter read path ho nemá) | A |
| F7 | žádný MDSM-Lite / Decision Resolver import | statická kontrola wrapper + smoke modulů | A |
| F8 | 1:1 input/output včetně duplicit | duplicitní (conid,date) input → 2 output řádky, 2 provider requesty | A |
| F9 | setup fail (neexistující snapshot_id) | konstrukce source selže CACHE_MISSING; žádný partial output | A |
| F10 | UNKNOWN_ERROR mapping | monkeypatched provider RuntimeError → EXCLUDED + UNKNOWN_ERROR | A |

## 4. Výstupy smoke

```text
output DataFrame (kontrola schema kontraktu §3)
coverage_<run_id>.md (adapter CoverageAccumulator formát)
smoke summary: scénář → PASS/FAIL; RESULT: PASS | STOP
```

Pravidlo: jakýkoli FAIL → STOP; žádné SKIPPED scénáře (na rozdíl od adapter smoke
zde nejsou datově podmíněné scénáře).

## 5. Akceptace smoke (vstup do gate)

```text
1. všech 10 scénářů PASS (úroveň A) 
2. reálný běh (úroveň B) RESULT: PASS
3. coverage report vygenerován a čísla sedí s F5
4. potvrzeno: adapter nezměněn, žádné API, žádné zakázané importy
```
