# MRL Feature Backlog — řízená výzkumná fronta

Ne seznam nápadů. Řízená pipeline. Každá položka projde:
`Hypotéza → Předregistrace → Experiment → KR → (pokud projde) MSL`.

## Klasifikace (viz TAXONOMY.md)

```
Category:  Technical / Fundamental / Market-Regime / Entry-C(onfirmation)
Status:    READY (testovatelné teď) | BLOCKED (chybí prerekvizita)
Blocked By: konkrétní prerekvizita — odděluje „slibné" od „teď měřitelné"
```

Pravidlo pořadí: řadit podle **Status (READY první) × potenciál**, NE jen podle
atraktivity. Vysoký potenciál + BLOCKED ≠ další krok (viz fundamenty).

---

## Fronta

| ID | Feature | Category | Hypotéza (co měří) | Status | Blocked By |
|----|---------|----------|--------------------|--------|------------|
| F001 | Volume Ratio | Technical | Vol(D)/SMA20(Vol) — spojitý vztah k 20D fwd | **DONE** — H1 not supported (KR-VOLUME-RATIO-v1) | — |
| F001b | Low Volume Penalty | Technical | Nízký vol ratio (<~0.77) predikuje podprůměrný fwd? (exploratorní z F001) | READY* | a-priori práh, NE stejná data |
| F002 | RS Acceleration | Technical | (5D RS − 20D RS vs SPY) — spojitý vztah k 20D fwd | **DONE** — H1 not supported, rho záporný nesignif. (KR-RS-ACCEL-v1) | — |
| F002b | Deceleration Within Leaders | Technical | Nízký/záporný RS_Accel → vyšší fwd? (exploratorní z F002, confounded MLE překryvem) | Exploratory / Not validated | separate preregistered test, víc dat / OOS |
| F002r | Relative Volume | Technical | Vol(D) vs typický vol jména (rel. k historii) | READY | — |
| F003 | Gap Size | Technical | Velikost gapu open(D)/close(D-1) jako feature kvality | READY | — |
| F004 | ATR / ADR | Technical | Volatilita kandidáta v D — koreluje s forward? | READY | — |
| F005 | Volatility Compression | Technical | Úzká konsolidace před signálem (potřebuje definici) | READY | def. báze |
| F006 | Revenue Growth | Fundamental | Přidává růst tržeb inkrement nad MLE×IRC? | BLOCKED | Sharadar + depth |
| F007 | EPS Growth | Fundamental | Růst EPS | BLOCKED | Sharadar + depth |
| F008 | ROE | Fundamental | Kvalita kapitálu | BLOCKED | Sharadar + depth |
| F009 | Gross / Operating Margin | Fundamental | Marže | BLOCKED | Sharadar + depth |
| F010 | Debt / Equity | Fundamental | Zadlužení | BLOCKED | Sharadar + depth |
| F011 | Free Cash Flow | Fundamental | FCF | BLOCKED | Sharadar + depth |
| F012 | SPY Trend | Market-Regime | Podmiňuje trend SPY ostatní faktory? (stratifikace, ne aditivní) | BLOCKED | approved regime labels |
| F013 | Market Breadth | Market-Regime | Breadth jako režimová vrstva | BLOCKED | approved regime labels |
| F014 | VIX Regime | Market-Regime | VIX pásmo jako podmiňující proměnná | BLOCKED | approved regime labels |
| F015 | Sector Breadth | Market-Regime | Šířka síly sektoru | BLOCKED | approved regime labels |

### Entry-Confirmation (patří do Entry Validation, ne Feature — mění množinu)

| ID | Feature | Category | Hypotéza | Status | Blocked By |
|----|---------|----------|----------|--------|------------|
| E005 | Follow-Through 3D | Entry-C | Vstup po D→D+3 síle (obrácený pullback) | READY | přísný protokol* |
| E006 | Follow-Through 5D | Entry-C | Táž hypotéza, 5D okno | READY | přísný protokol* |

\* Entry-C dědí protokol EntryTimingEdge: matched + skipped return + strategy-level
net + ticker-clustered. Práh (>3 %) fixovat a priori NEBO použít spojitý target
(korelace D→D+3 s D+3→D+23), aby se předešlo multiple-testing přes práh.

---

## Prerekvizity (co odblokuje které kategorie)

**Sharadar + depth** (odblokuje F006–F011):
1. Sharadar Fundamentals provider (PIT přes filing date, as-reported).
2. **Depth prerequisite (bottleneck):** MLE×IRC candidate pool ~1 rok. Dvě nezávislé
   zdi: (A) hloubka cen (D1 cache ~2 roky) a (B) point-in-time S&P 500 membership.
   Bez obou nemá fundamentální validace robustní vzorek — feasibility check PŘED nákupem
   Sharadaru.

**Approved regime labels** (odblokuje F012–F015):
- Chybí schválený Regime Engine / štítky. POZOR: regime je pravděpodobně **podmiňující**
  proměnná (multiplikativní), ne samostatný aditivní edge. Testovat jako stratifikaci
  přes ostatní faktory, ne izolovaně „přidává regime edge?". Přijde AŽ PO aspoň jednom
  faktoru, který jím lze podmínit (jinak není co stratifikovat).

---

## Doporučené pořadí (READY první)

```
1. F001 Volume Ratio        — první Feature Validation experiment (jedna feature)
2. F002/F003 pokud F001 projde nebo jako kontrast
3. E005 Follow-Through 3D   — Entry-C, přísný protokol
   ...
   feasibility check depth → teprve pak fundamentální větev (F006+)
   regime (F012+) až po aspoň jednom podmínitelném faktoru
```

Potenciál (pracovní hypotéza, NE závěr z dat — založeno na tom, co už vyvráceno):
další entry timing nízký · volume střední · fundamenty vysoký potenciál/nízká
testovatelnost teď · regime velmi vysoký ale podmiňující (ne samostatný).
