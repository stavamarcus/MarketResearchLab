# Market Research Lab

Research Operating System pro vývoj obchodních strategií.

**Poslání:** Vytvářet důvěryhodné poznatky, které mohou být bezpečně převedeny do produkční strategie.

```
MDSM-Lite          → spravuje data
Produkční moduly   → generují signály  
Market Research Lab → spravuje znalosti, řídí rozhodování o strategiích
Decision Resolver  → strategie vykonává
```

---

## Stav projektu

```
Architecture Baseline v1.0 — FROZEN (2026-06-30)
```

Architektura je zmrazena. Změny vyžadují konkrétní evidenci z výzkumu.
Aktuální fokus: experimenty, Knowledge Records, evidence — ne nová architektura.

## Klíčové dokumenty

| Dokument | Obsah |
|---|---|
| `ARCHITECTURE_BASELINE_v1.md` | Frozen baseline — co je zmrazeno, pravidlo pro změny |
| `RESEARCH_GOVERNANCE.md` | Proces výzkumu: lifecycle, governance, DR gate |
| `SYSTEM_ARCHITECTURE.md` | Vztahy mezi komponentami (bez implementace) |
| `DOMAIN_MODEL.md` | Všechny doménové objekty: data, vztahy, lifecycle, pravidla |
| `ARCHITECTURE_REVIEW.md` | Audit, duplicity, Architectural Debt Register |
| `knowledge_base/` | Ověřené poznatky — nejcennější výstup projektu |

---

## Adresářová struktura

```
MarketResearchLab/
│
├── config/
│   ├── settings.yaml          # logging, výstupní adresáře
│   └── data_paths.yaml        # cesty k MDSM-Lite (upravit před spuštěním)
│
├── src/
│   ├── core/                  # framework kontrakt
│   │   ├── base_experiment.py         # ABC: define() / validate() / run()
│   │   ├── experiment_runner.py       # orchestrace lifecycle běhu
│   │   ├── experiment_definition.py   # co experiment je (frozen, verzovaný)
│   │   ├── experiment_config.py       # parametry konkrétního běhu
│   │   ├── experiment_result.py       # ExperimentResult + ValidationResult
│   │   └── experiment_registry.py     # read-only dotazy nad JSONL
│   │
│   ├── domain/                # doménové objekty
│   │   ├── asset.py           # Asset (frozen) + AssetUniverse (kolekce)
│   │   └── feature.py         # Feature (frozen) + FeatureSet (kolekce)
│   │
│   ├── providers/             # datové kontrakty a MDSM implementace
│   │   ├── providers_abc.py   # PriceProvider, UniverseProvider,
│   │   │                      # SignalProvider, MetadataProvider (ABC)
│   │   ├── mdsm_providers.py  # MDSM-Lite implementace všech čtyř
│   │   └── provider_factory.py # ProviderBundle z data_paths.yaml
│   │
│   ├── context/               # dependency injection
│   │   ├── experiment_context.py # jediný vstup do experiment.run()
│   │   └── context_builder.py    # sestaví context před každým během
│   │
│   ├── transforms/            # čisté transformace nad cenovými daty
│   │   └── price_transforms.py   # close matrix, log returns, pct returns
│   │
│   ├── infrastructure/        # archivace, logging, konfigurace
│   │   ├── archive_manager.py    # immutable uložení results/{name}/{ver}/{run_id}/
│   │   ├── result_store.py       # čtení a diff metrik mezi běhy
│   │   ├── config_manager.py     # načítání YAML konfigurace
│   │   └── logging_manager.py    # centrální logging
│   │
│   ├── metrics/
│   │   └── metrics_engine.py     # modulární výpočet metrik (skeleton)
│   │
│   └── reports/
│       └── report_builder.py     # jednotný report.md pro každý experiment
│
├── experiments/
│   ├── templates/
│   │   └── experiment_template.py  # šablona pro nový experiment
│   └── README.md
│
├── results/                   # immutable archiv běhů (ArchiveManager)
│   └── {experiment}/{version}/{run_id}/
│       ├── metadata.json      # reprodukovatelnost: hashes, env, parametry
│       ├── config.yaml
│       ├── metrics.json
│       ├── tables/
│       └── report.md
│
├── registry/
│   └── experiment_runs.jsonl  # append-only log všech běhů
│
├── knowledge_base/            # Knowledge Records (immutable po vytvoření)
│   └── KR-*.md
│
├── research_projects/         # Research Projects (živé dokumenty)
│   ├── _template/PROJECT.md   # šablona pro nový projekt
│   └── RP-*/PROJECT.md
│
├── legacy_audits/             # karanténa starých skriptů (manuální review)
├── reports/                   # finální reporty pro review
├── tests/
├── main.py
└── environment.yaml           # conda env: market_research_lab
```

---

## Pravidla pro experimenty

```
✓  context.prices[conid]["close"]
✓  context.assets.get(conid).ticker
✓  context.features.get_value(conid, date, "MLE_Rank")
✓  context.config.parameters["lookback_days"]

✗  MDSMPriceProvider(prices_dir=...)   — zakázáno
✗  pd.read_parquet(...)                — zakázáno
✗  open("C:/...")                      — zakázáno
```

---

## Spuštění

```bash
# 1. Nastavit cesty v config/data_paths.yaml

# 2. Aktivovat prostředí
conda activate market_research_lab
cd C:\Users\stava\Projects\MarketResearchLab

# 3. Zkontrolovat stav registry
python main.py list

# 4. Porovnat dva běhy
python main.py compare <run_id_a> <run_id_b>
```

---

## Datový zdroj

MRL čte z MDSM-Lite **READ-ONLY** přes specializované providery.
Nikdy nezapisuje do MDSM-Lite. Pracuje výhradně s **EOD daty**.

Intraday data (AccessLayer v2) jsou mimo scope MRL —
budou použita v Decision Resolveru pro produkční execution.

---

## Architektonická pravidla

```
1. Experiment nikdy nepřistupuje přímo do MDSM-Lite.
2. KnowledgeRecord je immutable po vytvoření.
3. Resolution může vzniknout pouze po Conclusion.
4. Decision Resolver implementuje pouze schválená pravidla (Resolution = APPROVED).
5. MRL zapisuje pouze do results/, reports/, registry/, knowledge_base/.
6. Dependency PENDING blokuje vstup projektu do DR.
7. Starý KnowledgeRecord se nikdy nemaže — dostane status SUPERSEDED.
```
