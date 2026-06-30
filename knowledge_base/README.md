# Knowledge Base

Kumulativní znalostní databáze Market Research Lab.

**Principy:**
- Knowledge Record není pravda — je to aktuální nejlepší poznatek.
- Starý KR se nikdy nemaže — dostane `status: SUPERSEDED`.
- Výzkum je kumulativní. Každý KR odkazuje na předchůdce i nástupce.
- I REJECTED výsledky jsou cenné — zabraňují opakování.

---

## Evidence Level

| Level | Kritéria |
|---|---|
| A | Více experimentů, rolling validation, N > 500, stabilní výsledky |
| B | Základní backtest, N > 100, bez rolling validation |
| C | Explorace, malý N, předběžné výsledky |

## Confidence

| Level | Meaning |
|---|---|
| HIGH | Splněna kritéria Evidence Level A(-), konzistentní napříč více nezávislými typy validace (single-point + threshold robustness + time-window robustness) |
| MEDIUM-HIGH | Evidence Level B+, vícenásobná validace (grid/robustness), bez rolling validation |
| MEDIUM | Evidence Level B nebo A s omezeními |
| LOW | Evidence Level C nebo konfliktní výsledky |

---

## Doporuceny vstupni bod

**KR-2026-06-MLE-IRC-SYNTHESIS** — syntetizuje 5 samostatnych MLE x IRC
KR do jednoho referencniho dokumentu. Zacnete zde, pokud chcete pochopit
MLE x IRC linii poznani bez nutnosti cist vsech pet zdrojovych dokumentu.

## Index

| KR ID | Oblast | Téma | Status | Confidence | Evidence |
|---|---|---|---|---|---|
| KR-2026-06-IRC-persistence-edge | Industry Rotation | IRC Persistence Edge, RISK_OFF selhání | ACTIVE | MEDIUM | B |
| KR-2026-06-MLE-IRC-interaction | Market Leadership | MLE+IRC TOP10 alpha +1.28pp, alpha vs SPY standard | ACTIVE | MEDIUM | B |
| KR-2026-06-IMS-score-buckets | Market Leadership | IMS score edge +2.14pp (absolutní return — nutný re-test s alpha) | ACTIVE | LOW | B |
| KR-2026-06-MLE-IMS-no-synergy | Market Leadership | MLE×IMS overlap hypotéza nepotvrzena — jiná formulace doporučena | ACTIVE | LOW | B |
| KR-2026-06-IMS-missing-diagnosis | Market Leadership | Vysvětlení IMS_MISSING — 95.8% je score<60, ne chyba dat | ACTIVE | MEDIUM | B |
| KR-2026-06-IMS-within-MLE | Market Leadership | IMS jako prioritizace v MLE TOP20 — slabý efekt +0.84pp | ACTIVE | MEDIUM | B |
| KR-2026-06-MLE-IRC-robustness | Market Leadership | MLE×IRC grid 16/16 kladný diff — primární edge kandidát | ACTIVE | MEDIUM-HIGH | B+ |
| KR-2026-06-MLE-IRC-rolling | Market Leadership | MLE×IRC — 3 nezávislé validace, nejlépe podložený kandidát | ACTIVE | HIGH | A- |
| KR-2026-06-MLE-rank-value-decay | Market Leadership | MLE rank decay TOP10→TOP100, hranice edge mezi TOP30-50 | ACTIVE | MEDIUM-HIGH | B+ |
| KR-2026-06-IRC-persistence-standalone | Industry Rotation | IRC samostatně NEpřekonává trh — slabý kandidát na druhý edge | ACTIVE | LOW | B |
| KR-2026-06-MLE-buckets-IRC-multiplier | Market Leadership | IRC = multiplikátor síly (TOP10), ne záchranný filtr (21-30 hůř) | ACTIVE | MEDIUM-HIGH | B+ |
| **KR-2026-06-MLE-IRC-SYNTHESIS** | Market Leadership | **Syntéza 5 MLE×IRC KR — doporučený vstupní bod** | ACTIVE | HIGH | A- |

---

## Konvence pojmenování

```
KR-{YYYY-MM}-{projekt}-{téma}.md
```

## Supersede konvence

```
KR-2026-06-IRC-persistence-edge      status: SUPERSEDED → superseded_by: KR-2027-03-...
KR-2027-03-IRC-persistence-edge-v2   status: ACTIVE     ← rozšířená data, rolling validation
```
