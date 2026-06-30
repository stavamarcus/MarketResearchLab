# Research Project: IRC Persistence Edge

```yaml
project_id:        RP-0006-IRC-PERSISTENCE
portfolio_area:    Industry Rotation
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          HIGH
```

---

## Research Question

> Maji persistentne silne industries vyssi nasledne alpha
> nez kratkodobe silne nebo slabe industries?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref: KR-2026-06-MLE-IRC-rolling
    note: "MLE x IRC dosahl HIGH confidence pres tri nezavisle validace.
           Tento projekt testuje IRC SAMOSTATNE (bez MLE) jako kandidata
           na druhy nezavisly edge pro Decision Resolver."
  - type: knowledge_record
    ref: KR-2026-06-IRC-persistence-edge
    note: "Predchozi legacy finding: IRC persistence 11-16/20 = optimum.
           Tento projekt formalizuje a rozsiruje na industry-level alpha."
```

**Klicovy rozdil oproti MLE x IRC:**
```
MLE x IRC          = silna akcie v silne industry (asset-level signal)
IRC Persistence     = zda samotna industry sila ma pokracovani v case
                      (industry-level signal, BEZ MLE)
```

Pokud IRC persistence projde stejnym procesem (single-point -> robustness
grid -> rolling validation) jako MLE x IRC, ziska MRL druhy nezavisly
robustni edge.

---

## Hypotheses

### Hypothesis H-001

```yaml
formulace:          "Industries persistentne v IRC TOP10 (6-15 dni za
                     poslednich 20 obchodnich dni) maji vyssi median 30D
                     alpha nez nove vstoupive industries (1-2 dny)."
ocekavany_efekt:    "Median(PERSISTENT_TOP10) > Median(NEW_TOP10) + 0.5pp"
podminky:           "S&P 500, IRC lookback 20D, industry-level alpha vs SPY"
kriteria_potvrzeni: "Spread > 0.5pp, N >= 20 industry-observation"
kriteria_zamitnutí: "Spread <= 0"
```

---

## Buckety

```
NEW_TOP10          1-2 dny v TOP10 za poslednich 20 obch. dni
EMERGING_TOP10      3-5 dnu
PERSISTENT_TOP10    6-15 dnu
EXTENDED_TOP10       16-20 dnu
```

Metrika: industry-level alpha vs SPY (median industry return - SPY return),
30D primary, 5D/10D/20D sekundarni. Win rate, N industries.

**Jednotka analyzy:** industry-den (ne ticker-den jako u MLE testu).

---

## Experiments

| # | Nazev | Status |
|---|---|---|
| 1 | IRCPersistenceEdge v1.0.0 | RUNNING |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-rolling
      type: knowledge_record
      note: "Uspesny proces (single-point -> grid -> rolling) aplikovan
             na novy, nezavisly kandidat"
    - ref: KR-2026-06-IRC-persistence-edge
      type: knowledge_record
      note: "Legacy finding o optimalni persistence 11-16/20"
  inspired: []
  produced_rules: []
```
