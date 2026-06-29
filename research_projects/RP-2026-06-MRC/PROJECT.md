# Research Project: Market Regime Classifier

```yaml
project_id:        RP-2026-06-MRC
portfolio_area:    Risk Regimes
research_status:   HYPOTHESIS
production_status: NOT_EVALUATED
created:           2026-06-28
last_updated:      2026-06-28
```

---

## Research Question

> Lze spolehlivě klasifikovat tržní režim (RISK_ON / RISK_OFF) tak,
> aby systém věděl, kdy přestat obchodovat?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  KR-2026-06-IRC-persistence-edge
    note: "Finding 4: všechny edge kombinace selhávají v RISK_OFF.
           MRC je přímým důsledkem tohoto finding."
```

---

## Motivation

Bez MRC nelze bezpečně nasadit do Decision Resolveru:
- IRC persistence edge (APPROVED_WITH_RESTRICTIONS)
- IMS + Industry kombinaci
- MLE + Industry kombinaci

MRC je **blocker** pro produkční nasazení všech validovaných edge kombinací.

---

## Dependencies

```yaml
dependencies:
  - id: DEP-001
    type: dataset
    ref:  "Dostatečný historický dataset pokrývající min. jeden plný RISK_OFF cyklus"
    description: "Klasifikátor musí být trénován a validován na datech
                  obsahujících jasné RISK_OFF periody (2022, 2020, ...)"
    status: PENDING
    waived_reason: null
```

---

## Hypotheses

### Hypothesis H-001 — Klasifikace je možná

```yaml
id:                 H-001
formulace:          "Tržní režim (RISK_ON / RISK_OFF) lze spolehlivě klasifikovat
                     pomocí kombinace breadth metrik a price action SP500."
ocekavany_efekt:    "Precision >= 70%, Recall >= 60%, FPR <= 30%
                     oproti ex-post definovaným drawdown periodám."
podminky:           "EOD data, S&P 500, backfill s RISK_OFF periodami."
kriteria_potvrzeni: "Precision >= 70% a Recall >= 60% stabilní
                     napříč rolling windows."
kriteria_zamitnutí: "Precision < 60% nebo výsledek nestabilní v rolling windows."
```

### Hypothesis H-002 — Filtrace zlepší edge

```yaml
id:                 H-002
formulace:          "IRC persistence edge filtrovaný MRC (pouze RISK_ON)
                     vykazuje vyšší alpha než nefiltrovaný edge."
ocekavany_efekt:    "Alpha filtrovaného edge > alpha nefiltrovaného."
podminky:           "H-001 musí být potvrzena."
kriteria_potvrzeni: "Statisticky signifikantní zlepšení alpha, P < 0.05."
kriteria_zamitnutí: "Žádné zlepšení alpha po filtraci."
```

---

## Experiments

| # | Název | Typ | Status | Run ID | Výsledek |
|---|---|---|---|---|---|
| 1 | Regime Definition | Ex-post definice | PLANNED | | |
| 2 | Feature Selection | Forward Return | PLANNED | | |
| 3 | Classifier Backtest | Backtest | PLANNED | | |
| 4 | Rolling Validation | Rolling Window | PLANNED | | |
| 5 | IRC + MRC Filter | Kondicionální edge | PLANNED | | |

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
decided_by:        null
decided_on:        null
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-IRC-persistence-edge
      type: knowledge_record
      note: "Finding 4: RISK_OFF selhání všech edge kombinací"

  inspired: []
  produced_rules: []
```
