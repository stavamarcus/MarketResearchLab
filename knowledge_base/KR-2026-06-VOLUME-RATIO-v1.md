# KR-2026-06-VOLUME-RATIO-v1

**Class:** feature-validation (technical)
**Research Project:** RP-0010-FEATURE-VOLUME
**Experiment:** VolumeRatioEdge_v1
**Status:** VALIDATED (negative result)

```yaml
run_id:       f517acad-4b9f-4f53-8488-0e00a6556cfd
result_hash:  ee5684c0de9cd6ed537b
archive:      results/VolumeRatioEdge/1.0.0/20260701_033600_f517acad/
period:       2025-07-09 → 2026-06-27
universe:     MLE TOP10 × IRC TOP10 (lookback 20D)
created:      2026-06-30
```

> KR = current best knowledge, not truth.

---

## Hypotéza (pre-registrováno, zamčeno 2026-06-30)

- **H0:** Volume Ratio nepřidává inkrementální prediktivní hodnotu nad MLE×IRC.
- **H1:** vyšší Volume Ratio koreluje s vyšším 20D forward return.

feature = Volume(D) / mean(Volume[D-19 … D]); target = 20D fwd return (SPOJITÝ);
metoda = Spearman + kvantily (interpretace) + ticker-clustered bootstrap.
ZÁMEK: žádný binární práh. Regime split DEFERRED.

## Data integrity (ověřeno před během)

- volume v D1 parquet, ale **v tisících (lots)** — pro ratio neškodné (bezrozměrné).
- MLE archiv volume NEobsahuje → feature z price provideru, ne ze signálu.
- volume as-of-close (D1 batch po close / GDU). **Q2:** intraday update téhož D1 souboru
  by vyžadoval re-audit F001.
- warmup: vol_ratio NaN prvních 19 barů → kandidát vynechán.

## Výsledky (autoritativní běh, N=978 candidate-days, 142 unikátních tickerů)

```
Spearman rho (vol_ratio vs 20D fwd): +0.0747
ticker-clustered 95%CI:              [-0.0063, +0.1457]   sig=False
naivní p (IGNOROVAT — nerespektuje dependence)
```

Kvantilové koše (JEN interpretace, ne edge definice):
```
Q1_low   mean_fwd nejnižší
Q2–Q5    ploché (nerozlišitelné)
Q5-Q1 spread: +5.70pp   (NEmonotónní — viz exploratorní pozorování)
```

## Závěr

**H1 NOT SUPPORTED. H0 NEZAMÍTNUTA.**

Volume Ratio nemá statisticky podložený monotónní prediktivní vztah k 20D forward
returnu nad MLE×IRC kandidáty. Spearman rho +0.0747, CI[-0.006, +0.146] obsahuje nulu.

Pozn.: rho je blízko horní části pásma, ale CI jasně obsahuje nulu → NEčíst jako
„skoro signifikantní". V hypotéza-testovacím rámci: H1 not supported, tečka.

**Volume Ratio se NEPROMUJE jako feature do MSL.**

## Exploratorní pozorování (NE validovaný edge)

Kvantily nejsou monotónní: zaostává jen spodní kvantil (nízký volume), zbytek plochý.
To vysvětluje Spearman ~0 — efekt (pokud existuje) je prahový na spodním konci, ne
spojitý. Binární split na medián by dal falešně pozitivní výsledek.

**Post-hoc pozorování na koších — NENÍ nález.** Práh byl inspirován týmiž daty;
test na nich = data snooping. Zapsáno jako **F001b (Low Volume Penalty)** do feature
backlogu — vyžaduje vlastní předregistrovaný test, a-priori práh, NE stejná data.

## Caveats

- Rozsah: MLE×IRC leadeři, 2025-07 → 2026-06, hold 20D. Single ~1Y window; regime deferred.
- Dependence: nominal N=978, tickerů=142 (poměr 0.15) → efektivní N << nominal;
  signifikance jen z ticker-clustered bootstrapu.
- Kvantilové jevy = interpretace, ne edge.

## Architektonický dopad

- První Feature Validation experiment → třída funguje stejným protokolem (potvrzeno).
- **Negativní výsledek = actionable knowledge:** nejjednodušší volume feature nepřidává
  spojitý edge. NErozšiřovat na Relative Volume / Up-Down / Accumulation (variace téže
  myšlenky). Další feature má být kvalitativně JINÁ (jiná vlastnost firmy/trhu).
- Jediná dceřinná hypotéza hodná budoucího testu: F001b (Low Volume Penalty), čistě
  předregistrovaná.
