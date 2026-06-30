# Research Project: MLE x IRC Robustness Grid

```yaml
project_id:        RP-0004-MLE-IRC-ROBUSTNESS
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Je MLE x IRC edge robustni vuci zmene prahu MLE a IRC,
> nebo existuje pouze v jednom konkretnim bode (overfit)?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-interaction
    note: "Nejsilnejsi kandidat dosud: MLE TOP20 (10D) + IRC TOP10,
           diff +1.28pp alpha. Tento test overuje stabilitu kolem
           tohoto bodu."
```

**Motivace:** Edge testovany pouze v jednom bode (TOP20 x TOP10) muze
byt nahodny artefakt konkretni kombinace prahu. Pokud edge existuje
ve stabilni oblasti kolem tohoto bodu, je dukaz silnejsi.

---

## Hypotheses

### Hypothesis H-001

```yaml
formulace:          "Diff alpha (MLE+IRC_TOP vs MLE_HEADWIND) je kladny
                     a stabilni napric grid MLE TOP10/20/30/50 x IRC TOP5/10/15/20."
ocekavany_efekt:    "Vetsina (>=10 ze 16) kombinaci v gridu ma kladny diff > 0"
kriteria_potvrzeni: "Stabilni oblast kladneho diffu, ne jen jeden bod"
kriteria_zamitnutí: "Edge existuje pouze pri presne MLE TOP20 x IRC TOP10"
```

---

## Grid

```
MLE rank_10d <= {10, 20, 30, 50}
IRC rank      <= {5, 10, 15, 20}
= 16 kombinaci
```

Metrika: alpha vs SPY, vsechny windows (5D/10D/20D/30D), primary=30D.

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLEIRCRobustnessGrid v1.0.0 | RUNNING |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-interaction
      type: knowledge_record
      note: "Nejsilnejsi single-point vysledek — tento test overuje robustnost"
  inspired: []
  produced_rules: []
```
