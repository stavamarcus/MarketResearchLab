# System Architecture — Market Research Lab

**Verze:** 1.0  
**Datum:** 2026-06-28

Tento dokument popisuje pouze **vztahy** mezi komponentami.
Neobsahuje implementační detaily.

---

## 1. Celková architektura platformy

```
┌─────────────────────────────────────────────────────┐
│                    MDSM-Lite                         │
│   data/cache/prices/   data/universe/   data/archive │
│   READ-ONLY pro MRL                                  │
└────────────────────────┬────────────────────────────┘
                         │ čte (nikdy nepíše)
                         ▼
┌─────────────────────────────────────────────────────┐
│              Market Research Lab                     │
│                                                      │
│  Research Portfolio                                  │
│    └── Research Project                              │
│          └── Experiment → ExperimentRunner           │
│                               │                      │
│                         ContextBuilder               │
│                               │                      │
│                         Providers (MDSM)             │
│                               │                      │
│                         ExperimentContext            │
│                               │                      │
│                         BaseExperiment.run()         │
│                               │                      │
│                         ExperimentResult             │
│                               │                      │
│                    ┌──────────┴──────────┐           │
│                    ▼                     ▼           │
│              ArchiveManager       ReportBuilder      │
│              results/             reports/           │
│                    │                                 │
│              ExperimentRegistry                      │
│              registry/experiment_runs.jsonl          │
│                                                      │
│  Evidence ← [agregace výsledků experimentů]         │
│  Conclusion                                          │
│  Resolution (architekt)                              │
│  KnowledgeRecord → knowledge_base/                  │
└──────────────────────────┬──────────────────────────┘
                           │ pouze APPROVED + CONCLUDED
                           ▼
┌─────────────────────────────────────────────────────┐
│               Decision Resolver                      │
│   implementuje pouze ověřená pravidla                │
│   nikdy nevytváří znalosti                           │
└─────────────────────────────────────────────────────┘
```

---

## 2. Research Governance tok

```
Research Portfolio
       │
       ├── Research Project (RP-2026-06-MRC, RP-...)
       │         │
       │         ├── Research Question
       │         ├── Background
       │         ├── Dependencies ──→ [blocker pokud PENDING]
       │         │
       │         ├── Hypothesis
       │         │         │
       │         │         └── Experiment 1..N
       │         │                   │
       │         │             ExperimentRun (run_id)
       │         │                   │
       │         │             ExperimentResult
       │         │
       │         ├── Evidence  ←── agregace ExperimentResult
       │         │
       │         ├── Conclusion (SUPPORTED / REJECTED / ...)
       │         │
       │         ├── Resolution (architekt: APPROVED / REJECTED / ...)
       │         │
       │         └── Knowledge Record ──→ knowledge_base/
       │
       └── [další Research Project]
```

---

## 3. Experiment execution tok

```
ExperimentRunner.run(experiment, config)
       │
       ├──→ experiment.define() → ExperimentDefinition
       │
       ├──→ ContextBuilder.build(run_id, definition, config)
       │           │
       │           ├──→ UniverseProvider.load_assets()  → AssetUniverse
       │           ├──→ PriceProvider.load_prices()     → dict[conid, DataFrame]
       │           ├──→ SignalProvider.load_features()  → FeatureSet  [optional]
       │           └──→ MetadataProvider.*              → metadata
       │                    ↑
       │              [všechny čtou MDSM-Lite READ-ONLY]
       │
       ├──→ ExperimentContext (run_id, config, assets, prices, features, ...)
       │
       ├──→ experiment.validate(context) → ValidationResult
       │           [FAILED → stop]
       │
       ├──→ experiment.run(context) → ExperimentResult
       │           [čistá funkce, žádné side effects]
       │
       ├──→ ArchiveManager.save() → results/{name}/{version}/{run_id}/
       │
       ├──→ registry JSONL append
       │
       └──→ ReportBuilder.build() → report.md
```

---

## 4. Datová vrstva

```
MDSM-Lite filesystem
       │
       ▼
Providers (src/providers/)
       │
       ├── PriceProvider ABC ←── MDSMPriceProvider
       ├── UniverseProvider ABC ←── MDSMUniverseProvider
       ├── SignalProvider ABC ←── MDSMSignalProvider
       └── MetadataProvider ABC ←── MDSMMetadataProvider
                                        │
                              [budoucí: SharadarProvider, ...]
       │
       ▼
ProviderFactory → ProviderBundle (price, universe, signal, metadata)
       │
       ▼
ContextBuilder
       │
       ▼
ExperimentContext
  ├── assets: AssetUniverse
  │     └── Asset (conid, ticker, sector, industry, ...)
  ├── prices: dict[conid → DataFrame(OHLCV)]
  ├── features: FeatureSet
  │     └── Feature (conid, date, name, value, source_module)
  └── universe: pd.DataFrame (raw)
```

---

## 5. Knowledge lifecycle

```
KnowledgeRecord
  status: DRAFT
       │
       ▼ [po Resolution CONCLUDED]
  status: ACTIVE
  confidence: LOW | MEDIUM | HIGH
  evidence_level: A | B | C
       │
       ▼ [nový výzkum přinese lepší data]
  status: SUPERSEDED
  superseded_by: KR-YYYY-MM-...
       │
       ▼ [pokud strategie stažena z DR]
  status: DEPRECATED
```

```
Starý KR se nikdy nemaže.
Každý KR je immutable po vytvoření.
```

---

## 6. Vrstvy a směr závislostí

```
[Governance]    Research Portfolio, Project, Hypothesis, Evidence, Resolution
                        │ řídí
                        ▼
[Orchestration] ExperimentRunner, ContextBuilder, ArchiveManager
                        │ používá
                        ▼
[Experiment]    BaseExperiment (define, validate, run)
                        │ dostane
                        ▼
[Context]       ExperimentContext, ExperimentConfig, ExperimentResult
                        │ obsahuje
                        ▼
[Domain]        Asset, AssetUniverse, Feature, FeatureSet
                        │ načteno přes
                        ▼
[Providers]     PriceProvider, UniverseProvider, SignalProvider, MetadataProvider
                        │ implementováno jako
                        ▼
[Adapters]      MDSMPriceProvider, MDSMUniverseProvider, ...
                        │ čte (READ-ONLY)
                        ▼
[External]      MDSM-Lite filesystem
```

**Pravidlo:** Závislosti jdou pouze dolů (nebo na stejnou vrstvu).
Žádná nižší vrstva nesmí znát vyšší vrstvu.

---

## 7. Výstupní adresáře

```
MarketResearchLab/
├── results/              ← immutable archiv runs (ArchiveManager)
│   └── {exp}/{ver}/{run_id}/
│       ├── metadata.json
│       ├── metrics.json
│       ├── tables/
│       └── report.md
│
├── registry/             ← append-only log (ExperimentRunner)
│   └── experiment_runs.jsonl
│
├── reports/              ← finální reporty pro review
│
├── knowledge_base/       ← KnowledgeRecords (immutable po vytvoření)
│   └── KR-*.md
│
└── research_projects/    ← živé projektové soubory (mutable)
    └── RP-*/PROJECT.md
```

---

*Diagram vztahů, ne implementace. Aktualizovat při každé architektonické změně.*

---

## 8. Intraday data — architektonická poznámka

**Rozhodnutí architekta, 2026-06-28:**

MRL pracuje výhradně s **EOD daty** z MDSM-Lite Parquet cache.

Intraday data (AccessLayer v2 / IBKR TWS) jsou plánovaná budoucí capability
pro Decision Resolver a forward validation. MRL na ně **nezávisí** a neimplementuje
jejich načítání.

```
EOD data (MDSM-Lite cache)
    └── MRL — výzkum, validace, backtesting          ← aktuální scope

Intraday data (AccessLayer v2 / TWS)
    └── Decision Resolver — produkční execution       ← budoucí, mimo MRL
    └── Forward validation — live monitoring          ← budoucí, mimo MRL
```

**Implikace pro implementaci:**
- `PriceProvider` ABC pracuje s EOD DataFrame (index = obchodní den)
- Žádný MRL provider nenačítá intraday data
- `ExperimentContext` neobsahuje intraday série
- Tato hranice se nezmění bez explicitního architektonického rozhodnutí

---

## 9. Standard metrik pro selekční moduly

**Rozhodnutí architekta, 2026-06-30 (na základě RP-2026-06-30-MLE-IRC-DEPENDENCY):**

```
Primární metrika pro selekční moduly (MLE, IMS, IRC): alpha vs. SPY.
Absolutní return: doplňková metrika, nikdy primární pro rozhodování o hypotéze.
```

**Důvod:** Absolutní return v bull marketu obsahuje tržní drift který
zkresluje srovnání mezi skupinami. Alpha vs SPY izoluje skutečný edge
selekčního modulu od pohybu trhu jako celku.

**Implikace pro nové experimenty:**
- Každý experiment testující selekční modul (MLE, IMS, IRC, budoucí moduly)
  musí počítat alpha vs SPY jako primární metriku rozhodování o hypotéze
- SPY (conid=756733) musí být dostupný v `context.prices` —
  buď přidán do universe, nebo načten separátně (viz ACF-007)
- Absolutní return se uvádí jako kontext, ne jako základ pro SUPPORTED/NOT SUPPORTED

---

## 10. Hranice scope — MRL vs. Market Strategy Lab

**Rozhodnutí architekta, 2026-06-30:**

MRL po dosažení prvního robustního edge (MLE×IRC) dosáhl hranice
svého určeného účelu. Další vrstva (portfolio simulace, backtesting
strategií) NENI soucasti MRL — vznikne jako samostatny sourozenecky
projekt: **Market Strategy Lab (MSL)**.

### Tri oddelene vrstvy

```
1. Edge Research (MRL — hotovo, tento projekt)
   Vstup:  signal (MLE, IMS, IRC, ...)
   Vystup: Knowledge Record
   Otazka: "Ma tento signal edge?"

2. Strategy Research (MSL — novy projekt)
   Vstup:  Knowledge Records z MRL
   Vystup: Validated Strategy
   Otazka: "Vydelava tato strategie jako celek?"

3. Decision Resolver (budoucnost)
   Vstup:  vice strategii z MSL
   Vystup: dnesni akce (co koupit/prodat)
```

### Co MSL potrebuje a MRL nikdy nemel

```
Portfolio Engine     — soucasne otevrene pozice, cash, vahy, rebalancing
Execution Model       — vstup on open/close, slippage, komise
Performance Engine    — CAGR, Max Drawdown, Sharpe, Sortino, Calmar
```

### Proc oddeleny projekt, ne nova vrstva v MRL

MRL zustava zamereny na jediny ucel: objevovat a validovat edge.
MSL ma jiny ucel: zjistit, zda lze z overenych edge sestavit
obchodovatelnou strategii. Smichani by poskodilo citelnost obou.

MSL bude cist Knowledge Records z MRL (read-only), stejne jako MRL
cte MDSM-Lite read-only. Architektura zustava vrstvena:

```
MDSM-Lite
    ↓
Market Research Lab (edge discovery)
    ↓
Knowledge Base
    ↓
Market Strategy Lab (portfolio simulation)
    ↓
Validated Strategies
    ↓
Decision Resolver
    ↓
Trading Bot
```

### Status MRL po tomto rozhodnuti

MRL Architecture Baseline v1.0 zustava FROZEN beze zmeny.
MRL pokracuje v edge research (druhy nezavisly edge, statisticka
vyznamnost existujicich nalezu) paralelne s vznikem MSL.
