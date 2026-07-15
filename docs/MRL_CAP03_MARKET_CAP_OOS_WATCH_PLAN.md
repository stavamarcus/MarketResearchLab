# CAP-03 Market-Cap OOS Watch Plan

**Účel:** plán budoucího OOS sledování cap efektu. Pouze plán, nespouštět.

## Pravidla (LOCKED)

```text
žádné threshold tuning — fixní buckety z CAP-00:
    Mega ≥200B | Large-high 50–200B | Large-low 10–50B | Mid 2–10B
    Small <2B | UNBUCKETED (missing/suspect)
žádná pharma exclusion
market cap = close(candidate_date) × sharesbas(PIT) (CAP-01B formule)
sanity anchor = date-konzistentní (CAP-01B)
```

## Co sledovat

```text
Mega:       proti baseline — drží median20 nad baseline v non-overlap?
Large-high: proti baseline — zůstává nediferencovaný (FAIL) nebo se mění?
Large-low:  proti baseline — drží pod baseline? (possible caution bucket)
Mid/Small:  reportovat; interpretovat jen pokud N>=30 (dosud ne)
```

## Metriky (shodné s CAP-02, pre-registrované)

```text
median20 (primární) | hit20 | non-overlap median20 (dependence kontrola)
5/10D konzistence směru | mean20 | SPY-relative (sekundární)
per-bucket: N, unique conids, unique dates, top repeated conids
```

## Datové období

```text
POUZE candidate-days s candidate_date po CAP-02 cutoffu (2026-06-27).
Deterministic FUND-03 extraction nad novými MLE/IRC archivy.
Žádný překryv s in-sample obdobím → skutečné OOS.
```

## Rozhodovací kritéria (návrh, ke schválení)

```text
cap efekt POTVRZEN OOS pokud:
    Mega drží median20 > baseline a non-overlap směr drží
    AND Large-low drží median20 < baseline
    AND směr konzistentní s in-sample
    → teprve pak kandidát na selection policy

cap efekt NEPOTVRZEN pokud:
    směr se v OOS obrací nebo mizí v non-overlap
    → režimově podmíněný artefakt, zahodit jako selection signál
```

## Mimo scope

OOS run se nespouští teď (chybí data po cutoffu). Žádná strategie,
portfolio, sizing, selection layer.
