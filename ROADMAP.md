# ROADMAP — Market Research Lab

**Baseline:** Architecture v1.0 (zmrazena 2026-06-28)  
**Princip:** Implementace podle baseline. Architektonické změny výhradně přes ACP.

---

## Stav k 2026-06-28

```
✅ Architecture Candidate v1.0
✅ Framework skeleton (Core, Providers, Context, Domain)
✅ MDSM-Lite datové napojení (EOD, read-only)
✅ Research Governance (Projects, Knowledge Base)
✅ Domain Model specifikace
✅ conda env: market_research_lab
⏳ Architecture Baseline v1.0 — čeká na validaci prvními dvěma migracemi
```

---

## Fáze 4 — První experiment (příští)

**Cíl:** Provést první reálný výzkumný běh přes framework end-to-end.

**Úkoly:**
- [ ] Vybrat první Research Project pro migraci (kandidát: IRC edge validation)
- [ ] Implementovat `MDSMSignalProvider._load_IRC()` — načítání IRC archivů
- [ ] Implementovat základní metriky v `MetricsEngine` (alpha, win_rate, N)
- [ ] Spustit první `ExperimentRunner.run()` na reálných datech
- [ ] Ověřit archivaci výsledků a JSONL registry
- [ ] Zkontrolovat reprodukovatelnost (spustit dvakrát, porovnat result_hash)

**Výstup:** První záznam v `registry/experiment_runs.jsonl`.

---

## Fáze 5 — Signal Loader implementace

**Cíl:** Načítání výstupů produkčních modulů pro experimenty.

**Úkoly:**
- [ ] `MDSMSignalProvider._load_MLE()` — MLE rank archivy
- [ ] `MDSMSignalProvider._load_IMS()` — IMS score archivy
- [ ] `MDSMSignalProvider._load_IRC()` — IRC rank archivy
- [ ] `MDSMSignalProvider.load_features()` — překlad signálů na Feature objekty
- [ ] Dokumentace formátu archivních souborů každého modulu

**Podmínka:** Závisí na existenci archivních výstupů v MDSM-Lite.

---

## Fáze 6 — Metrics Engine implementace

**Cíl:** Základní sada metrik pro edge validaci.

**Úkoly:**
- [ ] `_metric_alpha()` — excess return vůči benchmarku
- [ ] `_metric_win_rate()` — podíl pozitivních výnosů
- [ ] `_metric_sample_size()` — počet pozorování
- [ ] `_metric_median_return()` — median forward return
- [ ] `PriceTransforms` — ověření na reálných datech

**Poznámka:** Statistické testy (bootstrap, permutation) — samostatná fáze, ne součást základu.

---

## Fáze 7 — Research Project MRC

**Cíl:** Dokončit RP-2026-06-MRC (Market Regime Classifier).

**Blokuje:** Nasazení všech validovaných IRC/MLE edge kombinací do Decision Resolveru.

**Úkoly:**
- [ ] Definovat ex-post RISK_ON/RISK_OFF periody na historických datech
- [ ] Experiment 1: Feature selection pro klasifikaci
- [ ] Experiment 2: Backtest klasifikátoru
- [ ] Experiment 3: Rolling validation
- [ ] Experiment 4: IRC edge filtrovaný MRC vs. nefiltrovaný
- [ ] Evidence agregace, Conclusion, Resolution
- [ ] `KR-2026-MRC.md` — Knowledge Record

---

## Fáze 8 — Legacy Audit migrace

**Cíl:** Migrovat vybrané existující audit skripty jako referenční implementace.

**Proces pro každý skript:**
```
legacy_audits/ → review → rozhodnutí → adaptace na BaseExperiment → validace → experiment
```

**Kandidáti** (po architektonické revizi):
- [ ] IRC Audit v4 → `experiments/edge_validation/irc_edge_v1.py`
- [ ] IMS Audit v4 → `experiments/edge_validation/ims_edge_v1.py`
- [ ] MLE Audit v5 → `experiments/edge_validation/mle_edge_v1.py`
- [ ] SectorRank Health → `experiments/hypothesis_testing/sector_health_v1.py`

---

## Mimo scope (vyžaduje ACP)

Následující oblasti jsou záměrně odloženy:

- Intraday data (AccessLayer v2) — Decision Resolver, ne MRL
- Sharadar datový zdroj — ACP až při konkrétní potřebě
- Decision Resolver integrace — až po prvních APPROVED Research Projects
- Vizualizační dashboard — nízká priorita
- Forward validation pipeline — po Decision Resolveru

---

## Pravidla Roadmap

```
Roadmap je orientační, ne závazná.
Pořadí fází může architekt změnit.
Architektonické změny vyžadují ACP — Roadmap změny ne.
Každá dokončená fáze se zaznamená do CHANGELOG.md.
```
