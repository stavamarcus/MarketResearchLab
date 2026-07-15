# MRL Fundamental Integration — Discovery

**Fáze:** MRL-FUND-00 (design only)
**Datum:** 2026-07-04
**Zdroj pravdy:** MarketResearchLab repo (stav po RP-0012), sharadar_mdsm_adapter v1.0 (COMPLETE/ACCEPTED)

---

## 1. Relevantní soubory a jejich role

| Soubor | Role |
|---|---|
| `src/providers/providers_abc.py` | 4 ABC kontrakty: PriceProvider, UniverseProvider, SignalProvider, MetadataProvider. Docstring explicitně počítá s budoucím SharadarProviderem. |
| `src/providers/provider_factory.py` | `ProviderFactory.build()` → `ProviderBundle` (price/universe/signal/metadata) z `config/data_paths.yaml`; jediný aktivní zdroj: `mdsm`. |
| `src/providers/mdsm_providers.py` | Implementace 4 providerů nad MDSM-Lite cache a archivy modulů (MLE/IMS/IRC/breadth). |
| `src/context/context_builder.py` | Sestaví ExperimentContext: universe → prices → features (`feature:*`) → benchmark (`benchmark:*`) → contextual signals (`signal:*`) → source_hashes. Řízeno `definition.required_data`. |
| `src/context/experiment_context.py` | Jediný vstupní objekt experimentu. Obsahuje i lazy provider pole (`price_provider`, ...) pro pokročilé případy. Experiment nikdy nečte disk přímo. |
| `src/query/research_query.py` | Doménová přístupová vrstva (AssetSnapshot/IndustrySnapshot/MarketSnapshot) nad contextem. |
| `src/core/experiment_runner.py` | Orchestrace běhu: ContextBuilder → validate() → run() → ArchiveManager → registry JSONL → ReportBuilder. |
| `src/core/experiment_result.py` | ExperimentResult (metrics/tables/artifacts/summary) + ValidationResult. |
| `src/core/experiment_registry.py` | READ vrstva nad `registry/experiment_runs.jsonl` (zápis provádí pouze Runner, append-only). |
| `src/infrastructure/archive_manager.py` | Immutable archiv: `results/{name}/{version}/{YYYYMMDD_HHMMSS_shortid}/` (metadata.json, config.yaml, metrics.json, tables/, artifacts/, report.md). |
| `src/reports/report_builder.py` | Jednotný `report.md` do run adresáře. |
| `experiments/**/**_v1.py` + `run_*.py` | Experimenty (BaseExperiment) + entry skripty. |
| `config/data_paths.yaml` | Cesty ke zdrojům; obsahuje zakomentovanou sekci `sharadar:` (placeholder). |

## 2. Kde MRL přijímá candidate-days a jak jsou reprezentované

- Candidate-day **není first-class objekt frameworku**. Vzniká uvnitř `experiment.run()` jako dvojice `(conid, signal_date)` iterací `query.dates()` × `query.assets(date=...)` s filtry signálu (MLE bucket, IRC group, ...).
- Reprezentace: ad-hoc `records: list[dict]` → `pd.DataFrame`; sloupce typicky `date, conid, ticker, bucket, ...` + forward returns. Datum je `datetime.date`/`pd.Timestamp`, conid `int`.
- Novější experimenty (exit/entry validation) reportují `N_candidate_days` a dependence warning na duplicitní conid×okna.

## 3. Registrace experimentů a výsledky

- Registrace běhu: `ExperimentRunner._append_registry()` → `registry/experiment_runs.jsonl` (append-only). Definice experimentu: `BaseExperiment.define()` → ExperimentDefinition (name, version, hypothesis, required_data, parameters, tags).
- Výsledky: `results/{name}/{version}/{run_folder}/` přes ArchiveManager (immutable, nikdy nepřepisuje).
- Reporty: `report.md` v run adresáři (ReportBuilder); knowledge_base/ obsahuje KR dokumenty (governance vrstva, mimo scope integrace).

## 4. Jak se dnes řeší exclusions / missing data

- **Tichý drop**: `continue` při chybějící ceně, chybějícím ranku, chybějícím SPY řádku. Žádné reason codes, žádný coverage accounting.
- ContextBuilder loguje `prices: X/Y conid načteno`; chybějící conid v `load_prices` výstupu = "data nejsou dostupná" (ABC kontrakt), ne výjimka.
- Důsledek: dnes nelze rozlišit "kandidát vyloučen kvůli chybějícím datům" vs. "kandidát neprošel filtrem". Pro fundamentals je to nepřijatelné (zadání: missing fundamentals nejsou tichý drop) — selection bias při nerovnoměrném SF1 pokrytí by kontaminoval edge výsledky.

## 5. Navržený insertion point

**Doporučení: varianta B — lazy `fundamental_source` v ExperimentContext.**

Porovnání variant:

| Varianta | Popis | Pro | Proti |
|---|---|---|---|
| A. Plnohodnotný 5. provider | Nový `FundamentalProvider` ABC, rozšíření ProviderBundle/Factory/ContextBuilder, prefetch přes `required_data` klíč | Konzistentní s architekturou 4 providerů | Prefetch model nesedí: candidate-days vznikají až v `run()`; prefetch conid×všechny dny rozsahu = zbytečné provider cally a coverage šum; zásah do 3 core souborů |
| **B. Lazy source v contextu (doporučeno)** | Nové optional pole `fundamental_source` v ExperimentContext; Factory ho sestaví, pokud je v `data_paths.yaml` sekce `sharadar_fundamentals`; experiment volá batch API **po** vygenerování candidate-days | Minimální zásah (context + factory); přesně kopíruje tok candidate-days → PIT lookup; coverage per run přesně odpovídá požadavkům | Odchylka od prefetch vzoru features/signals (zdůvodněná: PIT lookup je per (conid, date), ne range load) |
| C. Post-hoc join mimo framework | Standalone skript joinuje fundamentals na exportované candidate-days | Nulový zásah do MRL | Obchází Runner/registry/archiv → governance únik, riziko ad-hoc leakage; odmítnuto |

Proč B: (1) candidate-days jsou run-time produkt experimentu, PIT fundamentals se na ně vážou 1:1; (2) coverage accounting (kontrakt adapteru §11) je run-level — musí vzniknout v běhu experimentu, ne v prefetchi; (3) existující precedens: context už má lazy provider pole "pro pokročilé případy"; (4) migrace B→A je později aditivní, opačně ne.

## 6. Rizika / nejasnosti

1. **Duplicitní (conid, candidate_date) requesty** — experimenty generují překryvy; bez memoizace nafouknou `requested_candidate_days`. v1: bez memoizace (1 řádek = 1 provider call), reportovat obojí; optimalizace až po FUND-01. → otevřená otázka.
2. **Snapshot pinning** — `latest` je nereprodukovatelné; experiment musí pinovat `snapshot_id` v configu a zapsat `data_hash` manifestu do `source_hashes`.
3. **Coverage nerovnoměrnost v čase** — SF1 pokrytí S&P universe není konstantní; nutná coverage-po-čase kontrola před edge testem (gate).
4. **Alias price-derived pole** — Sharadar `marketcap/pe/ps/pb` jsou pro aliasy zakázané adapterem; pro non-alias jsou duplicitní vůči MDSM cenám. Návrh: v1 price-derived pole v MRL zcela zakázat (MDSM = canonical price source). → rozhodnutí architekta.
5. **Import závislost** — MRL musí importovat `sharadar_mdsm_adapter` (src layout, jiný projekt). Mechanismus (sys.path vs. pip install -e) = implementační rozhodnutí FUND-01.
6. **Umístění docs/** — tento adresář v MRL dosud neexistoval; založen touto fází.

## 7. Co se NESMÍ míchat do MRL fundamental wrapperu

```text
scoring / quality skóre / composite metriky
selekce, filtrování, sizing, trading logic
forward returns / výnosové výpočty
API volání, refresh, scheduler
čtení raw Sharadar dat (parquet) mimo adapter API
zápis do adapter data_root nebo adapter repa
importy MDSM-Lite / Decision Resolveru
mutace candidate-days (wrapper je pouze obohacuje/annotuje)
```
