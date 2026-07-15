# CAP-02 Performance Protocol (návrh — nespouštět)

**Signal-level performance comparison podle market-cap bucketu.
NENÍ portfolio strategie.** Předpoklad: CAP-01 PASS (příp. CONDITIONAL
s uzavřenou review).

## Design

```text
jednotka: bucket (Mega / Large-high / Large-low / Mid / Small),
    UNBUCKETED reportován, neinterpretuje se
baseline reference: celý MLE × IRC vzorek (analogie varianty A)
žádné filtry navíc — čistá dekompozice baseline podle bucketu
forward returns: close-to-close, kalendářní 5/10/20 d + nearest ≤ +5 d
    (konvence FUND-05/MLEBucketsIRCGrid); primární okno 20D, primární
    statistika median
```

## Povolené metriky

5/10/20D forward return; median, mean, hit-rate; SPY-relative jako
SEKUNDÁRNÍ diagnostika (ne acceptance); nominal N, unique conids,
unique dates, avg candidate-days/conid, top repeated conids per bucket;
non-overlap sensitivity (max 1 candidate-day/conid/20 obchodních dní,
first-occurrence, bez returns); bucket distribution; reason_code
distribution; market_cap coverage.

## Zakázané jako hlavní závěr

Sharpe, CAGR, portfolio CAGR, max drawdown, position sizing, Kelly,
execution model, Decision Resolver scoring, optimalizace thresholdů.

## Per-bucket statusy

```text
PASS:         bucket vykazuje robustní diferenciaci vs. celkový vzorek —
              median 20D nad/pod baseline SE shodným směrem na 5/10D
              A směr drží v non-overlap subsample A N >= 30 (pref. >= 100)
              → "worth later Decision Resolver research", nic víc
FAIL:         N >= 30 a žádná použitelná diferenciace
INCONCLUSIVE: N < 30 (očekávané u Small/Mid), dependence problém,
              nebo bucket koncentrovaný do < 10 unique conidů
STOP:         market-cap leakage (current cap), source failure,
              coverage failure, silent drops
```

Pozn.: „diferenciace" zahrnuje i robustně HORŠÍ bucket — negativní
poznatek (bucket se vyhnout) je stejně hodnotný.

## Dependence

Povinný reporting jako FUND-05 (nominal vs. unique, top repeated
per bucket, non-overlap). Slovník závěrů: statistically suggestive /
not conclusive / inconclusive. Zakázáno „edge confirmed" z jednoho
in-sample runu.

## Governance pojistka

Výsledek CAP-02 NESMÍ automaticky měnit Decision Resolver. Jediný
povolený výstup směrem k DR: doporučení, ZDA má smysl navrhnout
samostatný DR experiment (samostatné zadání, samostatné schválení).
