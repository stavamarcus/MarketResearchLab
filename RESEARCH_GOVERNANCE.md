# Market Research Lab — Research Governance

**Verze:** 2.0  
**Datum:** 2026-06-28  
**Status:** Schváleno architektem

---

## Účel

Definuje rozhodovací proces, kterým musí projít každá změna obchodní strategie
před implementací do Decision Resolveru.

```
Metodologie  říká: JAK provádět výzkum.
Governance   říká: KDY je výzkum dostatečný na to, aby změnil produkční systém.
```

---

## Architektonická hierarchie

```
Research Portfolio
    │
    ├── Research Project
    │       │
    │       ├── Research Question
    │       ├── Background
    │       ├── Motivation
    │       ├── Dependencies          ← strukturovaný seznam, ne ručně psaný BLOCKER
    │       ├── Hypotheses
    │       ├── Experiments
    │       ├── Evidence
    │       ├── Conclusion
    │       ├── Resolution
    │       └── Knowledge Record
    │
    └── Knowledge Base
            │
            ├── Knowledge Records     ← aktuální nejlepší poznatek (ne pravda)
            └── Research Lineage      ← řetězec vývoje myšlenky
```

---

## Research Portfolio

Nejvyšší úroveň. Všechny výzkumné oblasti platformy.

| Oblast | Popis |
|---|---|
| Market Leadership | MLE, momentum, rank evoluce |
| Market Breadth | breadth metriky, regime |
| Industry Rotation | IRC, sektorová rotace |
| Risk Regimes | RISK_ON / RISK_OFF klasifikace |
| Execution | vstupní logika, timing |
| Portfolio Construction | kombinace signálů |
| Position Sizing | velikost pozic |

---

## Research Project — dva nezávislé stavy

Projekt má vždy **dva ortogonální stavy**:

### Research Status

Kde se projekt nachází ve výzkumném procesu.

| Status | Meaning |
|---|---|
| `IDEA` | Nápad, otázka ještě není formulována |
| `RESEARCH_QUESTION` | Otázka formulována |
| `HYPOTHESIS` | Hypotéza definována, kritéria jasná |
| `TESTING` | Experimenty probíhají |
| `EVIDENCE_COMPLETE` | Všechny experimenty dokončeny, evidence agregována |
| `CONCLUDED` | Závěr strukturován |
| `ARCHIVED` | Odloženo bez závěru |

### Production Status

Co architekt rozhodl o nasazení do Decision Resolveru.
**Nezávisí na Research Status** — jsou ortogonální.

| Status | Meaning |
|---|---|
| `NOT_EVALUATED` | Výzkum ještě nebyl posouzen pro produkci |
| `REJECTED` | Zamítnuto — do DR nevstoupí |
| `APPROVED` | Schváleno bez podmínek |
| `APPROVED_WITH_RESTRICTIONS` | Schváleno, ale s podmínkami (specifikovány) |
| `DEPRECATED` | Bylo nasazeno, nyní nahrazeno nebo staženo |

**Příklad kombinací:**

```
research_status:    CONCLUDED
production_status:  NOT_EVALUATED
→ Výzkum dokončen, architekt ještě nerozhodl.

research_status:    CONCLUDED
production_status:  APPROVED_WITH_RESTRICTIONS
→ Schváleno, ale čeká na splnění podmínek (Dependencies).

research_status:    TESTING
production_status:  NOT_EVALUATED
→ Výzkum probíhá, produkce se neřeší.
```

---

## Dependencies

Strukturovaný seznam závislostí projektu.

**Pravidlo:** Projekt s `production_status: APPROVED` nebo `APPROVED_WITH_RESTRICTIONS`
nesmí vstoupit do Decision Resolveru dokud nejsou všechny závislosti `COMPLETE`.

```yaml
dependencies:
  - id: DEP-001
    type: research_project
    ref: RP-2026-06-MRC
    description: "MRC musí validovat RISK_ON / RISK_OFF klasifikaci"
    status: PENDING     # PENDING | COMPLETE | WAIVED

  - id: DEP-002
    type: dataset
    ref: "5-year EOD dataset"
    description: "Rozšíření backtestového období na 5 let"
    status: PENDING
```

Dependency `status: WAIVED` vyžaduje explicitní odůvodnění architekta.

---

## Lifecycle projektu

```
IDEA
 ↓
RESEARCH_QUESTION       otázka formulována, background zdokumentován
 ↓
HYPOTHESIS              hypotéza definována, kritéria jasná, dependencies identifikovány
 ↓
TESTING                 experimenty probíhají
 ↓
EVIDENCE_COMPLETE       evidence agregována, konflikty zdokumentovány
 ↓
CONCLUDED               závěr strukturován (Conclusion objekt)
 ↓
[architekt rozhodne production_status]
 ↓
KNOWLEDGE_RECORD        uložen do Knowledge Base
```

**Pravidlo:** Žádný projekt nesmí přeskočit fázi.
**Pravidlo:** Knowledge Record vzniká vždy — i pro REJECTED projekty.

---

## Hypothesis

Hypotéza musí být testovatelná a falsifikovatelná.

```yaml
hypothesis:
  id: H-001
  formulace: "..."
  ocekavany_efekt: "konkrétní: +X% median return, WR > Y%"
  podminky: "kdy má platit"
  kriteria_potvrzeni: "co musí být splněno"
  kriteria_zamitnutí: "co ji vyvrátí"
```

Hypotéza není závěr.

---

## Conclusion

Strukturovaný objekt, ne volný text.

| Status | Meaning |
|---|---|
| `SUPPORTED` | Hypotéza potvrzena, kritéria splněna |
| `PARTIALLY_SUPPORTED` | Potvrzena za určitých podmínek |
| `INCONCLUSIVE` | Data nedostatečná nebo konfliktní |
| `REJECTED` | Hypotéza vyvrácena |

Conclusion obsahuje: status, důkazy PRO, důkazy PROTI, podmínky platnosti.

---

## Decision Resolver Gate

DR přijímá **pouze** projekty splňující všechny podmínky:

```
production_status == APPROVED
    AND research_status == CONCLUDED
    AND evidence.complete == True
    AND knowledge_record.created == True
    AND all(dep.status == COMPLETE for dep in dependencies)
```

Pokud není splněna každá podmínka — projekt nevstupuje.

---

## Knowledge Record — aktuální nejlepší poznatek

Knowledge Record **není pravda**. Je to aktuální nejlepší poznatek.

### Povinná metadata KR

```yaml
kr_id: KR-{YYYY-MM}-{projekt}-{téma}
status: ACTIVE | SUPERSEDED | DEPRECATED
confidence: HIGH | MEDIUM | LOW
evidence_level: A | B | C    # A = silná, B = střední, C = slabá
created: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
supersedes: null | KR-...
superseded_by: null | KR-...
source_project: RP-...
```

### Evidence Level definice

| Level | Kritéria |
|---|---|
| A | Více experimentů, rolling validation, N > 500, stabilní výsledky |
| B | Základní backtest, N > 100, bez rolling validation |
| C | Explorace, malý N, předběžné výsledky |

### Pravidlo aktualizace

Starý KR se **nikdy nemaže**. Pouze dostane `status: SUPERSEDED` a odkaz na nástupce.

```
KR-2026-06-IRC-persistence-edge   status: SUPERSEDED → superseded_by: KR-2027-03-IRC-...
KR-2027-03-IRC-persistence-edge-v2  status: ACTIVE    ← nový, rozšířená data
```

---

## Research Lineage

Sleduje řetězec vývoje myšlenky. Součást každého Knowledge Record.

```yaml
lineage:
  inspired_by:
    - ref: "IRC Audit v4"
      type: audit
      note: "Finding: RISK_OFF selhání všech edge kombinací"

  inspired:
    - ref: RP-2026-06-MRC
      type: research_project
      note: "MRC jako přímý důsledek RISK_OFF finding"

  produced_rules:
    - ref: DR-17
      type: decision_resolver_rule
      note: "Industry Confirmation rule — čeká na MRC COMPLETE"
```

**Účel:** Za dva roky uvidíš celý řetězec — odkud pravidlo vzniklo, přes jaký výzkum prošlo, proč bylo přijato nebo zamítnuto. Žádné pravidlo nevzniká bez sledovatelné historie.

---

## Architektonický princip

```
Decision Resolver nikdy nevytváří znalosti.
Market Research Lab nikdy neobchoduje.
Knowledge Record není pravda — je to aktuální nejlepší poznatek.
Výzkum je kumulativní — starší poznatky se supersede, ne mažou.
```

---

## Rozdělení odpovědností platformy

```
MDSM-Lite          → spravuje data
Produkční moduly   → generují signály
Market Research Lab → spravuje znalosti a řídí rozhodování o strategiích
Decision Resolver  → strategie vykonává
```

MRL je Research Operating System pro trading projekt.
Backtesting je pouze jedna z jeho schopností.
