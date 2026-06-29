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
| HIGH | Splněna kritéria Evidence Level A, konzistentní napříč podmínkami |
| MEDIUM | Evidence Level B nebo A s omezeními |
| LOW | Evidence Level C nebo konfliktní výsledky |

---

## Index

| KR ID | Oblast | Téma | Status | Confidence | Evidence |
|---|---|---|---|---|---|
| KR-2026-06-IRC-persistence-edge | Industry Rotation | IRC Persistence Edge, RISK_OFF selhání | ACTIVE | MEDIUM | B |

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
