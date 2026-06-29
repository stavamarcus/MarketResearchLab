# Architecture Candidate v1.0

**Status:** CANDIDATE — čeká na ověření prvním reálným použitím  
**Version:** 1.0  
**Date:** 2026-06-28

---

## Co tento status znamená

```
Architektura je považována za kompletní.
Čeká na ověření prvními dvěma reálnými migracemi auditů.

Dokud první experiment skutečně nenačte ceny, universe a signály
z MDSM-Lite a neprojde end-to-end bez strukturálních změn,
architektura není zmrazena.
```

## Podmínky pro přechod na Architecture Baseline v1.0

```
✅ Migrace prvního auditu projde bez změny architektury
✅ Migrace druhého auditu (jiný typ) projde bez změny architektury
✅ Drobné opravy jsou pouze implementační, ne architektonické
→  Architecture Baseline v1.0 — FROZEN
```

## Co platí již nyní

```
Architektura se nemění ad-hoc.
Každá navrhovaná změna musí být pojmenována a odůvodněna.
Pokud migrace odhalí strukturální problém → opravit, zdokumentovat.
Ne přidávat vrstvy bez důvodu.
```

---

## Co je navrženo (candidate)

### Vrstvová architektura

```
MDSM-Lite          → Data Layer      (read-only zdroj)
Market Research Lab → Knowledge Layer (výzkum, validace, znalosti)
Decision Resolver  → Execution Layer  (produkční implementace)
```

### Adresářová struktura src/

```
src/core/          BaseExperiment, ExperimentRunner, Definition, Config, Result, Registry
src/domain/        Asset, AssetUniverse, Feature, FeatureSet
src/providers/     PriceProvider, UniverseProvider, SignalProvider, MetadataProvider (ABC)
                   MDSMPriceProvider, MDSMUniverseProvider, MDSMSignalProvider, MDSMMetadataProvider
                   ProviderFactory, ProviderBundle
src/context/       ExperimentContext, ContextBuilder
src/transforms/    PriceTransforms
src/infrastructure/ ArchiveManager, ResultStore, ConfigManager, LoggingManager
src/metrics/       MetricsEngine
src/reports/       ReportBuilder
```

### Klíčové kontrakty

```
BaseExperiment.define()    → ExperimentDefinition
BaseExperiment.validate()  → ValidationResult
BaseExperiment.run()       → ExperimentResult
ExperimentRunner.run()     → orchestrace celého lifecycle
ContextBuilder.build()     → ExperimentContext
ProviderFactory.build()    → ProviderBundle
```

### Datový tok

```
ProviderFactory → ProviderBundle
ProviderBundle  → ContextBuilder
ContextBuilder  → ExperimentContext
ExperimentContext → BaseExperiment.run()
ExperimentResult → ArchiveManager + ReportBuilder + Registry
```

### Governance struktura

```
research_projects/   Research Projects (lifecycle: IDEA → KNOWLEDGE_RECORD)
knowledge_base/      Knowledge Records (immutable, supersede nikdy nesmazat)
results/             Experiment runs (immutable, run_id adresáře)
registry/            experiment_runs.jsonl (append-only)
```

---

## Co candidate nepokrývá (záměrně)

Následující oblasti jsou mimo scope v1.0:

- Konkrétní experimenty a migrace auditů
- SignalProvider implementace (MLE, IMS, IRC archivy)
- MetricsEngine konkrétní metriky
- Decision Resolver integrace
- Intraday data (AccessLayer v2)
- Sharadar nebo jiné datové zdroje

---

## Jak probíhá implementace v candidate fázi

```
Nový experiment:
→ Zkopírovat experiments/templates/experiment_template.py
→ Implementovat define(), validate(), run()
→ Spustit přes ExperimentRunner
→ Žádná změna src/ struktury pokud to jde bez ní

Nový datový modul (MLE signály):
→ Implementovat MDSMSignalProvider._load_MLE()
→ Žádná nová třída, žádný nový balíček pokud to jde bez nich
```

---

## Výjimky vyžadující odůvodnění

Každá z následujících změn musí být odůvodněna před implementací:

- Přidání nového balíčku do `src/`
- Změna signatury kontraktů (BaseExperiment, Provider ABC, ExperimentContext)
- Změna výstupní struktury `results/` nebo `registry/`
- Přidání nové závislosti do `environment.yaml`
- Změna datového toku

---

## Roadmap ke zmrazení

```
Architecture Candidate v1.0        ← nyní
       ↓
Migrace prvního auditu             ← Fáze 4
       ↓
Migrace druhého auditu             ← Fáze 4
       ↓
Drobné opravy (pokud potřeba)
       ↓
Architecture Baseline v1.0         ← FROZEN
       ↓
Implementace dalších experimentů
```
