# CHANGELOG — Market Research Lab

Chronologický záznam změn. Aktualizovat při každém relevantnním commitu.

Formát: `[YYYY-MM-DD] Kategorie: Popis`

Kategorie: ARCHITECTURE | FRAMEWORK | GOVERNANCE | DOMAIN | PROVIDER | EXPERIMENT | FIX | DOCS

---

## 2026-06-28

**[ARCHITECTURE] Architecture Candidate v1.0**  
Architektura je považována za kompletní, čeká na ověření prvními dvěma migracemi auditů.
Status FROZEN bude vyhlášen po úspěšné validaci end-to-end.

**[DOCS] ARCHITECTURE_BASELINE_v1.md vytvořen**  
Frozen baseline s kontrakty, datovým tokem a pravidly pro změny.

**[DOCS] acp/ adresář vytvořen**  
Proces Architecture Change Proposal. Šablona `_TEMPLATE.md`.

**[DOCS] CHANGELOG.md a ROADMAP.md vytvořeny**  
MRL přechází z fáze návrhu do fáze systematické implementace.

**[ARCHITECTURE] Phase 3 — Architecture Consolidation**  
Refactoring pass: oprava `validate_inputs()` → `validate()`, `file_hash()` přidáno
do `PriceProvider` ABC, `ContextBuilder` volá přes kontrakt ne přes `getattr`.
Smazány mrtvé Phase 1/1.5 soubory. `README.md` přepsán.

**[DOCS] ARCHITECTURE_REVIEW.md — Architectural Debt Register**  
Přidány AD-001 až AD-004.

**[DOCS] DOMAIN_MODEL.md vytvořen**  
Specifikace všech doménových objektů: data, vztahy, lifecycle, pravidla (1–10).

**[DOCS] SYSTEM_ARCHITECTURE.md vytvořen**  
Sedm diagramů vztahů mezi komponentami.

**[ARCHITECTURE] Research Governance Layer**  
`RESEARCH_GOVERNANCE.md` v2.0: dva nezávislé stavy (research_status +
production_status), Dependencies jako entita, Evidence Level A/B/C,
Confidence HIGH/MEDIUM/LOW, Research Lineage.

**[GOVERNANCE] Knowledge Base inicializována**  
`KR-2026-06-IRC-persistence-edge.md` — první Knowledge Record.
Findings IRC Audit v4: persistence 11–16/20 optimum, RISK_OFF selhání.

**[GOVERNANCE] Research Projects inicializovány**  
`RP-2026-06-MRC/PROJECT.md` — aktivní projekt, status HYPOTHESIS, blocker pro DR.

**[ARCHITECTURE] Phase 2 — Data Contract Layer**  
`Asset`, `AssetUniverse`, `Feature`, `FeatureSet` — doménové objekty.  
`PriceProvider`, `UniverseProvider`, `SignalProvider`, `MetadataProvider` — specializované ABC.  
`MDSMPriceProvider`, `MDSMUniverseProvider`, `MDSMSignalProvider`, `MDSMMetadataProvider`.  
`ExperimentContext` — jediný vstupní objekt do `run()`.  
`ContextBuilder` — DI sestavení contextu.  
`ProviderFactory` → `ProviderBundle`.

**[ARCHITECTURE] Phase 1.5 — MDSM Data Provider**  
Napojení MRL na MDSM-Lite Parquet cache.
`MDSMDataProvider` (nahrazen v Phase 2 specializovanými providery).

**[ARCHITECTURE] Phase 1 — Framework Skeleton**  
`BaseExperiment`, `ExperimentRunner`, `ExperimentDefinition`, `ExperimentConfig`,
`ExperimentResult`, `ExperimentRegistry`, `ArchiveManager`, `ResultStore`,
`ConfigManager`, `LoggingManager`, `MetricsEngine`, `ReportBuilder`.  
conda env: `market_research_lab`.  
Verifikace: `python main.py list` → 0 běhů, framework funkční.
