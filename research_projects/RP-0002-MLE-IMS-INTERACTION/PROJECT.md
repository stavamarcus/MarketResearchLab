# Research Project: MLE x IMS Signal Interaction

```yaml
project_id:        RP-0002-MLE-IMS-INTERACTION
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Je kombinace MLE a IMS lepsi nez kazdy modul samostatne?
> Pridava silna institucionalni podpora (IMS) hodnotu k cenovemu leadershipu (MLE)?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  KR-2026-06-MLE-IRC-interaction
    note: "Standard alpha vs SPY zaveden timto KR. Pouzit od zacatku."
  - type: knowledge_record
    ref:  KR-2026-06-IMS-score-buckets
    note: "IMS edge potvrzen (s vyhradou absolutniho returnu)."
  - type: legacy_audit
    ref:  "IMS_audit/tests/overlap_analysis.py"
    note: "Legacy logika IMS x MLE overlap - kandidat pro inspiraci metodiky."
```

**Motivace:**
MLE meri relativni silu ceny (price leadership).
IMS meri institucionalni kvalitu a momentum.
Teoreticky prekryv obou by mel identifikovat akcie s nejsilnejsim
kombinovanym signalem.

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
formulace:          "MLE TOP20 akcie s IMS score >= 90 (ELITE) dosahuji
                     vyssi median 30D alpha vs SPY nez MLE TOP20 samotne."
ocekavany_efekt:    "Median(MLE+IMS_ELITE) > Median(MLE_only) + 0.5pp alpha"
podminky:           "S&P 500, alpha vs SPY jako primarni metrika (standard)."
kriteria_potvrzeni: "Spread > 0.5pp, N >= 20"
kriteria_zamitnutí: "Spread <= 0, nebo N < 20"
```

### Hypothesis H-002

```yaml
id:                 H-002
formulace:          "MLE+IMS kombinace prevysuje kazdy modul samostatne
                     (MLE only i IMS only)."
ocekavany_efekt:    "Median(MLE+IMS) > max(Median(MLE_only), Median(IMS_only))"
kriteria_potvrzeni: "Kombinace je nejlepsi skupina ze vsech testovanych"
kriteria_zamitnutí: "Kombinace neni lepsi nez alespon jeden samostatny modul"
```

### Hypothesis H-003

```yaml
id:                 H-003
formulace:          "Vyssi IMS score (90-94 vs 80-89) v kombinaci s MLE
                     prinasi monotonne vyssi alpha."
ocekavany_efekt:    "Median(MLE+IMS_90-94) > Median(MLE+IMS_80-89)"
kriteria_potvrzeni: "Monotonni rust alpha s IMS bucketem"
kriteria_zamitnutí: "Zadny monotonni vztah"
```

---

## Skupiny

```
MLE_ONLY          — MLE TOP20 (rank_10d), bez ohledu na IMS
IMS_ONLY          — IMS score >= 80, bez ohledu na MLE rank
MLE+IMS_70-79     — MLE TOP20 + IMS 70-79
MLE+IMS_80-89     — MLE TOP20 + IMS 80-89
MLE+IMS_90-94     — MLE TOP20 + IMS 90-94 (ELITE)
MLE+IMS_MISS      — MLE TOP20, IMS score < 70 nebo chybi
```

Metrika: alpha vs SPY (30D primary), win rate, N.
Point-in-time: IMS score znamy k datu MLE signalu (oba jsou ASSET-level
k stejnemu datu — bez joinu pres industry, jednodussi nez MLE x IRC).

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | MLEIMSInteraction v1.0.0 | PLANNED |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-interaction
      type: knowledge_record
      note: "Standard alpha vs SPY a uspesna metodika MLE x context testu"
    - ref: "IMS_audit/tests/overlap_analysis.py"
      type: audit
      note: "Legacy MLE x IMS overlap logika"
  inspired: []
  produced_rules: []
```
