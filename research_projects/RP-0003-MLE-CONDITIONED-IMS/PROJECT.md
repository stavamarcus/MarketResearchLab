# Research Project: MLE-Conditioned IMS Prioritization

```yaml
project_id:        RP-0003-MLE-CONDITIONED-IMS
portfolio_area:    Market Leadership
research_status:   IDEA
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          MEDIUM
```

---

## Research Question

> Pomaha IMS prioritizovat kandidaty UVNITR jiz vybraneho MLE univerza?

To je odlisna statisticka otazka nez RP-0002 (prekryv dvou nezavislych mnozin).

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-IMS-no-synergy
    note: "RP-0002 testoval prekryv MLE TOP20 a IMS bucketu jako dve
           nezavisle definovane skupiny. Hypoteza nepotvrzena.
           Tento projekt testuje jinou formulaci."
```

**Klicovy rozdil oproti RP-0002:**

RP-0002: MLE_ONLY vs MLE+IMS_buckety (obe casti jsou ruzne velke mnoziny,
nesrovnatelne primo).

RP-0003: Vsechny rezy jsou PODMNOZINY stejne zakladni mnoziny (MLE TOP20),
nebo PODMNOZINY IMS 90+. Srovnani je primejsi.

---

## Hypotheses

### Hypothesis H-001 (rez A — uvnitr MLE TOP20)

```yaml
formulace:          "Uvnitr MLE TOP20 mnoziny, akcie s vyssim IMS skore
                     dosahuji vyssi median 30D alpha nez akcie s nizsim
                     IMS skore."
ocekavany_efekt:    "Monotonni rust alpha s IMS bucketem, VSE uvnitr MLE TOP20"
kriteria_potvrzeni: "Median(MLE_TOP20 + IMS90+) > Median(MLE_TOP20 + IMS<70)"
kriteria_zamitnutí: "Zadny rozdil nebo opacny smer"
```

### Hypothesis H-002 (rez B — uvnitr IMS 90+)

```yaml
formulace:          "Uvnitr IMS 90+ mnoziny, akcie s lepsim MLE rankem
                     (TOP5 < TOP10 < TOP20 < none) dosahuji vyssi alpha."
ocekavany_efekt:    "Monotonni vztah MLE rank tightness -> alpha, VSE uvnitr IMS90+"
kriteria_potvrzeni: "Median(IMS90+ & MLE_TOP5) > Median(IMS90+ & MLE_none)"
kriteria_zamitnutí: "Zadny rozdil nebo opacny smer"
```

---

## Skupiny

**Rez A (fixed MLE TOP20):**
```
MLE_TOP20 + IMS<70
MLE_TOP20 + IMS_70-79
MLE_TOP20 + IMS_80-89
MLE_TOP20 + IMS_90+
```

**Rez B (fixed IMS90+):**
```
IMS90+ & MLE_TOP5
IMS90+ & MLE_TOP10
IMS90+ & MLE_TOP20
IMS90+ & MLE_none (mimo TOP20)
```

Metrika: alpha vs SPY (standard), 30D primary, statisticka vyznamnost
(bootstrap CI nebo Mann-Whitney) jako soucast teto generace experimentu.

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLEConditionedIMS v1.0.0 | PLANNED |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IMS-no-synergy
      type: knowledge_record
      note: "Negativni vysledek RP-0002 motivoval jemnejsi formulaci"
  inspired: []
  produced_rules: []
```
