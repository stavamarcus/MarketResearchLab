# Research Project: [NÁZEV]

```yaml
project_id:        RP-{YYYY-MM}-{název}
portfolio_area:    Market Leadership | Breadth | Industry Rotation | Risk Regimes | ...
research_status:   IDEA
production_status: NOT_EVALUATED
created:           YYYY-MM-DD
last_updated:      YYYY-MM-DD
```

---

## Research Question

> [Jedna konkrétní otázka. Nesmí obsahovat předpoklad odpovědi.]

---

## Background

*Odkud myšlenka přišla.*

```yaml
sources:
  - type: audit | observation | knowledge_record | literature | hypothesis
    ref:  "..."
    note: "..."
```

---

## Motivation

*Co se změní, pokud hypotéza bude potvrzena.*

---

## Dependencies

*Strukturovaný seznam. Projekt s APPROVED/APPROVED_WITH_RESTRICTIONS
nevstupuje do DR dokud nejsou všechny COMPLETE.*

```yaml
dependencies:
  - id: DEP-001
    type: research_project | dataset | module | external
    ref:  "RP-... nebo popis"
    description: "proč je nutná"
    status: PENDING   # PENDING | COMPLETE | WAIVED
    waived_reason: null
```

---

## Hypotheses

### Hypothesis H-001

```yaml
id:                   H-001
formulace:            ""
ocekavany_efekt:      ""   # konkrétní čísla: +X%, WR > Y%, N > Z
podminky:             ""
kriteria_potvrzeni:   ""
kriteria_zamitnutí:   ""
```

---

## Experiments

| # | Název | Typ | Status | Run ID | Výsledek |
|---|---|---|---|---|---|
| 1 | | Forward Return | PLANNED | | |
| 2 | | Rolling Window | PLANNED | | |
| 3 | | Regime Split | PLANNED | | |

Typy: Forward Return · Rolling Window · Regime Split · Sensitivity · Bootstrap · Out-of-Sample

---

## Evidence

```yaml
complete: false
```

### Souhrn výsledků

*Vyplnit po dokončení experimentů.*

### Konfliktní výsledky

*Povinná sekce. Dokumentovat i výsledky odporující hypotéze.*

### Omezení

---

## Conclusion

```yaml
status: null   # SUPPORTED | PARTIALLY_SUPPORTED | INCONCLUSIVE | REJECTED
```

**Důkazy PRO:**

**Důkazy PROTI:**

**Podmínky platnosti:**

---

## Resolution

```yaml
production_status: NOT_EVALUATED
decided_by:        null
decided_on:        null
restrictions:      null
```

**Odůvodnění:**

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: ""
      type: audit | knowledge_record | observation
      note: ""
  inspired: []
  produced_rules: []
```

---

## Knowledge Record

*Vyplnit po Resolution. Přesunout do knowledge_base/.*

```yaml
kr_id:          KR-{YYYY-MM}-{název}
status:         ACTIVE
confidence:     HIGH | MEDIUM | LOW
evidence_level: A | B | C
supersedes:     null
```
