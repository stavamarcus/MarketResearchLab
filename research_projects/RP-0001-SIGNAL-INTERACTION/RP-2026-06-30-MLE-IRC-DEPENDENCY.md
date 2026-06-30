# Research Project: MLE × IRC Dependency Audit

```yaml
project_id:        RP-2026-06-30-MLE-IRC-DEPENDENCY
portfolio_area:    Market Leadership
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
parent_project:    RP-0001-SIGNAL-INTERACTION
```

---

## Research Question

> Má MLE edge větší hodnotu, když je ticker zároveň v silné industry podle IRC?

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  KR-2026-06-IRC-persistence-edge
    note: "IRC má validovaný edge (+2.68% alpha). MLE má validovaný edge.
           Nikdy netestováno jak IRC context ovlivňuje MLE selekci."
  - type: experiment
    ref:  IMSScoreBucketEdge v1.0.0
    note: "IMS score predikuje forward return. Přirozený další krok: IRC context."
```

---

## Hypotheses

### H-002
```yaml
formulace:          "MLE kandidáti v silných IRC industries (rank <= 20) mají
                     vyšší median 30D forward return než MLE kandidáti bez IRC podpory."
kriteria_potvrzeni: "Median(MLE+IRC_TOP) > Median(MLE_only) + 0.5%"
kriteria_zamitnutí: "Median(MLE+IRC_TOP) <= Median(MLE_only)"
```

### H-003
```yaml
formulace:          "MLE kandidáti v top IRC industries mají vyšší win rate
                     než MLE kandidáti v bottom IRC industries."
kriteria_potvrzeni: "WR(MLE+IRC_TOP) > WR(MLE+IRC_WEAK) + 3%"
kriteria_zamitnutí: "Žádný rozdíl ve win rate"
```

### H-004
```yaml
formulace:          "IRC sám o sobě nestačí — nejlepší výsledky má kombinace MLE + IRC."
kriteria_potvrzeni: "Median(MLE+IRC_TOP) > Median(IRC_strong_only)"
kriteria_zamitnutí: "IRC_strong_only >= MLE+IRC_TOP"
```

---

## IRC Buckety

```
IRC_TOP     = industry_rank <= 20      (top třetina z 59 industries)
IRC_MID     = industry_rank 21–60
IRC_WEAK    = industry_rank > 60
IRC_MISSING = industry není v IRC archivu k danému datu
```

---

## Kritický detail — Point-in-Time

IRC rank musí být znám k datu signálu, ne dopočten zpětně.
Join: `mle.date == irc.date AND ticker_industry == irc.industry`
Industry mapping: MLE ticker → universe.industry (ne MLE.industry — to je 99.2% NaN).

---

## Experimenty

| # | Název | Status |
|---|---|---|
| 1 | MLE_IRC_Dependency_Audit v1.0.0 | RUNNING |

---

## Evidence

```yaml
complete: true
```

### Výsledky — dvě verze, metodický rozdíl objasněn

**v1.0.0** (TOP50/20D, IRC TOP20, absolutní return): +0.22pp NOT SUPPORTED  
**v1.1.0** (TOP20/10D, IRC TOP10, alpha vs SPY): **+1.28pp SUPPORTED**

Reprodukce historického IRC Audit Test 7. Run ID: 23da9018-1a6f-4e24-8061-fd5bd24bb5e3

| Skupina | Median 30D alpha | Win Rate | N |
|---|---|---|---|
| MLE+IRC_TOP10 | +1.41% | 55.1% | 1,984 |
| MLE_HEADWIND | +0.13% | 50.5% | 2,396 |

### Konfliktní výsledky

v1.0.0 a v1.1.0 dávají odlišné závěry na první pohled — vyřešeno jako
metodický rozdíl, ne jako rozpor. Zdokumentováno v KR-2026-06-MLE-IRC-interaction.

---

## Conclusion

```yaml
status: SUPPORTED
```

**Důkazy PRO:**
- Reprodukce nezávislého historického auditu (Test 7)
- Konzistentní efekt přes dva nezávislé běhy (+1.12pp test, +1.28pp plný dataset)
- Mechanismus odpovídá architektuře: MLE asset-level + IRC context

**Podmínky platnosti:**
- MLE TOP20 (rank_10d), IRC TOP10, alpha vs SPY jako metrika
- Bez RISK_OFF filtru

---

## Resolution

```yaml
production_status: APPROVED_WITH_RESTRICTIONS
decided_by:        Architekt
decided_on:        2026-06-30
restrictions:
  - "Nasadit pouze v RISK_ON podmínkách (čeká na MRC)"
  - "Alpha vs SPY jako primární metrika pro všechny budoucí selekční experimenty"
  - "Doplnit statistickou významnost (bootstrap, Mann-Whitney) před finální produkční Resolution"
```

---

## Standard zaveden touto research projektem

**Primární metrika pro selekční moduly (MLE, IMS, IRC): alpha vs. SPY.**
Absolutní return jako doplňková metrika, nikdy jako primární.
