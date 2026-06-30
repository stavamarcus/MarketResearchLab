# Domain Model — Market Research Lab

**Verze:** 1.0  
**Datum:** 2026-06-28

Definuje všechny doménové objekty: odpovědnost, vlastní data, vztahy, lifecycle.

---

## Governance vrstva

### ResearchPortfolio

**Odpovědnost:** Nejvyšší kontejner výzkumných oblastí.

**Data:**
```
name:        str           # "Market Leadership", "Risk Regimes", ...
description: str
projects:    list[ResearchProject]
```

**Vztahy:**
- Obsahuje 1..N `ResearchProject`

**Lifecycle:** Statický — oblasti se přidávají, nemění se.

---

### ResearchProject

**Odpovědnost:** Základní jednotka výzkumu. Řeší jednu konkrétní otázku.

**Data:**
```
project_id:        str       # "RP-2026-06-MRC"
portfolio_area:    str
research_status:   ResearchStatus
production_status: ProductionStatus
research_question: ResearchQuestion
background:        str
motivation:        str
dependencies:      list[Dependency]
hypotheses:        list[Hypothesis]
experiments:       list[ExperimentRef]
evidence:          Evidence | None
conclusion:        Conclusion | None
resolution:        Resolution | None
knowledge_record:  KnowledgeRecord | None
created:           date
last_updated:      date
```

**Vztahy:**
- Patří do 1 `ResearchPortfolio`
- Obsahuje 1 `ResearchQuestion`
- Obsahuje 1..N `Hypothesis`
- Obsahuje 0..N `Experiment` (přes ExperimentRef)
- Produkuje 0..1 `Evidence`
- Produkuje 0..1 `Conclusion`
- Produkuje 0..1 `Resolution`
- Produkuje 0..1 `KnowledgeRecord`
- Může záviset na jiných `ResearchProject` (přes Dependency)

**Lifecycle:**
```
IDEA → RESEARCH_QUESTION → HYPOTHESIS → TESTING →
EVIDENCE_COMPLETE → CONCLUDED → ARCHIVED
```

**Pravidlo:** Projekt nesmí přeskočit fázi.

---

### ResearchStatus (enum)

```
IDEA
RESEARCH_QUESTION
HYPOTHESIS
TESTING
EVIDENCE_COMPLETE
CONCLUDED
ARCHIVED
```

---

### ProductionStatus (enum)

**Odpovědnost:** Ortogonální vůči `ResearchStatus`. Rozhodnutí architekta.

```
NOT_EVALUATED
REJECTED
APPROVED
APPROVED_WITH_RESTRICTIONS
DEPRECATED
```

**Pravidlo:** Nastavuje výhradně architekt.
**Pravidlo:** `APPROVED` nebo `APPROVED_WITH_RESTRICTIONS` → nutné splnění všech Dependency.

---

### Dependency

**Odpovědnost:** Blokátor podmíněného schválení projektu.

**Data:**
```
id:            str       # "DEP-001"
type:          str       # "research_project" | "dataset" | "module" | "external"
ref:           str       # odkaz: "RP-2026-06-MRC", "5-year dataset", ...
description:   str
status:        DependencyStatus
waived_reason: str | None
```

**DependencyStatus:**
```
PENDING
COMPLETE
WAIVED
```

**Pravidlo:** Projekt s APPROVED production_status nevstupuje do DR
dokud existuje alespoň jedna Dependency se statusem `PENDING`.
**Pravidlo:** `WAIVED` vyžaduje explicitní odůvodnění.

---

### ResearchQuestion

**Odpovědnost:** Formulace výzkumné otázky.

**Data:**
```
text:    str     # "Pomáhá Industry Confirmation zvýšit očekávaný výnos MLE?"
sources: list[Source]
```

**Pravidlo:** Otázka nesmí obsahovat předpoklad správné odpovědi.
**Pravidlo:** Otázka musí být zodpověditelná daty.

---

### Hypothesis

**Odpovědnost:** Testovatelné a falsifikovatelné tvrzení.

**Data:**
```
id:                   str    # "H-001"
formulace:            str
ocekavany_efekt:      str    # konkrétní čísla
podminky:             str
kriteria_potvrzeni:   str
kriteria_zamitnutí:   str
```

**Pravidlo:** Hypotéza není závěr. Kritéria musí být definována před spuštěním experimentů.

---

### Evidence

**Odpovědnost:** Agregovaný soubor důkazů z dokončených experimentů.

**Data:**
```
complete:            bool
experiment_results:  list[ExperimentRef]
key_metrics:         dict[str, Any]
conflicting_results: list[str]     # povinné — i negativní výsledky
limitations:         list[str]
```

**Pravidlo:** Evidence vzniká až po dokončení VŠECH plánovaných experimentů.
**Pravidlo:** Konfliktní výsledky musí být dokumentovány.

---

### Conclusion

**Odpovědnost:** Strukturovaný závěr z Evidence.

**Data:**
```
status:           ConclusionStatus
evidence_for:     list[str]
evidence_against: list[str]
conditions:       str | None    # podmínky platnosti (PARTIALLY_SUPPORTED)
recommendation:   str
```

**ConclusionStatus:**
```
SUPPORTED
PARTIALLY_SUPPORTED
INCONCLUSIVE
REJECTED
```

**Pravidlo:** Conclusion je strukturovaný objekt, ne volný text.
**Pravidlo:** Conclusion vzniká až po kompletní Evidence.

---

### Resolution

**Odpovědnost:** Rozhodnutí architekta o produkčním nasazení.

**Data:**
```
production_status: ProductionStatus
decided_by:        str
decided_on:        date
restrictions:      list[str] | None
rationale:         str
implementation_notes: str | None
```

**Pravidlo:** Rozhoduje výhradně architekt.
**Pravidlo:** Resolution může vzniknout pouze po Conclusion.

---

### KnowledgeRecord

**Odpovědnost:** Trvalá znalost z projektu. Nejcennější výstup.

**Data:**
```
kr_id:          str        # "KR-2026-06-IRC-persistence-edge"
status:         KRStatus
confidence:     Confidence
evidence_level: EvidenceLevel
created:        date
last_reviewed:  date
supersedes:     str | None     # KR-ID předchůdce
superseded_by:  str | None     # KR-ID nástupce
source_project: str            # RP-ID zdroje
findings:       list[str]
when_valid:     str
when_invalid:   str
limitations:    str
recommendations: list[str]
lineage:        Lineage
```

**KRStatus:**
```
DRAFT
ACTIVE
SUPERSEDED
DEPRECATED
```

**Confidence:**
```
HIGH    # Evidence Level A, konzistentní výsledky
MEDIUM  # Evidence Level B nebo A s omezeními
LOW     # Evidence Level C nebo konfliktní výsledky
```

**EvidenceLevel:**
```
A   # více experimentů, rolling validation, N > 500, stabilní
B   # základní backtest, N > 100, bez rolling validation
C   # explorace, malý N, předběžné výsledky
```

**Pravidlo:** KnowledgeRecord je immutable po vytvoření.
**Pravidlo:** Starý KR se nikdy nemaže — pouze `status: SUPERSEDED`.
**Pravidlo:** KR vzniká vždy — i pro REJECTED projekty.

---

### Lineage

**Odpovědnost:** Sleduje řetězec vývoje myšlenky.

**Data:**
```
inspired_by:     list[LineageRef]    # odkud přišla myšlenka
inspired:        list[LineageRef]    # co tato znalost inspirovala
produced_rules:  list[LineageRef]    # produkční pravidla vzniklá z KR
```

---

## Experiment vrstva

### ExperimentDefinition

**Odpovědnost:** Statický popis experimentu — co experiment je.

**Data:**
```
name:          str        # unikátní název
version:       str        # sémantická verze
hypothesis:    str        # [budoucí: odkaz na Hypothesis objekt]
description:   str
required_data: list[str]  # "prices", "feature:MLE_Rank", ...
parameters:    dict       # výchozí parametry
tags:          list[str]
author:        str
```

**Pravidlo:** Immutable. Změna logiky = nová verze.

---

### ExperimentConfig

**Odpovědnost:** Parametry konkrétního běhu experimentu.

**Data:**
```
date_from:   date
date_to:     date
parameters:  dict      # přepisují defaults z Definition
universe:    str       # "sp500", "custom", ...
random_seed: int | None
notes:       str
```

---

### ExperimentContext

**Odpovědnost:** Jediný vstupní objekt pro `experiment.run()`. Nese vše.

**Data:**
```
run_id:    str
config:    ExperimentConfig
assets:    AssetUniverse
prices:    dict[conid → DataFrame]
features:  FeatureSet
universe:  pd.DataFrame
price_provider:    PriceProvider | None    # lazy-load
universe_provider: UniverseProvider | None
signal_provider:   SignalProvider | None
metadata_provider: MetadataProvider | None
signals:       dict[str, pd.DataFrame]   # non-asset kontextuální signály (IRC, breadth)
source_hashes: dict[str, str]
metadata:      dict
```

**Granularita signálů v ExperimentContext:**
- `features` (FeatureSet) = asset-level only: MLE, IMS — identifikováno conid
- `signals` (dict DataFrame) = non-asset: IRC (industry-level), breadth (market-level)

**Pravidlo:** Experiment dostane context — nevytváří si vlastní providery.
**Pravidlo:** Experiment context pouze čte — nikdy nepíše.

---

### ExperimentResult

**Odpovědnost:** Výstup jednoho běhu experimentu.

**Data:**
```
metrics:     dict[str, float | int | str]
tables:      dict[str, DataFrame | dict]
artifacts:   dict[str, Any]
summary:     str
run_id:      str        # nastavuje Runner
completed_at: datetime  # nastavuje Runner
result_hash: str        # SHA-256 metrics, nastavuje Runner
```

**Pravidlo:** `run_id`, `completed_at`, `result_hash` nastavuje Runner, ne experiment.

---

### ValidationResult

**Odpovědnost:** Výsledek `experiment.validate(context)`.

**Data:**
```
status:   ValidationStatus   # OK | WARNING | FAILED
messages: list[str]
```

**Pravidlo:** Runner experiment nespustí pokud `status == FAILED`.

---

## Doménová vrstva

### Asset

**Odpovědnost:** Doménový objekt obchodovaného instrumentu.

**Data:**
```
conid:           int        # IBKR technický identifikátor
ticker:          str        # "AAPL", "SPY"
company_name:    str | None
exchange:        str | None
currency:        str | None
instrument_type: str | None # "STK", "ETF"
sector:          str | None
industry:        str | None
subcategory:     str | None
active:          bool
metadata:        dict
```

**Pravidlo:** Immutable (frozen dataclass).
**Pravidlo:** Experiment pracuje s `Asset`, nikdy přímo s `conid`.

---

### AssetUniverse

**Odpovědnost:** Kolekce Asset objektů s lookup API.

**Metody:**
```
get(conid) → Asset | None
get_by_ticker(ticker) → Asset | None
all() → list[Asset]
active() → list[Asset]
conids() → list[int]
filter_by_sector(sector) → AssetUniverse
filter_by_industry(industry) → AssetUniverse
```

---

### Feature

**Odpovědnost:** Vypočtená informace pro konkrétní instrument a datum.

**Data:**
```
conid:          int
date:           date
feature_name:   str    # "MLE_Rank", "Industry_Rank", "Breadth_Regime"
value:          Any
source_module:  str    # "MLE", "IMS", "IRC", "computed"
source_version: str
metadata:       dict
```

**Pravidlo:** Immutable (frozen dataclass).
**Pravidlo:** Experiment feature nedopočítává — dostane ji v FeatureSet.

---

### FeatureSet

**Odpovědnost:** Kolekce Feature objektů s rychlým lookup.

**Lookup klíč:** `(conid, date, feature_name)`

**Metody:**
```
get(conid, date, feature_name) → Feature | None
get_value(conid, date, name, default) → Any
all_for_conid(conid) → list[Feature]
all_for_date(date) → list[Feature]
all_for_name(name) → list[Feature]
feature_names() → set[str]
```

---

### PriceSeries

**Odpovědnost:** [Budoucí entita] Typed wrapper pro OHLCV DataFrame.

**Poznámka:** V současné implementaci je cena reprezentována jako
`pd.DataFrame` s indexem `date` a sloupci `open, high, low, close, volume`.
`PriceSeries` jako doménový objekt přijde při první implementaci metriky
vyžadující type safety.

---

## Infrastrukturní vrstva

### ArchiveManager

**Odpovědnost:** Immutable archivace výsledků experimentů.

**Pravidlo:** Každý běh = nový adresář `results/{name}/{version}/{run_id}/`.
**Pravidlo:** Existující run_id → výjimka `ArchiveConflictError`.

---

### ExperimentRegistry

**Odpovědnost:** Append-only log všech experimentálních běhů.

**Formát:** JSONL — jeden řádek = jeden běh.
**Operace:** Pouze READ (find, last_run, compare_runs, summary).
**Zápis:** Výhradně `ExperimentRunner`.

---

### ProviderBundle

**Odpovědnost:** Čtveřice specializovaných providerů pro jeden datový zdroj.

**Data:**
```
price:       PriceProvider
universe:    UniverseProvider
signal:      SignalProvider
metadata:    MetadataProvider
source_name: str
```

---

## Pravidla architektury

```
1. Experiment nikdy nepřistupuje přímo do MDSM-Lite.
   Experiment používá pouze ExperimentContext.

2. KnowledgeRecord je immutable po vytvoření.
   Starý KR se nikdy nemaže — dostane status SUPERSEDED.

3. Resolution může vzniknout pouze po Conclusion.
   Conclusion může vzniknout pouze po kompletní Evidence.

4. Decision Resolver nikdy nečte ExperimentResult přímo.
   Decision Resolver implementuje pouze pravidla schválená v Resolution.

5. MRL nikdy nezapisuje do MDSM-Lite.
   MRL zapisuje pouze do results/, reports/, registry/, knowledge_base/.

6. Dependency se statusem PENDING blokuje vstup projektu do DR.

7. ExperimentDefinition je immutable po registraci.
   Změna výzkumné logiky = nová verze, ne editace.

8. Žádná nižší vrstva nezná vyšší vrstvu.
   Providers neznají Experimenty. Experimenty neznají Governance.

9. Conflicting results musí být dokumentovány v Evidence.
   Negativní výsledky jsou stejně cenné jako pozitivní.

10. Každý ResearchProject produkuje KnowledgeRecord — i REJECTED projekty.
```

---

## Poznámka: rozsah datového kontraktu

**Rozhodnutí architekta, 2026-06-28:**

Všechny doménové objekty a providery v MRL pracují s **EOD daty**.

`PriceSeries` (budoucí entita) bude mít granularitu = obchodní den.

Intraday data jsou mimo scope MRL. Budou použita v Decision Resolveru
pro produkční execution a ve forward validation jako samostatná capability.
MRL tuto hranici nepřekračuje.
