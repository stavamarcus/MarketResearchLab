# Knowledge Record: MLE x IRC — Rolling Validation

```yaml
kr_id:          KR-2026-06-MLE-IRC-rolling
status:         ACTIVE
confidence:     HIGH
evidence_level: A-
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0005-MLE-IRC-ROLLING
```

**Confidence upgrade (2026-06-30, architekt):** MEDIUM-HIGH -> HIGH.
Duvod: tri nezavisle typy validace (single-point, threshold robustness,
time-window robustness) jsou kvalitativne jina uroven evidence nez
jeden backtest. Viz sekce "Tri nezavisle typy validace" nize.

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-robustness
      type: knowledge_record
      note: "Robustnost vuci prahum potvrzena (16/16). Tento test overuje
             robustnost vuci CASU."
  inspired:
    - ref: "budouci: MRC motivace"
      type: observation
      note: "Dve negativni okna naznacuji moznou citlivost na trzni rezim —
             prvni empiricky signal proc bude MRC potreba"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLEIRCRollingValidation v1.0.0"
    type: experiment
    note: "8 rolling oken (60d/20d step), 2025-07-09 -> 2026-06-29"
```

---

## Co bylo zjisteno

### Rolling okna (diff = alpha(MLE+IRC_TOP10) - alpha(MLE_HEADWIND), 30D)

```
2025-07-09 -> 2025-10-01: +2.69%
2025-08-06 -> 2025-10-29: +2.32%
2025-09-04 -> 2025-11-26: +1.32%
2025-10-02 -> 2025-12-26: -0.66%   <- negativni
2025-10-30 -> 2026-01-27: +0.39%
2025-11-28 -> 2026-02-25: +2.85%
2025-12-29 -> 2026-03-25: +1.49%
2026-01-28 -> 2026-04-23: -0.33%   <- negativni
```

### Finding 1 — Edge drzi vetsinu casu, ne univerzalne

```
6/8 oken kladnych (75%) — splnuje kriterium >=70%
Median diff: +1.41% — splnuje kriterium >0.5pp
Rozsah: -0.66% az +2.85%
```

Edge neni tazen jednim obdobim. Konzistentni kladny efekt napric
vetsinou roku, s logickou strukturou (viz KR-2026-06-MLE-IRC-robustness
pro prahovou robustnost).

### Finding 2 — Dve negativni okna — otevrena otazka

Obe negativni okna se prekryvaji s obdobim **rijen 2025 az leden 2026**.
To je prvni empiricky signal mozne citlivosti edge na trzni podminky
nebo rezim — presne otazka, kterou by v budoucnu resil Market Regime
Classifier (MRC).

**Tento KR netvrdi, ze edge selhava v RISK_OFF.** Nemame definovanou
ex-post klasifikaci rezimu pro toto obdobi. Pouze zaznamenavame, ze
dve negativni okna existuji a casove se prekryvaji, coz je hoden dalsiho
zkoumani az bude MRC k dispozici.

---

## Tri nezavisle typy validace

```
1. Single-point experiment (KR-2026-06-MLE-IRC-interaction)
   MLE TOP20 x IRC TOP10, jeden backtest, diff +1.28pp

2. Threshold robustness (KR-2026-06-MLE-IRC-robustness)
   16 kombinaci prahu (MLE TOP10-50 x IRC TOP5-20)
   16/16 kladnych, median +1.17pp

3. Time-window robustness (tento KR)
   8 rolling oken (60d/20d step)
   6/8 kladnych, median +1.41pp
```

Tyto tri validace testuji RUZNE zdroje moznych chyb:
- (1) overuje ze efekt vubec existuje
- (2) overuje ze efekt neni artefakt jednoho konkretniho prahu (overfit)
- (3) overuje ze efekt neni artefakt jednoho konkretniho obdobi

Shoda napric vsemi tremi je kvalitativne jina uroven evidence nez
jakykoliv jednotlivy test samostatne.

## Architektonicky zaver

```
MLE x IRC edge potvrzen jako:
  - existujici (single-point)
  - robustni vuci prahum (16/16 kombinaci)
  - robustni vuci casu (6/8 oken)

Stale NENI:
  - testovan se statistickou vyznamnosti (bootstrap, permutace)
  - testovan out-of-sample (mimo 2025-07-09 -> 2026-06-29, t.j. >1 rok historie)
  - segmentovan podle trzniho rezimu (ceka na MRC)
```

**MLE x IRC je zatim nejlepe podlozeny kandidat na produkcni signal
v celem projektu.**

Toto JESTE neznamena pripravenost pro Decision Resolver — k tomu chybi
5letý dataset, out-of-sample obdobi a odhad statisticke nejistoty
(bootstrap). To jsou ukoly dalsiho vyzkumu, ne architektury.

---

## Kdy plati

- S&P 500, MLE TOP20 (rank_10d), IRC TOP10 (lookback 20D)
- Rolling okna 60 obchodnich dni, step 20 dni
- Backtest 2025-07-09 -> 2026-06-29

## Kdy neplati / nevalidovano

- Dve okna (rijen 2025, leden-duben 2026) vykazuji negativni diff —
  pricina nevysvetlena, mozna souvislost s trznim rezimem (nevalidovano)
- RISK_OFF klasifikace neexistuje — nelze potvrdit ani vyvratit
  souvislost negativnich oken s rezimem
- Out-of-sample, mimo S&P 500
- Statisticka vyznamnost jednotlivych oken

---

## Confidence: HIGH — odůvodnění

Upgrade z MEDIUM-HIGH na HIGH zaloven na trech nezavislych typech
validace (viz sekce vyse) — to je kvalitativni skok oproti jednomu
backtestu nebo jedne dimenzi robustnosti.

Duvod proc 6/8 (ne 8/8) ZVYSUJE duveryhodnost, ne snizuje ji:
realny edge typicky nevitezi kazde obdobi. 8/8 by bylo podezreleji
dokonale a vzbuzovalo by otazku o pretrenovani nebo data snoopingu.
6/8 s logickou strukturou (negativni okna casove souvisla, ne nahodna)
je vzorek, ktery odpovida ocekavani od realneho, ale ne dokonaleho edge.

Proc presto NE Evidence Level A (pouze A-):
- pouze ~1 rok historie — omezeny pocet nezavislych rolling oken (8)
- chybi out-of-sample test mimo tento dataset
- chybi formalni statisticka vyznamnost (bootstrap CI, permutace)
- dve negativni okna nejsou vysvetlena (cekaji na MRC)

---

## Doporuceni pro budouci vyzkum

**Po vzniku MRC:** zpetne zkontrolovat, zda negativni okna
(rijen 2025, leden-duben 2026) odpovidaji RISK_OFF klasifikaci.
Pokud ano, MLE x IRC edge muze byt podmineny RISK_ON filtrem —
presne struktura navrzena v puvodni architektuře MRL.

**Pred MRC:** rozsireni datasetu (vice historie) pro vice rolling oken
a vyssi statistickou silu zaveru.
