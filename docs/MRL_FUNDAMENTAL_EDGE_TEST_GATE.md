# MRL Fundamental Edge Test — GATE (návrh)

**Fáze:** MRL-FUND-00. Gate definuje podmínky pro PRVNÍ MLE × IRC × fundamentals
edge test. Dokud nejsou VŠECHNY položky splněny a odsouhlaseny architektem,
edge test je BLOCKED.

---

## A. Gate podmínky

### 1. Schválený integration contract
`MRL_FUNDAMENTAL_PROVIDER_CONTRACT.md` schválen architektem (včetně rozhodnutí
otevřených otázek §8: memoizace, price-derived, staleness, feature whitelist).

### 2. Schválený wrapper design
`MRL_FUNDAMENTAL_SOURCE_DESIGN.md` schválen; implementace (FUND-01) CLOSED/ACCEPTED.

### 3. Smoke integration PASS
Dle `MRL_FUNDAMENTAL_SMOKE_TEST_PLAN.md` §5 (A i B úroveň, RESULT: PASS).

### 4. Feature whitelist
Explicitní seznam polí povolených v prvním edge testu. Návrh (ke schválení):

```text
Povoleno v1: revenue, netinc, eps, fcf, roe, grossmargin, netmargin, de
Vyloučeno v1: debt, assets, equity samostatně (pouze jako součást de);
              všechna price-derived pole (marketcap, pe, ps, pb)
Odvozené metriky (growth, buckety) se počítají VÝHRADNĚ v experimentu
z PIT snapshotů, nikdy ve wrapperu.
```

### 5. Leakage policy

```text
- PIT: pouze adapter lookup (datekey <= candidate_date); zákaz jakéhokoli
  pole odvozeného z dat po candidate_date
- Growth metriky: srovnání dvou PIT snapshotů k RŮZNÝM candidate_dates je
  zakázané; growth = poměr polí uvnitř JEDNOHO snapshotu, nebo dva get_snapshot
  cally s candidate_date_2 < candidate_date_1, oba PIT k datu vyhodnocení
- Forward returns: výhradně MDSM ceny (stávající MRL mechanismus)
- Žádný re-fetch/refresh dat během experimentu; snapshot pinned per run
- Survivorship: universe = stávající MRL universe loader; adapter nemá
  delisted backfill (kontrakt §12) → výsledky interpretovat s touto výhradou v KR
```

### 6. PIT alignment policy

```text
candidate_date fundamentals = signal_date experimentu (den MLE/IRC signálu)
Žádný lag/offset v v1 (žádné "datekey + N dní zpracování" úpravy —
Sharadar datekey už je filing-based PIT)
sf1_datekey a staleness_days se logují per záznam (tabulka experimentu)
```

### 7. Staleness policy

```text
v1: warning-only pass-through (adapter default, 180d)
Edge test MUSÍ reportovat staleness distribuci (median, p95, % >180d)
Rozhodnutí o hard-exclude >180d: architekt na základě reálné distribuce
(dnes: snapshot má 0 % >180d → prakticky bezpředmětné, ale reportovat)
```

### 8. Alias field policy

```text
GOOG/FOX/NWS: company-level fundamentals povoleny (is_alias=True v datech)
Price-derived pole zakázána globálně (viz kontrakt §3) → alias asymetrie
nevzniká
Edge test reportuje alias_count; alias záznamy se NEVYLUČUJÍ
```

### 9. Coverage / exclusion policy

```text
Coverage report povinný per run (bez něj výsledek NEVALIDNÍ)
EXCLUDED řádky: mimo statistiky, ale reportované (reason_code distribuce)
Návrh prahů (ke schválení):
    coverage_pct >= 95 %   → výsledek plnohodnotný
    90–95 %                → výsledek podmíněný, povinná reason analýza
    < 90 %                 → run nevalidní pro KR, pouze diagnostika
UNKNOWN_ERROR > 0          → investigace před jakoukoli interpretací
Coverage-po-čase: žádný souvislý úsek eligible dnů s coverage < 90 %
(ochrana proti časově nerovnoměrnému selection bias)
```

### 10. Minimální sample-size pravidla

```text
Návrh (ke schválení; konzistentní s MRL konvencí min_observations):
    per grid buňka (baseline × varianta): N >= 30 candidate-days,
        jinak buňka reportována bez interpretace
    per hypotéza: N >= 100 celkem
    dependence: reportovat unikátní conids a unikátní dny (stávající
        dependence-warning vzor z exit experimentů)
```

### 11. Experiment report requirements

Nad rámec standardního report.md:

```text
snapshot_id + data_hash + contract_versions
coverage sekce (metriky + reason_code_counts)
staleness distribuce
alias_count
feature whitelist použitá v runu
N per buňka + dependence warning
```

### 12. Acceptance criteria pro první edge test

```text
1. Gate položky 1–11 splněny/schváleny
2. Run završen bez UNKNOWN_ERROR
3. Coverage >= schválený práh
4. Registry + immutable archiv + report.md + coverage report kompletní
5. Výsledek (pozitivní i negativní) zapsán jako KR návrh s evidence level
6. Žádná změna adapteru, MLE, IRC, MDSM-Lite, Decision Resolveru
```

---

## B. Návrh prvního edge testu (POUZE NÁVRH — nespouštět)

**Pracovní název:** RP-00XX-FUND-QUALITY-OVERLAY (číslo přidělí governance)

**Hypotéza (draft):** Fundamentální kvalita PIT snapshotu moduluje edge
validovaných momentum kombinací (MLE×IRC); nekvalitní fundamentals identifikují
podmnožinu kandidátů s horším forward výnosem.

### Baseline

```text
MLE TOP10 × IRC TOP10    (primární)
MLE TOP20 × IRC TOP10    (sekundární)
Universe, obchodní dny, forward returns: stávající MRL mechanismy
```

### Varianty (každá = baseline + jeden overlay)

```text
V1  fundamental quality filter    (např. netinc > 0 AND fcf > 0)
V2  revenue growth bucket         (YoY z PIT snapshotů, terciles)
V3  margin / profitability bucket (netmargin nebo roe, terciles)
V4  balance-sheet weakness exclusion (např. de > práh → exclude)
V5  composite quality bucket      (rank-average V1–V4 komponent, terciles)
```

Konkrétní prahy/definice bucketů: samostatné schválení v zadání edge testu
(zde záměrně nefixováno — patří do experiment designu, ne do gate).

### Metriky

```text
5D / 10D / 20D forward return (raw + alpha vs SPY)
mean return, median return
hit rate
sample size (N, unikátní conids, unikátní dny)
coverage rate + excluded candidate-days
reason_code distribution
staleness distribuce
gross vs net: POUZE pokud později přibude strategy layer — v prvním testu ne
```

### Interpretační pravidla (draft)

```text
Primární srovnání: varianta vs. baseline na STEJNÉ množině candidate-days
(overlay smí množinu jen zužovat/segmentovat, ne rozšiřovat)
Negativní výsledek je plnohodnotný výsledek (KR) — viz Edge Lifetime
precedens RP-0011/0012
```

---

## C. Stav

```text
Gate status: DRAFT — čeká na architektonické schválení
Edge test:   BLOCKED do splnění A.1–A.12
```
