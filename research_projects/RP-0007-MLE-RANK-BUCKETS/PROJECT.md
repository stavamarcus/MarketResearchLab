# Research Project: MLE Rank Buckets — Kompletni profil

```yaml
project_id:        RP-0007-MLE-RANK-BUCKETS
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Jak rychle klesa informacni hodnota MLE ranku?
> Kde konci edge — a je hranice TOP20/TOP50 informovana, nebo arbitrarní?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-robustness
    note: "Grid testoval pouze MLE TOP10/20/30/50. Nikdy nebyl testovan
           profil za hranici TOP50."
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-rolling
    note: "MLE x IRC dosahl HIGH confidence, ale vzdy v ramci TOP10-50.
           Tento projekt zjistuje, zda je tato hranice spravna."
```

**Motivace:** Implicitne predpokladame TOP20 > TOP50 > ostatni, ale nikdy
jsme to systematicky neotestovali nad ramec TOP50. Bucket 51-70 je prvni
nejlevnejsi test za soucasnym prahem — bud potvrdi spravnost hranice,
nebo odhali ze zahazujeme kvalitni kandidaty.

---

## Hypotheses

### Hypothesis H-001

```yaml
formulace:          "Median 30D alpha vs SPY monotonne klesa s rostoucim
                     MLE rank_10d bucketem (Elite > Strong > ... > Tail)."
ocekavany_efekt:    "Monotonni nebo priblizne monotonni pokles alpha"
kriteria_potvrzeni: "Alespon 5 ze 6 prechodu mezi sousednimi buckety
                     ma nezaporny smer (vyssi bucket <= nizsi alpha)"
kriteria_zamitnutí: "Zadny jasny trend, nebo opacny smer"
```

---

## Buckety

```
Elite      1-10
Strong     11-20
Good       21-35
Moderate   36-50
Watch      51-70
Weak       71-100
Tail       101-150
```

Metrika: alpha vs SPY (standard), 30D primary, 10D/20D sekundarni.
Win rate, N per bucket.

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLERankBuckets v1.0.0 | RUNNING |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-robustness
      type: knowledge_record
      note: "Grid omezeny na TOP10-50 — tento projekt rozsiruje profil"
  inspired: []
  produced_rules: []
```
