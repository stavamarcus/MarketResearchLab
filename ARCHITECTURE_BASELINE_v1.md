# Architecture Baseline v1.0

**Status:** FROZEN  
**Version:** 1.0  
**Date frozen:** 2026-06-30

---

## Důvod zmrazení

```
Reference experiments completed:
  - Reference Experiment #1 (MomentumEdge) — OK
  - Reference Experiment #2 (IMSScoreBucketEdge) — OK
  - MLEIRCDependencyAudit v1.0 → v1.1 — metodický rozdíl objasněn, ne implementační chyba

Historical audit reproduced:
  - IRC Audit v4 Test 7 reprodukován v MRL (v1.1.0)
  - Konzistentní výsledek se stejnou metodikou

No structural architectural deficiencies found.
```

## Pravidlo

```
Architecture changes require evidence from research.

Architektura se mění pouze tehdy, když konkrétní experiment
prokáže konkrétní strukturální omezení.

Ne proto, že nás napadne lepší řešení.
Ne proto, že "by se to mohlo zlepšit".
```

## Default activity od 2026-06-30

```
Run experiments.
Produce Knowledge Records.
Build evidence.

NE: nové architektonické nápady, nové vrstvy, nové abstrakce.
```

Pokud experiment odhalí skutečné architektonické omezení, vznikne
Architecture Baseline v1.1 — přes ACP proces, ne ad-hoc.

---

## Co tento status znamená

```
Architektura je považována za kompletní.
Čeká na ověření prvními dvěma reálnými migracemi auditů.

Dokud první experiment skutečně nenačte ceny, universe a signály
z MDSM-Lite a neprojde end-to-end bez strukturálních změn,
architektura není zmrazena.
```

## Status



Infrastruktura je uzavřena. Změny pouze na základě objektivního
architektonického problému odhaleného reálným experimentem.

---

## Status — 2026-06-29

Podmínky splněny:
- Reference Experiment 1 (MomentumEdge) — OK
- Reference Experiment 2 (IMSScoreBucketEdge) — OK
- Žádné strukturální architektonické změny nebyly nutné

**BASELINE CONFIRMED. MRL Infrastructure v1.0 COMPLETED.**

Infrastruktura je uzavřena.
Změny pouze pokud reálný experiment odhalí objektivní architektonický problém.

---

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

## Co je zmrazeno

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

## Co baseline nepokrývá (záměrně)

Následující oblasti jsou mimo scope v1.0:

- Konkrétní experimenty a migrace auditů
- SignalProvider implementace (MLE, IMS, IRC archivy)
- MetricsEngine konkrétní metriky
- Decision Resolver integrace
- Intraday data (AccessLayer v2)
- Sharadar nebo jiné datové zdroje

---

## Jak probíhá implementace v rámci baseline

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

## Historie zmrazení

```
2026-06-28  Architecture Candidate v1.0 vyhlášena
2026-06-29  Reference Experiment #1 (MomentumEdge) — OK
2026-06-29  Reference Experiment #2 (IMSScoreBucketEdge) — OK
2026-06-30  MLEIRCDependencyAudit v1.0 → v1.1 — metodika objasněna
2026-06-30  Historický audit (IRC Test 7) reprodukován
2026-06-30  Architecture Baseline v1.0 — FROZEN
```
