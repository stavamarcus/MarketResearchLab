# Architecture Candidate Findings

**Verze candidate:** 1.0  
**Reference Experiment:** MomentumEdge v1.0.0 (2026-06-28)

Tento dokument zachycuje poznatky z prvního end-to-end použití architecture candidate.
Každý finding je podkladem pro rozhodnutí před vyhlášením Architecture Baseline v1.0.

---

## ACF-001 — source_hashes loguje příliš mnoho dat

**Severity:** LOW  
**Status:** OBSERVED — čeká na rozhodnutí architekta

**Pozorování:**  
`ContextBuilder._collect_hashes()` hashuje všechny načtené ceny (500 conid).
Výsledek — `source_hashes` dict se 500 záznamy — se loguje do konzole celý
jako součást `context.summary()`.

Log výstup je čitelný jen strojově. Pro člověka je bezcenný.

**Dopad:**  
Žádný funkční dopad. Pouze šum v logu.
`metadata.json` hash data ukládá správně a kompletně.

**Možná řešení (bez architektonické změny):**  
A) Logovat pouze počet hashovaných souborů: `"price_hashes: 500"`  
B) `context.summary()` vrací `{"source_hashes_count": 500}` místo plného dict

**Doporučení:**  
Opravit v `ContextBuilder` nebo `ExperimentContext.summary()` — jde o implementační detail,
ne architektonická změna. Nevyžaduje ACP.

---

## ACF-002 — ReportBuilder nedostane summary z experimentu při live run

**Severity:** MEDIUM  
**Status:** OBSERVED — čeká na rozhodnutí architekta

**Pozorování:**  
`ExperimentRunner` volá `ReportBuilder` ale `result.summary` musí být
vyplněn experimentem v `run()`. V Reference Experimentu byl report generován
dodatečně ručně (mimo Runner) protože Runner neobsahoval ReportBuilder instanci
(byl předán `None`).

Skutečný `report.md` vznikl v Runneru bez `summary` — ten byl přidán
ručně v testovacím skriptu.

**Příčina:**  
`ExperimentRunner.__init__()` přijímá `report_builder=None` jako volitelný parametr.
Při inicializaci v testovacím kódu byl předán `None`.

**Dopad:**  
Žádný architektonický problém — kontrakt je správný.
Jde o inicializační vzor v použití Runneru.

**Doporučení:**  
`main.py` nebo inicializační kód musí vždy předat `ReportBuilder()`.
Zvážit, zda Runner má `ReportBuilder` jako povinný parametr (ne optional).
Nevyžaduje ACP.

---

## ACF-003 — ExperimentConfig.parameters nepropaguje do ReportBuilder

**Severity:** LOW  
**Status:** OBSERVED

**Pozorování:**  
Experiment definuje parametry v `LOOKBACK_DAYS`, `FORWARD_DAYS` jako class-level konstanty.
`ExperimentConfig.parameters` byl předán prázdný dict `{}`.
`ReportBuilder` proto vypsal "_(žádné parametry)_" i přes to, že experiment
parametry má.

**Příčina:**  
Experiment parametry jsou v `ExperimentDefinition.parameters` (defaults),
ale konkrétní běh nevrátil tyto defaults do `ExperimentConfig.parameters`.

**Dopad:**  
Report nezobrazuje parametry experimentu — méně čitelný.
Funkční správnost není ovlivněna.

**Doporučení:**  
`ExperimentRunner` by mohl merge-ovat `definition.parameters` s
`config.parameters` před sestavením contextu — config.parameters přepíše
defaults kde jsou specifikovány. Implementační změna, nevyžaduje ACP.

---

## ACF-004 — Výzkumný výsledek: momentum efekt přítomen, pod prahem

**Severity:** INFO (výzkumný poznatek, ne architektonický problém)

**Pozorování:**  
TOP decil (20D momentum) median 10D forward return: **+0.81%**  
BOTTOM decil median 10D forward return: **+0.46%**  
Spread: **+0.35%** (pod threshold 0.5%)

Hypotéza H-001 technicky NOT SUPPORTED dle nastaveného prahu.
Směr efektu je správný (TOP > BOTTOM), ale magnituda nedosáhla prahu.

**Kontext:**  
Backtestové období 2024–2026 je silně bull market bez výraznějšího RISK_OFF.
Momentum bez RISK_OFF filtru je záměrně nedostatečné — přesně jak IRC Audit ukázal.
Výsledek není překvapivý a neindikuje problém v architektuře.

---

## Celkové hodnocení Architecture Candidate v1.0

### Co prošlo bez problémů ✅

- `ProviderBundle` sestavení — OK
- `MDSMUniverseProvider.load_assets()` — 503 instrumentů načteno
- `MDSMPriceProvider.load_prices()` — 500/503 conid načteno (3 chybějící logované)
- `ContextBuilder.build()` — context sestaven, source_hashes vygenerovány
- `BaseExperiment.validate()` — validace prošla
- `BaseExperiment.run()` — čistá funkce, 219,554 pozorování zpracováno za 5.2s
- `ExperimentResult` — metriky, tables, summary správně
- `ArchiveManager.save()` — immutable archiv vytvořen
- JSONL registry — záznam vytvořen
- `ReportBuilder.build()` — report.md vygenerován
- Reprodukovatelnost — result_hash uložen

### Co vyžaduje drobnou opravu (ne ACP) ⚠️

- ACF-001: `source_hashes` v logu (implementační detail)
- ACF-002: `ReportBuilder` jako povinný parametr Runneru (inicializační vzor)
- ACF-003: merge `definition.parameters` → `config.parameters` (propagace)

### Architektonické kontrakty — beze změny ✅

Žádný z nalezených problémů nevyžaduje změnu:
- `BaseExperiment` interface
- `Provider` ABC
- `ExperimentContext` struktury
- `ArchiveManager` immutability
- JSONL registry formátu
- výstupní adresářové struktury

---

## Závěr

Architecture Candidate v1.0 prošla Reference Experiment #1 **bez strukturálních změn**.

Tři nalezené issues jsou implementační detaily řešitelné bez ACP.

**Doporučení:** Po opravě ACF-001, 002, 003 a úspěšném dokončení
Reference Experiment #2 vyhlásit **Architecture Baseline v1.0**.
