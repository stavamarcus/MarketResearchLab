# KR-2026-06-RS-ACCEL-v1 (DRAFT — pending authoritative run)

**Class:** feature-validation (technical)
**Research Project:** RP-0010-FEATURE-VOLUME
**Experiment:** RSAccelEdge_v1
**Status:** VALIDATED (negative result)

```yaml
run_id:       c1c68a1f-d11d-49cf-bd34-e8fc7b940f54
result_hash:  fa6e751a0d7e0c466ad5
archive:      results/RSAccelEdge/1.0.0/20260701_040106_c1c68a1f/
period:       2025-07-09 → 2026-06-27
universe:     MLE TOP10 × IRC TOP10 (lookback 20D)
```

> KR = current best knowledge, not truth.

---

## Hypotéza (pre-registrováno, zamčeno 2026-06-30)

- **H0:** RS_Accel nepřidává prediktivní hodnotu nad MLE×IRC.
- **H1:** vyšší RS_Accel koreluje s vyšším 20D forward return.

```
RS_Accel(D) = (close[D]/close[D-5]  - SPY[D]/SPY[D-5])
            - (close[D]/close[D-20] - SPY[D]/SPY[D-20])
obě RS okna KONČÍ dnem D | 5D=krátkodobé zrychlení, 20D=swing kontext
target = 20D fwd (spojitý) | Spearman + kvantily | ticker-clustered bootstrap
warmup ≥20 barů | ZÁMEK: žádný práh, žádný window sweep | regime DEFERRED
```

## Výsledky (autoritativní běh, N=976, 142 unikátních tickerů)

```
Spearman rho (rs_accel vs 20D fwd): -0.0905   ← ZÁPORNÉ
ticker-clustered 95%CI:             [-0.1993, +0.032]   sig=False (přes nulu)
```

Kvantilové koše (JEN interpretace, ne edge definice):
```
Q1_low  (rs_accel -0.73 … -0.26)  mean_fwd +11.29%   N=210   ← NEJVYŠŠÍ fwd
Q2                                 +6.00%
Q3                                 +7.21%
Q4                                 +4.67%
Q5_high (rs_accel -0.03 … +0.23)   +5.68%
Q5-Q1 spread: -5.264pp   ← ZÁPORNÝ
```

## Závěr

**H1 NOT SUPPORTED. H0 NEZAMÍTNUTA.**

RS_Accel (5D−20D) jako spojitý POZITIVNÍ prediktor nepřidává validovaný edge nad
MLE×IRC. Náznak jde OPAČNĚ než H1 (rho -0.09, decelerace → vyšší fwd), ale
**nesignifikantně** (CI [-0.1993, +0.032] přes nulu). Nelze tvrdit ani „decelerace
je edge".

**RS_Accel se NEPROMUJE jako feature do MSL.**

## Exploratorní pozorování (NE validovaný nález)

Q1 (nejnižší RS_accel = decelerující kandidáti) měl nejvyšší forward (+11.3 %),
spread Q5-Q1 záporný. Možný mechanismus (SPEKULACE): decelerace uvnitř už-silných
leaderů = zdravý oddech před pokračováním; nejvyšší akcelerace = přehřátí / blízko
lokálního vrcholu → mean reversion. Rezonuje s entry-edge nálezem z opačné strany
(pullback timing vs stav v den signálu), ale je to POUZE hypotéza.

**NENÍ nález:** rho nesignifikantní, a KNOWN LIMITATION — RS_Accel se překrývá s MLE
selection (MLE rank ~10D RS), takže i signifikantní výsledek nemusí být nezávislý edge.
Neoptimalizovat na stejných datech. Zapsáno jako F002b (Deceleration Within Leaders)
do backlogu — samostatný předregistrovaný test, ideálně víc dat / OOS.

## Caveats

- Rozsah: MLE×IRC leadeři, 2025-07 → 2026-06, hold 20D. Single ~1Y window; regime deferred.
- Dependence: nominal N=976, tickerů=142 → efektivní N << nominal; signifikance jen
  z ticker-clustered bootstrapu.
- KNOWN LIMITATION: RS_Accel není nezávislá na MLE selection (překryv v RS logice).
- Kvantilové jevy = interpretace, ne edge.

## Architektonický dopad

- Druhý Feature Validation experiment, druhý negativní výsledek.
- Actionable: jednoduchá RS akcelerace (pozitivní směr) nepřidává edge nad MLE×IRC.
  Zajímavější je nečekaný záporný náznak — ale ten je exploratorní a confounded překryvem.
- Zatím dvě negativní technické features (Volume Ratio, RS Accel).
  ROZSAH TVRZENÍ: prokázáno POUZE, že tyto dvě konkrétní cenové/objemové featury nepřidaly
  edge. NEPLYNE z toho "selection nese většinu edge" — to je kvantitativní tvrzení o
  rozdělení edge mezi vrstvy, které NEBYLO měřeno (exit/regime/fundamenty netestovány).
  Slabý náznak: inkrementální edge nebude v jednoduchých DERIVÁTECH téže cenové informace
  → posunout prior ke kvalitativně jiným datům. Podíl edge selection vs ostatní = neznámý.
- Nečekaný záporný náznak RS_Accel (Q5 přehřátí, Q1 decelerace → vyšší fwd) je druhý
  nezávislý signál stejného směru jako entry-edge (síla navíc uvnitř leaderů = spíš
  kontraindikátor). NENÍ nález (nesignif. + confounded). Hodné budoucí předregistrace
  jako "mean reversion within leaders", NE dalšího momentum filtru. Viz F002b.
