# FUND-04 Edge Test Protocol (návrh — pre-registrace pro FUND-05)

**Toto je protokol, ne spuštění.** Všechny prahy a pravidla jsou
pre-registrované PŘED výpočtem jakýchkoli výnosů (leakage protokol §5).
Prahy označené PROPOSED podléhají schválení architekta; po schválení
jsou zamčené — post-hoc změna = STOP.

---

## 1. Baseline a data

```text
Baseline universe: MLE TOP10 × IRC TOP10 (20d) candidate-days
    — FUND-03 extraction (deterministic, manifest+hashe)
    — poslední známý stav: 1 144 candidate-days, 151 conidů,
      2025-07-09 → 2026-06-27
Snapshot: sf1art_20260704_005521 (pinned)
Forward returns: MDSM ceny přes MRL price provider, počítá se až
    v experiment layer (FUND-05); vstupní okna ořezávají poslední
    ~30 kalendářních dní rozsahu (20D okno + buffer)
```

## 2. Varianty (fixní pravidla, žádný optimizer)

| V | Název | Filter rule (PROPOSED prahy) | Poznámka |
|---|---|---|---|
| A | baseline only | žádný filter | referenční |
| B | quality filter | netinc > 0 AND fcf > 0 | zisková + FCF-pozitivní |
| C | growth filter | revenue_yoy > 0 | derived, 2 PIT lookupy |
| D | profitability filter | roe > 0.15 (equity > 0) | fixní práh |
| E | balance-sheet weakness exclusion | exclude de > 2.0 nebo equity <= 0 | negativní filter |
| F | composite quality bucket | splněno >= 4 z 5 podmínek {netinc>0, fcf>0, revenue_yoy>0, roe>0.15, de<=2.0} | prostý count, bez vah |

Per varianta povinně předem definováno a v reportu vykázáno:
input universe (=A), filter rule, included/excluded counts (vč.
field_null_excluded), min. sample size (viz §5), expected output
(kompletní metrická tabulka), failure condition (N < 30 ⇒ varianta
INCONCLUSIVE, ne FAIL).

Zákazy: žádný ML model, žádná optimalizace vah, žádný parameter sweep
mimo výše uvedené fixní prahy, žádný post-hoc výběr "nejlepší varianty"
jako finální závěr — reportují se VŠECHNY varianty, každá vyhodnocena
samostatně proti A.

## 3. Metriky

Povolené (gross, signal-level research):

```text
5D / 10D / 20D forward return (20D = primární okno)
mean, median (primární statistika: median 20D)
hit rate (podíl > 0)
sample size (N, unique conids, unique dates)
coverage rate, excluded candidate-days
reason_code distribution, staleness distribution, alias distribution
field_null_excluded per varianta
```

Zakázané v první fázi: Sharpe jako hlavní metrika, CAGR, portfolio CAGR,
max drawdown jako hlavní závěr, optimized sizing, Kelly, portfolio
construction, execution model, Decision Resolver scoring.

Gross returns only = přípustné pouze jako signal-level research; přechod
do strategy layer vyžaduje náklady/slippage (mimo scope FUND-05).

Otevřená otázka pro architekta: benchmark adjustace (alpha vs SPY) není
v povoleném seznamu — raw forward returns nesou market-regime bias
(245 dní jednoho režimového mixu). Doporučuji povolit `alpha vs SPY`
jako SEKUNDÁRNÍ metriku; bez ní je interpretace mezi-variantních rozdílů
validní (společný benchmark bias se odečítá), ale absolutní úrovně ne.

## 4. Dependence and Effective Sample Size

Fakta z FUND-03: 1 144 candidate-days = 151 conidů × 245 dní; průměr
~7,6 candidate-days/conid; ~4,7/den. **1 144 NENÍ 1 144 nezávislých
pozorování**: (a) opakované conidy napříč po sobě jdoucími dny sdílejí
tutéž fundamentální i cenovou trajektorii; (b) 5/10/20D forward okna
se překrývají; (c) candidate-days clusterují podle market regime
(MLE×IRC výběr je režimově korelovaný).

Povinný reporting (per varianta):

```text
nominální N | unique conids | unique dates
average candidate-days per conid
top 10 nejopakovanějších conidů (conid, ticker, count, podíl na N)
non-overlap sensitivity: subsample max 1 candidate-day per conid
    na 20 obchodních dní (deterministický výběr: první výskyt);
    reportovat metriky nad subsample vedle plného vzorku
```

Interpretační slovník závěrů (povinný):

```text
statistically suggestive — směr konzistentní napříč okny i non-overlap
                           subsample, N nad minimem
not conclusive           — směr pozitivní, ale selhává konzistence
                           nebo efektivní N
inconclusive             — sample/coverage/dependence problém
```

Tvrzení „edge potvrzen" z jednoho in-sample testu je ZAKÁZÁNO —
maximum je „candidate for out-of-sample / robustness validation".

## 5. PASS / FAIL / INCONCLUSIVE / STOP (acceptance criteria pro FUND-05)

Per varianta B–F vs. A, primární: median 20D forward return.

```text
PASS  (candidate for further validation):
    median_20d(V) > median_20d(A)
    AND hit_rate_20d(V) >= hit_rate_20d(A)
    AND směr zlepšení drží na 5D i 10D (znaménko rozdílu mediánů)
    AND směr drží v non-overlap subsample
    AND N(V) >= 30 (preferováno >= 100)

FAIL  (no evidence of improvement):
    N(V) >= 30 a podmínky PASS nesplněny

INCONCLUSIVE:
    N(V) < 30, nebo coverage/dependence problém znemožňující čtení
    (např. varianta koncentrovaná do <20 unique conidů)

STOP  (leakage / data integrity — celý run nevalidní):
    lookahead leakage detekován
    forward-return sloupce použité ve feature konstrukci
    coverage < 95 %
    UNKNOWN_ERROR > 0
    CACHE_MISSING / SCHEMA_MISMATCH > 0
    nevysvětlené tiché dropy (porušení 1:1 / field_null accountingu)
    nereprodukovatelné source files (hash mismatch vůči manifestům)
```

PASS ≠ produkční strategie. PASS = varianta stojí za out-of-sample /
robustness validaci (samostatná budoucí fáze, samostatné schválení).
