# CAP-03 Pharma Exclusion — Pre-note (dependency, nespouštět)

Pharmaceutical industry exclusion je ODLOŽEN do doby, než bude znám
market-cap profil leaders (CAP-01/CAP-02).

Důvod pořadí: pharma exclusion efekt by byl bez cap kontroly
konfundovaný s market-cap efektem (pharma jména se koncentrují
v konkrétních cap vrstvách) — test před CAP-02 by nešel interpretovat.

## Budoucí test (idea, nezávazné)

```text
baseline MLE × IRC
vs. baseline excluding Pharmaceutical industry
srovnat: returns, hit-rate, N, dependence
POVINNÁ kontrola: market-cap bucket mix obou větví
    (rozdíl výnosů dekomponovat na industry vs. cap složku)
před testem potvrdit zdroj a definici industry labelu
    (MDSM universe `industry` vs. IRC industry taxonomie — musí být týž
    slovník, jinak exclusion míří jinam než IRC signál)
```

## Stav

```text
Pharma exclusion test: BLOCKED until CAP-01/CAP-02 CLOSED
Žádný industry exclusion test se nespouští.
```
