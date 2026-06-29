# Architecture Review — Market Research Lab

**Verze:** 1.0  
**Datum:** 2026-06-28  
**Rozsah:** Celý projekt po Phase 1, 1.5, 2 a Governance vrstvě

---

## Metodika

Každý soubor byl přečten. Hodnocení je strukturováno do čtyř kategorií:
duplicity, nejasné odpovědnosti, pojmenování, porušení pravidel vrstev.

Závažnost: 🔴 kritická | 🟡 střední | 🟢 nízká

---

## 1. Duplicity a překrývající se odpovědnosti

### 🔴 DataProvider vs. specializované Provider ABC

**Problém:**  
`src/data/data_provider.py` (Phase 1.5) definuje obecný `DataProvider` ABC s metodami
`load_prices()`, `load_universe()`, `available_conids()`.

`src/providers/providers_abc.py` (Phase 2) definuje čtyři specializované ABC:
`PriceProvider`, `UniverseProvider`, `SignalProvider`, `MetadataProvider`.

Oba soubory existují. Žádný nový kód by neměl používat `DataProvider` —
ale je stále přítomen a mohl by být omylem použit.

**Dopad:** Budoucí programátor neví, který interface použít.

**Doporučení:** Smazat nebo nahradit `src/data/data_provider.py` stub souborem
s komentářem odkazujícím na `src/providers/providers_abc.py`.

---

### 🔴 MDSMDataProvider vs. MDSM specialized providers

**Problém:**  
`src/data/mdsm_data_provider.py` (Phase 1.5) — monolitická implementace
`MDSMDataProvider` implementující starý `DataProvider` ABC.

`src/providers/mdsm_providers.py` (Phase 2) — čtyři specializované třídy
`MDSMPriceProvider`, `MDSMUniverseProvider`, `MDSMSignalProvider`, `MDSMMetadataProvider`.

Oba soubory existují a obsahují duplicitní logiku čtení Parquet souborů.
`MDSMDataProvider._read_parquet()` ≈ `MDSMPriceProvider._read_parquet()` — totožný kód.

**Dopad:** Bug fix v jednom místě = nutnost opravit i druhé.

**Doporučení:** Smazat `src/data/mdsm_data_provider.py`. Veškerá funkčnost
je v `src/providers/mdsm_providers.py`.

---

### 🔴 ExperimentData vs. ExperimentContext

**Problém:**  
`src/core/experiment_data.py` — `ExperimentData` s `DataSource` záznamy (Phase 1).
`src/context/experiment_context.py` — `ExperimentContext` (Phase 2, aktivní).

`ExperimentData` není nikde používán po Phase 2. `BaseExperiment.run(context)`
přijímá `ExperimentContext`. `ExperimentData` je mrtvý kód.

`DataSource` v `experiment_data.py` a `source_hashes` v `ExperimentContext`
řeší stejný problém (reprodukovatelnost zdrojů) dvěma různými způsoby.

**Dopad:** Matoucí pro budoucí implementaci.

**Doporučení:** Smazat `src/core/experiment_data.py`. `DataSource` funkcionalita
je pokryta `source_hashes: dict[str, str]` v `ExperimentContext`.

---

### 🟡 DataLoader vs. ContextBuilder

**Problém:**  
`src/data/data_loader.py` — skeleton `DataLoader` (Phase 1).
`src/context/context_builder.py` — `ContextBuilder` (Phase 2, aktivní).

Oba mají metodu `load()` / `build()` se stejným účelem: načíst data pro experiment.
`DataLoader` je skeleton bez implementace. `ContextBuilder` je plná implementace.

**Doporučení:** Smazat `src/data/data_loader.py`. Není použit.

---

### 🟡 ProviderFactory (Phase 1.5) vs. ProviderFactory (Phase 2)

**Problém:**  
`src/data/provider_factory.py` — vrací `DataProvider` (starý interface).
`src/providers/provider_factory.py` — vrací `ProviderBundle` (nový interface).

Stejný název, jiný balíček, jiný výstup. `main.py` neví, který použít.

**Doporučení:** Smazat `src/data/provider_factory.py`.

---

### 🟡 SignalLoader vs. MDSMSignalProvider

**Problém:**  
`src/data/signal_loader.py` — `SignalLoader` skeleton (Phase 1.5).
`src/providers/mdsm_providers.py` — `MDSMSignalProvider` skeleton (Phase 2).

Totožná zodpovědnost, totožný stav (skeleton), různé místo.

**Doporučení:** Smazat `src/data/signal_loader.py`.

---

### 🟡 UniverseLoader vs. MDSMUniverseProvider / UniverseProvider

**Problém:**  
`src/data/universe_loader.py` — `UniverseLoader` wrapping DataProvider (Phase 1.5).
`src/providers/providers_abc.py` — `UniverseProvider` ABC (Phase 2).
`src/providers/mdsm_providers.py` — `MDSMUniverseProvider` implementace (Phase 2).

`UniverseLoader` z Phase 1.5 přidává helper metody (`active_conids()`, `get_ticker()`).
Tyto helpers jsou nyní v `AssetUniverse` v `src/domain/asset.py`.
`UniverseLoader` je tedy překrytý třemi různými třídami.

**Doporučení:** Smazat `src/data/universe_loader.py`.

---

### 🟡 PriceLoader vs. MDSMPriceProvider

**Problém:**  
`src/data/price_loader.py` — `PriceLoader` wrapping DataProvider (Phase 1.5).
Metody `load_close()`, `load_returns()` počítají transformace nad cenami.

Tato funkcionalita chybí v `MDSMPriceProvider` a `ExperimentContext`.
`ExperimentContext.close_matrix()` částečně nahrazuje `PriceLoader.load_close()`.

**Situace je složitější než ostatní duplicity** — `PriceLoader` obsahuje hodnotnou
logiku (výpočet returns, coverage logging), která nemá ekvivalent v Phase 2.

**Doporučení:** Nepřesouvat do providers. Zachovat jako `src/data/price_transforms.py`
(přejmenovat) — statické transformace nad cenovými DataFrame. Jasně oddělit
od načítání dat (providers) a od contextu.

---

## 2. Nejasné nebo matoucí odpovědnosti

### 🟡 ExperimentDefinition.hypothesis — string vs. objekt

**Problém:**  
`ExperimentDefinition` obsahuje pole `hypothesis: str` — volný text.

`RESEARCH_GOVERNANCE.md` definuje `Hypothesis` jako strukturovaný objekt
s formulací, kritérii potvrzení, kritérii zamítnutí.

Tyto dva pojmy jsou nyní nesourodé — jeden je string, druhý je plnohodnotná entita.

**Doporučení:** V příští fázi nahradit `hypothesis: str` odkazem na
`Hypothesis` objekt z domain modelu. Prozatím akceptovatelné.

---

### 🟡 ExperimentRunner — příliš mnoho zodpovědností

**Problém:**  
`ExperimentRunner` v jedné třídě:
- orchestruje lifecycle
- buildí metadata dict
- hashuje výsledky
- zapisuje do JSONL registry
- volá ArchiveManager
- volá ReportBuilder

To je 6 zodpovědností. Třída je 200+ řádků.

Není kritické nyní, ale při růstu projektu se stane bottleneckem.

**Doporučení:** Extrahovat `ResultHasher` (triviální), `RunMetadataBuilder`
a `RegistryWriter` jako interní helpers nebo separátní třídy
při první větší úpravě Runneru.

---

### 🟡 ArchiveManager.save() — příliš mnoho formátů

**Problém:**  
`ArchiveManager.save()` rozhoduje jak uložit každý typ artefaktu:
DataFrame → CSV, string → text, bytes → binary, ostatní → JSON.

Tato logika bude růst s každým novým typem artefaktu.

**Doporučení:** Extrahovat `ArtifactSerializer` při prvním rozšíření.

---

### 🟢 MetricsEngine — skeleton bez jasného vstupu

**Problém:**  
`MetricsEngine.compute(metric_name, **kwargs)` přijímá `**kwargs`.
To je příliš volné — každá metrika má jiný interface.

Při 10 metrikách bude dispatch nepřehledný.

**Doporučení:** Zvážit typed protocol pro každou metriku, nebo skupiny metrik
(ReturnMetrics, StatisticalMetrics). Nízká priorita — řešit až s první
implementovanou metrikou.

---

## 3. Pojmenování

### 🟡 `src/data/` — balíček přežil svůj účel

**Problém:**  
`src/data/` byl navržen jako datová vrstva (Phase 1). Po Phase 2 přesunu
do `src/providers/` a `src/domain/` je `src/data/` hybrid:
- obsahuje Phase 1.5 kód (mrtvý)
- obsahuje `price_loader.py` (částečně živý)

Název `data` je příliš obecný a překrývá se s `providers`, `domain`, `context`.

**Doporučení:** Po smazání mrtvého kódu přejmenovat `src/data/` na
`src/transforms/` pro price transformace, nebo sloučit s jiným balíčkem.

---

### 🟢 `experiment_data.py` — název koliduje s konceptem

**Problém:**  
Soubor se jmenuje `experiment_data.py` a obsahuje `ExperimentData` i `DataSource`.
Ale `ExperimentContext` v jiném balíčku plní stejnou roli a jmenuje se jinak.

Programátor hledající "data pro experiment" najde obojí.

**Doporučení:** Smazat (viz duplicity výše). Pokud zůstane, přejmenovat.

---

### 🟢 `docs_governance.md` — prázdný placeholder

**Problém:**  
`docs_governance.md` v root adresáři je prázdný soubor (1 řádek "placeholder").
`RESEARCH_GOVERNANCE.md` obsahuje skutečný obsah.

**Doporučení:** Smazat `docs_governance.md`.

---

## 4. Porušení vrstvových pravidel

### 🟢 `mdsm_providers.py` — duplikovaná `_parse_bool`

**Problém:**  
Pomocná funkce `_parse_bool()` je definována v `mdsm_providers.py`.
Stejná logika existuje v `asset.py` implicitně přes `_normalize_active_flag`.

**Doporučení:** Extrahovat do `src/infrastructure/utils.py` nebo
přijmout jako akceptovatelnou duplicitu (funkce je triviální).

---

### 🟢 `ContextBuilder._collect_hashes()` — zná konkrétní provider

**Problém:**  
```python
file_hash_fn = getattr(self._price_provider, "file_hash", None)
```
`ContextBuilder` ví, že `MDSMPriceProvider` má metodu `file_hash()`.
To je leak implementačního detailu přes ABC boundary.

`PriceProvider` ABC tuto metodu nedefinuje.

**Doporučení:** Přidat `file_hash(conid: int) -> str | None` do `PriceProvider` ABC.
Ostatní implementace vrátí `None`.

---

## 5. Souhrn — prioritizovaný akční seznam

| Priorita | Akce | Soubor | Typ |
|---|---|---|---|
| 🔴 1 | Smazat | `src/data/data_provider.py` | Duplicita s providers_abc |
| 🔴 2 | Smazat | `src/data/mdsm_data_provider.py` | Duplicita s mdsm_providers |
| 🔴 3 | Smazat | `src/core/experiment_data.py` | Nahrazeno ExperimentContext |
| 🟡 4 | Smazat | `src/data/data_loader.py` | Nahrazeno ContextBuilder |
| 🟡 5 | Smazat | `src/data/provider_factory.py` | Duplicita s providers/ |
| 🟡 6 | Smazat | `src/data/signal_loader.py` | Duplicita s MDSMSignalProvider |
| 🟡 7 | Smazat | `src/data/universe_loader.py` | Nahrazeno AssetUniverse |
| 🟡 8 | Smazat | `docs_governance.md` | Prázdný placeholder |
| 🟡 9 | Přejmenovat | `src/data/price_loader.py` → `src/transforms/price_transforms.py` | Pojmenování |
| 🟡 10 | Přidat do ABC | `file_hash()` do `PriceProvider` | Layer boundary |
| 🟢 11 | Zvážit | Rozdělit `ExperimentRunner` | SRP, nízká priorita |
| 🟢 12 | Zvážit | Typed metriky v `MetricsEngine` | Nízká priorita |

---

## 6. Co je dobře navrženo

Pro rovnováhu — toto jsou části, které jsou architektonicky správné a neměnit:

- `DataProvider` → `ProviderBundle` (specializace) je správný směr
- `Asset` + `AssetUniverse` — čistý doménový objekt, frozen, lookup API
- `Feature` + `FeatureSet` — správná abstrakce pro budoucí feature engineering
- `ExperimentContext` jako jediný vstup do `run()` — DI je čistá
- `ArchiveManager` immutability (run_id adresář, conflict exception) — správně
- JSONL registry append-only — správně
- `ExperimentDefinition` frozen + verzování — správně
- `ProviderFactory` → `ProviderBundle` — dobrý pattern pro DI
- Governance dokumenty odděleny od kódu — správně

---

*Architecture Review by Claude (programátor), 2026-06-28*  
*Ke schválení architektem před implementací akčního seznamu.*

---

## 7. Architectural Debt — stav po Refactoring Pass (2026-06-28)

| ID | Priority | Description | Impact | Resolution | Status |
|---|---|---|---|---|---|
| AD-001 | HIGH | `src/data/` celý balíček — 7 souborů Phase 1/1.5 překrývající Phase 2 | Bug fix duplicity, matoucí pro budoucí implementaci | Smazán, `price_loader.py` přesunut do `src/transforms/` | ✅ RESOLVED |
| AD-002 | HIGH | `MDSMDataProvider` — monolitická Phase 1.5 implementace duplikující Phase 2 providers | Duplicitní `_read_parquet()` logika | Smazán | ✅ RESOLVED |
| AD-003 | HIGH | `ExperimentData` / `DataSource` — Phase 1 předchůdce `ExperimentContext` | Mrtvý kód, matoucí naming | Smazán | ✅ RESOLVED |
| AD-004 | MEDIUM | `load_assets()` v `MDSMUniverseProvider` — duplicitní implementace (neúspěšný refactor) | Mrtvý kód uvnitř metody | Opraveno — jeden čistý průchod | ✅ RESOLVED |
| AD-005 | MEDIUM | `file_hash()` chybělo v `PriceProvider` ABC — layer boundary leak | `ContextBuilder` znal konkrétní implementaci | Přidáno do ABC jako default `None` | ✅ RESOLVED |
| AD-006 | MEDIUM | `docs_governance.md` — prázdný placeholder | Zbytečný soubor | Smazán | ✅ RESOLVED |
| AD-007 | MEDIUM | Phase references v docstrinzích (`Phase 1`, `Phase 2`, ...) | Matoucí historiografie v produkčním kódu | Odstraněno z `experiment_runner.py`, `providers_abc.py` | ✅ RESOLVED |
| AD-008 | LOW | `ExperimentRunner` — 6 zodpovědností v jedné třídě | SRP porušení, bottleneck při růstu | Odloženo — řešit při první větší úpravě Runneru | 🔵 DEFERRED |
| AD-009 | LOW | `ArchiveManager.save()` — ad-hoc serializace artefaktů | Poroste s každým novým typem artefaktu | Odloženo — extrahovat `ArtifactSerializer` při první potřebě | 🔵 DEFERRED |
| AD-010 | LOW | `MetricsEngine.compute(**kwargs)` — příliš volný interface | Nepřehledné při 10+ metrikách | Odloženo — řešit při první implementované metrice | 🔵 DEFERRED |
| AD-011 | LOW | `ExperimentDefinition.hypothesis: str` — nesoulad s `Hypothesis` objektem v Governance | String vs. strukturovaný objekt | Odloženo — Phase 4 (Research Project entity) | 🔵 DEFERRED |

**Stav po refactoring pass:** 7 RESOLVED, 4 DEFERRED (nízká priorita, vhodný čas pro řešení definován).

---

*Architectural Debt sekce aktualizovat po každém větším refactoringu.*

---

## 7. Architectural Debt Register

Strukturovaný seznam architektonického dluhu. Aktualizovat po každé změně.

---

### AD-001 — ExperimentDefinition.hypothesis je string

**Priority:** MEDIUM  
**Status:** OPEN  

**Description:**  
`ExperimentDefinition.hypothesis: str` je volný text.  
`DOMAIN_MODEL.md` definuje `Hypothesis` jako strukturovaný objekt
s kritérii potvrzení a zamítnutí.

**Impact:**  
Experiment nemůže strojově ověřit, zda jsou kritéria hypotézy splněna.
Při migraci auditů bude nutná ruční konverze.

**Resolution:**  
Nahradit `hypothesis: str` odkazem na `Hypothesis` doménový objekt.
Implementovat až při prvním experimentu s formální hypotézou.

---

### AD-002 — ExperimentRunner má příliš mnoho zodpovědností

**Priority:** LOW  
**Status:** OPEN  

**Description:**  
`ExperimentRunner` v jedné třídě: orchestruje lifecycle, buildí metadata,
hashuje výsledky, zapisuje JSONL, volá ArchiveManager, volá ReportBuilder.
6 zodpovědností, 200+ řádků.

**Impact:**  
Při růstu projektu bude obtížné testovat a rozšiřovat jednotlivé části.

**Resolution:**  
Extrahovat `RunMetadataBuilder` a `RegistryWriter` jako interní helpers.
Řešit při první větší změně Runneru — ne nyní.

---

### AD-003 — MetricsEngine používá **kwargs dispatch

**Priority:** LOW  
**Status:** OPEN  

**Description:**  
`MetricsEngine.compute(metric_name, **kwargs)` — každá metrika má jiný interface.
Při 10+ metrikách bude dispatch nepřehledný a obtížně typovatelný.

**Impact:**  
Nízký dokud existuje ≤ 5 metrik.

**Resolution:**  
Zvážit typed protocol pro skupiny metrik (ReturnMetrics, StatisticalMetrics).
Řešit až s první implementovanou metrikou.

---

### AD-004 — ArchiveManager.save() rozhoduje o formátu artefaktů

**Priority:** LOW  
**Status:** OPEN  

**Description:**  
`ArchiveManager.save()` obsahuje inline logiku pro různé typy artefaktů
(DataFrame → CSV, str → text, bytes → binary, ostatní → JSON).
Tato logika poroste s každým novým typem artefaktu.

**Impact:**  
Nízký při ≤ 4 typech artefaktů.

**Resolution:**  
Extrahovat `ArtifactSerializer` při prvním rozšíření.
