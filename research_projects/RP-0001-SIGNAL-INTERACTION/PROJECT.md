# Research Project: Signal Interaction Study

```yaml
project_id:        RP-0001-SIGNAL-INTERACTION
portfolio_area:    Market Leadership
research_status:   IDEA
production_status: NOT_EVALUATED
created:           2026-06-29
last_updated:      2026-06-29
priority:          HIGH
```

---

## Research Question

> Které kombinace již ověřených signálů (MLE, IMS, IRC, Breadth)
> vytvářejí nejvyšší očekávaný edge v S&P 500 universe?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  KR-2026-06-IRC-persistence-edge
    note: "MLE, IMS, IRC mají individuálně validovaný edge.
           Nikdy nebyly systematicky testovány jako kombinace."
  - type: audit
    ref:  market_breadth_audit/decision_simulation_audit.py
    note: "Existující script pro multi-modul kombinace — kandidát na migraci."
```

**Motivace:**
Jednotlivé signály jsou ověřeny. Nevíme:
- zda kombinace přidávají alpha nebo ji snižují
- které kombinace jsou redundantní
- která kombinace má nejvyšší očekávaný edge

---

## Dependencies

```yaml
dependencies:
  - id: DEP-001
    type: research_project
    ref:  RP-2026-06-MRC
    description: "RISK_ON/RISK_OFF filtr — bez MRC nelze bezpečně nasadit do DR"
    status: PENDING
```

---

## Hypotheses

### Hypothesis H-001 — Kombinace MLE + IMS > samostatné signály

```yaml
id:                 H-001
formulace:          "MLE TOP20 filtrovaný IMS score >= 80 dosahuje vyššího
                     median 30D forward returnu než samotné MLE TOP20."
ocekavany_efekt:    "Median(MLE+IMS) > Median(MLE_only) + 0.5%"
podminky:           "S&P 500, RISK_ON, backfill 2025-07-09 → aktuální"
kriteria_potvrzeni: "Spread > 0.5%, N >= 100 pozorování"
kriteria_zamitnutí: "Spread <= 0, nebo IMS filtr snižuje N pod 30"
```

### Hypothesis H-002 — Industry context přidává alpha

```yaml
id:                 H-002
formulace:          "MLE TOP20 akcie jejichž industry je v IRC TOP10 (20D)
                     dosahují vyššího median 30D returnu než MLE TOP20 bez tohoto filtru."
ocekavany_efekt:    "Median(MLE+IRC) > Median(MLE_only) + 0.5%"
podminky:           "S&P 500, RISK_ON, lookback IRC 20D"
kriteria_potvrzeni: "Spread > 0.5%, N >= 50"
kriteria_zamitnutí: "Spread <= 0"
```

### Hypothesis H-003 — Triple kombinace MLE + IMS + IRC

```yaml
id:                 H-003
formulace:          "MLE TOP20 + IMS >= 80 + IRC TOP10 industry dosahuje
                     nejvyšší median 30D alpha ze všech testovaných kombinací."
ocekavany_efekt:    "Median(triple) > Median(MLE+IMS) a > Median(MLE+IRC)"
podminky:           "N musí být >= 30 — triple filtr může být příliš restriktivní"
kriteria_potvrzeni: "Median(triple) nejvyšší, N >= 30"
kriteria_zamitnutí: "N < 30, nebo triple horší než double kombinace"
```

---

## Experiments

| # | Název | Typ | Status |
|---|---|---|---|
| 1 | MLE only baseline | Edge Validation | PLANNED |
| 2 | MLE + IMS filter | Edge Validation | PLANNED |
| 3 | MLE + IRC context | Edge Validation | PLANNED |
| 4 | MLE + IMS + IRC triple | Edge Validation | PLANNED |
| 5 | Rolling validation | Rolling Window | PLANNED |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-IRC-persistence-edge
      type: knowledge_record
      note: "Individuální edge validovány — čas na kombinace"
    - ref: market_breadth_audit/decision_simulation_audit.py
      type: audit
      note: "Existující multi-modul logika k migraci"
  inspired: []
  produced_rules: []
```
