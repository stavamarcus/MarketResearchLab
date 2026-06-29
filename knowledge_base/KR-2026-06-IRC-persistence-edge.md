# Knowledge Record: IRC Persistence Edge

```yaml
kr_id:          KR-2026-06-IRC-persistence-edge
status:         ACTIVE
confidence:     MEDIUM
evidence_level: B
created:        2026-06-28
last_reviewed:  2026-06-28
supersedes:     null
superseded_by:  null
source_project: RP-2026-06-IRC-edge (legacy audit → formalizováno)
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "IRC Audit v1-v4"
      type: audit
      note: "19 statistických testů, 269 obchodních dní backfill"

  inspired:
    - ref: RP-2026-06-MRC
      type: research_project
      note: "RISK_OFF finding → MRC jako nutný prerekvizit"

  produced_rules:
    - ref: DR-pending
      type: decision_resolver_rule
      note: "IRC + MLE edge čeká na MRC COMPLETE"
```

---

## Co bylo zjištěno

### Finding 1 — Optimální persistence pásmo je 11–16/20

Intuitivní předpoklad (čím vyšší persistence, tím lepší) je vyvrácen.

| Pásmo | Alpha (30D) | P-value | Poznámka |
|---|---|---|---|
| 11–16/20 | +2.68% | 0.000 | Optimum |
| 17–20/20 | pokles | — | Mean reversion — přeceněno |

Pásmo 17–20/20 vykazuje ostrý pokles výnosů.
Extrémně persistentní industrie jsou trhem přeceněny.

### Finding 2 — IMS + TOP7 Industry edge

Alpha: +1.07% | Validováno.

### Finding 3 — MLE + TOP7–10 Industry edge

Alpha: +1.96% | Validováno.

### Finding 4 — RISK_OFF: kritické selhání všech kombinací

**Všechny testované edge kombinace selhávají v RISK_OFF podmínkách.**

Toto je nejzásadnější finding. Bez Market Regime Classifieru systém
nedokáže určit, kdy přestat obchodovat. Žádná edge kombinace není
bezpečná pro nasazení bez RISK_ON filtru.

### Finding 5 — Disproved hypotézy

| Hypotéza | Výsledek |
|---|---|
| New Entrant bonus | Disproved |
| IMS + Persistence kombinace | Disproved |
| Persistence 17–20 je optimální | Disproved — obrácená závislost |

---

## Kdy platí

- RISK_ON tržní podmínky (podmínka nutná, ne dostatečná)
- S&P 500 vesmír (~503 instrumentů)
- Backtest: 2025-07-09 → 2026-06-23 (269 obchodních dní)
- EOD data z MDSM-Lite / IBKR

---

## Kdy neplatí

- RISK_OFF podmínky — všechny edge kombinace selhávají
- Persistence 17–20/20 — mean reversion, nepoužívat
- Mimo S&P 500 vesmír (nevalidováno)
- Kratší než 30D forward return horizon (méně stabilní)

---

## Confidence: MEDIUM — odůvodnění

- Evidence Level B: jeden backtest, 269 dní, bez rolling validation
- Absence 5-year dataset — výsledky nevalidovány na delší historii
- Absence out-of-sample validace
- RISK_OFF definice je zatím ex-post, ne prospektivní klasifikátor

Pro upgrade na MEDIUM→HIGH: potřeba rolling validation + 5-year dataset.

---

## Doporučení pro budoucí výzkum

- RP-MRC: validovat RISK_ON/RISK_OFF klasifikátor (blocker pro DR)
- RP: Rolling validation IRC persistence edge (upgrade Evidence Level B→A)
- RP: Out-of-sample test na 5-year dataset
- RP: Sensitivity pásma — 10–15 vs 11–16 vs 12–17
- RP: IRC TOP5 vs TOP7 vs TOP10 threshold
