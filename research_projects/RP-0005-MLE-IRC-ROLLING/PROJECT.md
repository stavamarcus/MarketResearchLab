# Research Project: MLE x IRC Rolling Validation

```yaml
project_id:        RP-0005-MLE-IRC-ROLLING
portfolio_area:    Market Leadership
research_status:   IDEA
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Drzi MLE x IRC edge napric casovymi okny, nebo je tazen jednim obdobim?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-robustness
    note: "Edge potvrzen jako robustni vuci prahum (16/16 kombinaci kladnych).
           Tento projekt overuje robustnost vuci CASU."
```

**Motivace:** Robustnost vuci prahum (RP-0004) nevylucuje, ze cely efekt
je tazen jednim kratkym obdobim (napr. jeden silny bull-market mesic).
Rolling validation rozdeli dostupnou historii na okna a overi konzistenci.

---

## Hypotheses

### Hypothesis H-001

```yaml
formulace:          "Diff alpha (MLE+IRC_TOP10 vs MLE_HEADWIND) je kladny
                     ve vetsine rolling oken napric dostupnou historii."
ocekavany_efekt:    "Vetsina oken (napr. >=70%) ma kladny diff"
kriteria_potvrzeni: "Konzistentni kladny diff napric okny, ne jen v jednom"
kriteria_zamitnutí: "Diff je kladny pouze v 1-2 oknech, jinde negativni/nulovy"
```

---

## Navrh metodiky

```
Rozdelit 2025-07-09 -> 2026-06-29 (219 dni) na rolling okna
(presna delka okna k diskuzi — napr. 60 dni s 30denni prekryvou)

Pro kazde okno spocitat diff (MLE+IRC_TOP10 vs MLE_HEADWIND, alpha 30D)
Reportovat: pocet oken s kladnym diff, rozsah, stabilita
```

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLEIRCRollingValidation v1.0.0 | PLANNED |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-robustness
      type: knowledge_record
      note: "Robustnost vuci prahum potvrzena, dalsim krokem je robustnost
             vuci casu — pred jakoukoli uvahou o MRC nebo Decision Resolveru"
  inspired: []
  produced_rules: []
```
