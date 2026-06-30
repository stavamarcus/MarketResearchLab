# Research Project: IMS Score Edge

```yaml
project_id:        RP-2026-06-IMS-SCORE-EDGE
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-29
last_updated:      2026-06-29
```

---

## Účel

**Reference Experiment #2.**

Primární cíl: ověřit MRL end-to-end pipeline s reálnými IMS signály.
- Research Project → Experiment → ResearchQuery → Result → Report → Registry

Sekundární cíl: změřit zda IMS score predikuje forward return.

---

## Research Question

> Dosahují akcie s vyšším IMS skóre konzistentně vyšších forward returnů
> než akcie s nižším skóre?

---

## Background

```yaml
sources:
  - type: audit
    ref:  "IMS_audit/tests/return_analysis.py"
    note: "Existující logika — migrace výpočetní logiky, ne přepis."
  - type: knowledge_record
    ref:  "KR-2026-06-IRC-persistence-edge"
    note: "IMS ELITE (90–94): 30D Alpha +4.48%, WR 67% — validováno v IRC Audit."
```

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
formulace:          "Akcie s IMS skóre >= 90 (ELITE bucket) dosahují
                     vyššího median 30D forward returnu než akcie
                     s IMS skóre 60–69 (RADAR bucket)."
ocekavany_efekt:    "Median return ELITE > Median return RADAR.
                     Alpha > 0. N >= 30 pozorování na bucket."
podminky:           "S&P 500 universe, IMS archiv 2025-07-09 → 2026-06-27."
kriteria_potvrzeni: "Median(ELITE_30D) > Median(RADAR_30D) + 0.5%."
kriteria_zamitnutí: "Median(ELITE_30D) <= Median(RADAR_30D)."
```

---

## Experiments

| # | Název | Typ | Status | Run ID | Výsledek |
|---|---|---|---|---|---|
| 1 | IMS Score Bucket Forward Edge | Edge Validation | RUNNING | | |

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "IMS_audit/tests/return_analysis.py"
      type: audit
      note: "Reference Experiment #2 — migrace logiky do MRL frameworku"
  inspired: []
  produced_rules: []
```

---

## Evidence

```yaml
complete: true
```

### Výsledky Experiment #1 (2026-06-29)

| Bucket | N signálů | Median 30D return | Win Rate |
|---|---|---|---|
| RADAR (60-69) | viz metrics | +0.58% | — |
| H70-79 | viz metrics | — | — |
| H80-89 | viz metrics | — | — |
| H90-94 (ELITE) | viz metrics | +1.71% | — |
| H95+ | viz metrics | +2.24% | — |

**Spread ELITE–RADAR: +1.12%** (threshold: 0.5%)

**Run ID:** b7159986-8a49-49ae-95b1-8b76f8459976  
**Archiv:** results/IMSScoreBucketEdge/1.0.0/b7159986-8a49-49ae-95b1-8b76f8459976/

### Poznámka k alpha

SPY není v sp500_rank_calendar universe — alpha vs SPY nebyla počítána.
Absolutní forward return byl použit místo alpha. Budoucí verze přidá SPY jako benchmark ticker.

### Konfliktní výsledky

Žádné — monotónní nárůst returnu s rostoucím skóre (RADAR → H95+).

---

## Conclusion

```yaml
status: SUPPORTED
```

**Důkazy PRO:**
- Monotónní nárůst median 30D returnu s rostoucím IMS skóre
- Spread ELITE–RADAR: +1.12% (>threshold 0.5%)
- H95+ bucket: +2.24% median 30D

**Podmínky platnosti:**
- S&P 500 universe, datový rozsah 2025-07-09 → 2026-04-30
- Bez RISK_OFF filtru (MRC zatím neexistuje)

---

## Resolution

```yaml
production_status: APPROVED_WITH_RESTRICTIONS
decided_by:        Architekt
decided_on:        2026-06-29
restrictions:
  - "Nasadit pouze v RISK_ON podmínkách (čeká na MRC)"
  - "Validovat na rozšířeném datasetu (5 let)"
  - "KRITICKÉ: re-test s alpha vs SPY před produkčním nasazením
     (experiment použil absolutní return, standard zaveden později — viz KR)"
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "IMS_audit/tests/return_analysis.py"
      type: audit
      note: "Reference Experiment #2 — migrace logiky do MRL frameworku"
  inspired:
    - ref: "budoucí: IMS + MRC kombinace"
      type: research_project
  produced_rules: []
```


## Knowledge Record

```yaml
kr_id: KR-2026-06-IMS-score-buckets
status: ACTIVE
confidence: LOW
```

Viz `knowledge_base/KR-2026-06-IMS-score-buckets.md`
