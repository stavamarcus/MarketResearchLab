# Research Project: MLE Rank Buckets x IRC Tailwind

```yaml
project_id:        RP-0008-MLE-BUCKETS-IRC
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Dokaze IRC zachranit slabsi MLE buckety, nebo IRC pomaha hlavne
> uz silnym MLE kandidatum?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-rank-value-decay
    note: "MLE rank decay — hranice edge mezi TOP30 a TOP50."
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-rolling
    note: "MLE x IRC (TOP20) dosahl HIGH confidence. Ale nikdy nebyl
           testovan napric jemnejsimi MLE buckety."
```

**Motivace:** Spojeni dvou nezavisle vzniklych poznatku do jednoho
testu. Pokud IRC dokaze zvednout slabsi buckety (21-30, 31-50) nad
trh, vznika prima architektonicka logika pro Decision Resolver
priority tiers.

---

## Hypotheses

### Hypothesis H-001

```yaml
formulace:          "MLE TOP10 ma kladnou alpha i bez IRC potvrzeni (HEADWIND)."
kriteria_potvrzeni: "alpha(TOP10, HEADWIND) > 0"
kriteria_zamitnutí: "alpha(TOP10, HEADWIND) <= 0"
```

### Hypothesis H-002

```yaml
formulace:          "MLE 11-20 a 21-30 potrebuji IRC TOP10 potvrzeni
                     pro kladnou alpha (HEADWIND je zaporna nebo nulova,
                     IRC_TOP je kladna)."
kriteria_potvrzeni: "alpha(11-30, HEADWIND) <= 0 AND alpha(11-30, IRC_TOP) > 0"
kriteria_zamitnutí: "Zadny rozdil mezi HEADWIND a IRC_TOP v tomto pasmu"
```

### Hypothesis H-003

```yaml
formulace:          "MLE 51+ zustava negativni i s IRC TOP10 potvrzenim
                     (IRC nedokaze zachranit slabe MLE kandidaty)."
kriteria_potvrzeni: "alpha(51+, IRC_TOP) <= 0"
kriteria_zamitnutí: "alpha(51+, IRC_TOP) > 0.5pp"
```

---

## Grid

```
MLE buckets: 1-10, 11-20, 21-30, 31-50, 51-70, 71-100
IRC:         TOP10, HEADWIND
= 12 kombinaci
```

Metrika: alpha vs SPY, 30D primary.

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLEBucketsIRCGrid v1.0.0 | RUNNING |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-rank-value-decay
      type: knowledge_record
    - ref: KR-2026-06-MLE-IRC-rolling
      type: knowledge_record
  inspired:
    - ref: "budouci: Decision Resolver priority tiers (formalni navrh)"
      type: observation
  produced_rules: []
```
