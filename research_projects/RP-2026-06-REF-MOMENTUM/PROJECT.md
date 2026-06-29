# Research Project: Price Momentum Edge (Reference Experiment #1)

```yaml
project_id:        RP-2026-06-REF-MOMENTUM
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-28
last_updated:      2026-06-28
```

---

## Účel

Toto je **Reference Experiment #1**.

Primárním cílem není nový výzkumný výsledek.
Primárním cílem je ověřit Architecture Candidate v1.0 end-to-end.

---

## Research Question

> Vykazují akcie S&P 500 s nejvyšším 20denním momentum
> statisticky vyšší 10denní forward return než akcie s nejnižším momentum?

---

## Background

```yaml
sources:
  - type: hypothesis
    ref:  "Základní momentum anomálie (Jegadeesh & Titman 1993)"
    note: "Momentum je jednou z nejreplikovanějších anomálií v literatuře.
           Vhodné jako referenční experiment — výsledek je předvídatelný,
           odchylky odhalí problémy v implementaci, ne v hypotéze."
```

Experiment byl vybrán jako Reference #1 protože:
- používá pouze EOD prices + universe (jediné dostupné zdroje)
- hypotéza je jasná a falsifikovatelná
- logika je jednoduchá — snadno ověřitelná ručně
- měří obchodní hodnotu signálu (edge), ne správnost modulu

---

## Dependencies

```yaml
dependencies: []
```

---

## Hypotheses

### Hypothesis H-001

```yaml
id:                 H-001
formulace:          "Akcie S&P 500 v TOP decilu podle 20D price momentum
                     vykazují vyšší median 10D forward return než akcie
                     v BOTTOM decilu."
ocekavany_efekt:    "Median return TOP decil > Median return BOTTOM decil.
                     Rozdíl > 0. N >= 50 pozorování na decil."
podminky:           "S&P 500 universe, EOD data, lookback 20D, forward 10D."
kriteria_potvrzeni: "Median(TOP) > Median(BOTTOM), rozdíl > 0.5%."
kriteria_zamitnutí: "Median(TOP) <= Median(BOTTOM)."
```

---

## Experiments

| # | Název | Typ | Status | Run ID | Výsledek |
|---|---|---|---|---|---|
| 1 | Momentum Edge 20D→10D | Edge Validation | RUNNING | | |

---

## Evidence

```yaml
complete: false
```

---

## Conclusion

```yaml
status: null
```

---

## Resolution

```yaml
production_status: NOT_EVALUATED
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "Architecture Candidate v1.0 validation"
      type: observation
      note: "Reference experiment pro ověření MRL frameworku end-to-end"
  inspired: []
  produced_rules: []
```
