# KR-CAP-02 — Market-Cap Differentiation of MLE × IRC Candidates

**Status:** ACCEPTED AS EVIDENCE. Evidence level: B (in-sample,
non-overlap-adjusted, single regime, not OOS-confirmed).

## Otázka

Diferencuje market-cap bucket forward returns MLE TOP10 × IRC TOP10
candidate-days oproti celkovému vzorku (signal-level, bez strategie)?

## Vstup

```text
candidate-days: MLE TOP10 × IRC TOP10 (20d), FUND-03 extraction
    1 144 candidate-days | 151 conidů | 2025-07-09 → 2026-06-27
snapshot: sf1art_20260704_005521 (pinned)
market cap: close(candidate_date) × sharesbas(PIT) — CAP-01B
```

## CAP-01B coverage

```text
coverage_pct: 98.16 | MARKET_CAP_OK: 1123 | SUSPECT: 18 | PRICE_MISSING: 3
known issue: 18 UNBUCKETED (CRWD/KLAC vendor-anchor anomálie, 1.57 %)
```

## Bucket distribuce

```text
Mega 263 (32 conidů) | Large-high 355 (64) | Large-low 487 (77)
Mid 18 (7) | Small 0 | UNBUCKETED 21 (5)
```

## CAP-02 výsledky (baseline median20 = 2.4037, hit20 = 0.5995)

| bucket | status | median20 | non-overlap median20 | hit20 |
|---|---|---|---|---|
| Mega | PASS | 6.8871 | 3.3086 | 0.7166 |
| Large-high | FAIL | 3.6541 | 1.9447 | 0.6459 |
| Large-low | PASS | 0.0652 | 1.0791 | 0.5032 |
| Mid | INCONCLUSIVE | 4.8227 | — | 0.7778 |
| Small | NO DATA | — | — | — |

## Mega PASS

median20 6.89 vs baseline 2.40 (diff +4.48), robustně **nad** baseline.
5/10D konzistentní, non-overlap 3.31 > baseline 1.97 → diferenciace drží
po odstranění dependence. Statisticky suggestivní směrem nahoru.

## Large-low slabost

median20 0.065 ≈ 0, robustně **pod** baseline (diff −2.34), 5/10D
konzistentní, non-overlap 1.08 < baseline 1.97. Diferenciace směrem dolů
— možný caution bucket. Stejně platný poznatek jako Mega, opačný směr.

## Large-high FAIL

median20 3.65 nad baseline, ale 5/10D nekonzistentní (median5 0.51 <
baseline 0.66) a non-overlap 1.9447 ≈ baseline 1.9699 → po odstranění
dependence žádná diferenciace. FAIL korektní.

## Mid / Small

Mid INCONCLUSIVE (N=18 < 30). Small NO DATA (N=0). Segment firem pod
~10B v S&P leaders vzorku prakticky chybí — o cap-return vztahu pod
touto hranicí nelze říct nic.

## Dependence caveat

Mega 247 řádků = 32 conidů (AMD 44×, MU 43×, INTC 38×); non-overlap N
klesá na 43. Vztah drží, ale efektivní N nízké. Full-sample monotónní
klesající vztah (Mega 6.89 > Large-high 3.65 > Large-low 0.07) přežívá
non-overlap (Mega 3.31 > baseline 1.97 > Large-low 1.08) — to je
nejsilnější část výsledku.

## Proč to není potvrzený edge

```text
- jeden in-sample run, jeden režim (2025-07→2026-06, převážně rostoucí)
  → cap efekt může být režimově podmíněný (mega-caps vedly tento trh)
- nízké efektivní N u Mega (non-overlap 43)
- žádná OOS ani portfolio-level validace
- SPY-relative kopíruje směr (Mega +5.56, Large-low −0.22), ale je
  sekundární diagnostika, nerozhoduje
```

## Závěr

```text
Market-cap bucket differentiates forward returns of MLE TOP10 × IRC TOP10
candidate-days in this in-sample run: Mega robustly above baseline,
Large-low robustly below, Large-high not differentiated after dependence
control. Statistically suggestive, not conclusive, not OOS-confirmed.
Evidence level: B.
```

Srovnání s KR-FUND-05: fundamentální filtry nedržely non-overlap (všechny
FAIL); market-cap Mega/Large-low směr non-overlap drží. Silnější signál,
stále ne potvrzený.
