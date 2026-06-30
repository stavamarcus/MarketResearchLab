# Signal Provider Contract Validation

**Datum:** 2026-06-29  
**Rozsah:** MDSMSignalProvider — všechny čtyři loadery  
**Datový rozsah testu:** 2025-10-01 → 2026-01-31  
**Verze:** Krok 1.1

---

## Účel

Ověřit, že `MDSMSignalProvider` vrací data ve formátu kompatibilním
s MRL kontraktem — ne jen načtené CSV soubory.

MRL kontrakt vyžaduje:
- jednotný datový typ pro `date`
- `ticker → conid` mapping (Feature.conid je povinný)
- explicitní `feature_name` (ne CSV sloupec)
- explicitní `source_module`
- žádné NaN v klíčových sloupcích

---

## Výsledky — Check by Check

### CHECK 1 — Date column type ✅

Všechny loadery vrací `datetime64[us]`.

| Modul | dtype | Status |
|---|---|---|
| MLE | datetime64[us] | ✅ OK |
| IMS | datetime64[us] | ✅ OK |
| IRC | datetime64[us] | ✅ OK |
| breadth | datetime64[us] | ✅ OK |

---

### CHECK 2 — Ticker → conid mapping ✅

| Modul | Mapped | Total | Pokrytí |
|---|---|---|---|
| MLE | 497 | 497 | 100.0% |
| IMS | 401 | 401 | 100.0% |

Universe (sp500_rank_calendar) pokrývá všechny tickery v archivech.

---

### CHECK 3 — IRC/breadth conid absence ⚠️ STRUCTURAL FINDING

**IRC** je industry-level signál. Neobsahuje `conid` ani `ticker` — identifikátor je `industry` (string).

**breadth** je market-level signál. Neobsahuje `conid` ani `ticker` — jeden řádek = celý trh.

`Feature.conid` je povinný `int` dle Domain Model.

→ **IRC a breadth nelze přímo převést na `Feature` objekty.**

Toto je strukturální nález — viz `ARCHITECTURE_CANDIDATE_FINDINGS.md` ACF-005.

---

### CHECK 4 — Feature name mapping ✅

Všechny klíčové MLE sloupce jsou přítomny a mapovatelné na MRL feature names:

| CSV sloupec | Feature name | Status |
|---|---|---|
| rank_20d | MLE_Rank_20d | ✅ |
| ret_20d | MLE_Ret_20d | ✅ |
| rank_10d | MLE_Rank_10d | ✅ |
| ret_10d | MLE_Ret_10d | ✅ |
| rank_5d | MLE_Rank_5d | ✅ |
| ret_5d | MLE_Ret_5d | ✅ |
| rank_1d | MLE_Rank_1d | ✅ |
| ret_1d | MLE_Ret_1d | ✅ |

IMS feature map:

| CSV sloupec | Feature name | Status |
|---|---|---|
| score | IMS_Score | ✅ |
| priority_group | IMS_Priority_Group | ✅ |
| rs_vs_spy_20d | IMS_RS_vs_SPY_20d | ✅ |
| rank_improvement_20d | IMS_Rank_Improvement_20d | ✅ |
| rank_stability_20d | IMS_Rank_Stability_20d | ✅ |

---

### CHECK 5 — Feature objekt sestavitelný ✅

MLE a IMS lze převést na `Feature` objekty:

```
Feature(conid=292080616, date=2025-10-01, name='MLE_Rank_20d', value=329.0)
Feature(conid=99831145,  date=2025-10-01, name='MLE_Rank_20d', value=330.0)
Feature(conid=95514904,  date=2025-10-01, name='MLE_Rank_20d', value=331.0)
```

3/3 OK. ticker→conid lookup přes universe funguje.

---

### CHECK 6 — source_module explicitní ⚠️ INFO

`source_module` není v raw DataFrame — musí být přidán v `load_features()`.

Aktuální `load_signals()` vrací raw data bez `source_module`.
`load_features()` (skeleton) je místo kde se normalizace odehraje.

Není to architektonický problém — je to implementační úkol pro `load_features()`.

---

### CHECK 7 — NaN v klíčových sloupcích ✅

| Modul | Sloupec | NaN | Status |
|---|---|---|---|
| MLE | rank_20d | 0 (0.0%) | ✅ |
| MLE | ret_20d | 0 (0.0%) | ✅ |
| MLE | ticker | 0 (0.0%) | ✅ |
| IMS | score | 0 (0.0%) | ✅ |
| IMS | priority_group | 0 (0.0%) | ✅ |
| IMS | ticker | 0 (0.0%) | ✅ |

---

## Celkové hodnocení

| Check | Status | Poznámka |
|---|---|---|
| Date type | ✅ | datetime64[us] jednotný |
| Ticker→conid | ✅ | 100% pokrytí |
| IRC/breadth conid | ⚠️ | Strukturální nález — viz ACF-005 |
| Feature name mapping | ✅ | CSV sloupce → MRL feature names definovány |
| Feature objekt | ✅ | MLE a IMS lze sestavit |
| source_module | ⚠️ | Info — doplnit v load_features() |
| NaN klíčové | ✅ | 0 NaN |

---

## Závěr

**MLE a IMS jsou připraveny pro `load_features()` implementaci.**

Ticker→conid mapping přes universe funguje na 100 %.
Feature objekty lze sestavit. feature_name konvence je definována.

**IRC a breadth vyžadují architektonické rozhodnutí** (viz ACF-005)
o tom, jak reprezentovat industry-level a market-level signály
v rámci `Feature` kontraktu který vyžaduje `conid`.

---

## Doporučení pro Reference Experiment #2

Vybrat experiment který používá **pouze MLE nebo IMS** signály —
kde `load_features()` je plně implementovatelný bez architektonického rozhodnutí
o IRC/breadth.

Kandidát: **IMS Score Edge** — testuje zda vyšší IMS score predikuje
vyšší forward return. Čistý ticker-level experiment, jen IMS data.
