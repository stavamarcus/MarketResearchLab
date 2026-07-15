# CAP-02 Market Cap Performance Report

**Signal-level research. NENÍ obchodovatelná strategie** — žádné náklady, slippage, sizing, portfolio konstrukce.

- market_cap source: `C:\Users\stava\Projects\MarketResearchLab\results\diagnostics\cap01_market_cap_coverage_20260705_050531_sf1art_20260704_005521\market_cap_output.csv`
- candidate-days: 1144
- forward return method: close-to-close, kalendářní [5, 10, 20] d + nearest ≤ +5d (konvence FUND-05)
- SPY-relative: sekundární diagnostika, ne acceptance
- entry_price_missing: 3
- baseline median 20D: 2.4037 | hit 20D: 0.5995

## Per-bucket performance

| bucket | status | n_rows | unique_conids | unique_dates | n_ret_20d | median_20d | mean_20d | hit_20d | spyrel_median_20d | median_5d | median_10d | nonoverlap_n | nonoverlap_median_20d | detail |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL (baseline) | BASELINE | 1144 | 151 | 244 | 1111 | 2.4037 | 4.4432 | 0.5995 | 1.8638 | 0.6579 | 1.4147 | 266 | 1.9699 | referenční celý vzorek |
| Mega | PASS | 263 | 32 | 129 | 247 | 6.8871 | 10.9612 | 0.7166 | 5.5607 | 1.6191 | 3.5121 | 43 | 3.3086 | median20 6.8871 vs vzorek 2.4037 (diff +4.4834); 5/10D konzist=True; non-overlap 3.3086 vs 1.9699 |
| Large-high | FAIL | 355 | 64 | 189 | 353 | 3.6541 | 4.2887 | 0.6459 | 2.4806 | 0.5125 | 1.4939 | 82 | 1.9447 | median20 3.6541 vs vzorek 2.4037 (diff +1.2504); 5/10D konzist=False; non-overlap 1.9447 vs 1.9699 |
| Large-low | PASS | 487 | 77 | 215 | 475 | 0.0652 | 1.28 | 0.5032 | -0.2159 | 0.5159 | 0.5948 | 127 | 1.0791 | median20 0.0652 vs vzorek 2.4037 (diff -2.3385); 5/10D konzist=True; non-overlap 1.0791 vs 1.9699 |
| Mid | INCONCLUSIVE | 18 | 7 | 16 | 18 | 4.8227 | 5.4623 | 0.7778 | 2.5434 | 0.2722 | 2.5666 | 9 | 4.8172 | N_20d=18 < 30 |
| Small | NOT_INTERPRETED | 0 | 0 | 0 | 0 |  |  |  |  |  |  | 0 |  | Small se neinterpretuje |
| UNBUCKETED | NOT_INTERPRETED | 21 | 5 | 19 | 18 | -0.4362 | 0.486 | 0.4444 | -0.2061 | -0.0474 | 4.7096 | 5 | -1.7839 | UNBUCKETED se neinterpretuje |

## Dependence (valid buckets)

| bucket | nominal_N | unique_conids | avg_per_conid | top_conids |
|---|---|---|---|---|
| Mega | 263 | 32 | 8.22 | AMD(44), MU(43), INTC(38) |
| Large-high | 355 | 64 | 5.55 | STX(21), VRT(19), INTC(16) |
| Large-low | 487 | 77 | 6.32 | TER(22), GNRC(21), LITE(20) |
| Mid | 18 | 7 | 2.57 | APA(6), NCLH(4), CRL(3) |

## Statusy

- Mega: **PASS** — median20 6.8871 vs vzorek 2.4037 (diff +4.4834); 5/10D konzist=True; non-overlap 3.3086 vs 1.9699
- Large-high: **FAIL** — median20 3.6541 vs vzorek 2.4037 (diff +1.2504); 5/10D konzist=False; non-overlap 1.9447 vs 1.9699
- Large-low: **PASS** — median20 0.0652 vs vzorek 2.4037 (diff -2.3385); 5/10D konzist=True; non-overlap 1.0791 vs 1.9699
- Mid: **INCONCLUSIVE** — N_20d=18 < 30
- Small: **NOT_INTERPRETED** — Small se neinterpretuje
- UNBUCKETED: **NOT_INTERPRETED** — UNBUCKETED se neinterpretuje

## Overall RESULT: COMPLETED

PASS bucket = robustní diferenciace (nad i pod baseline) hodná samostatného DR výzkumu. NESMÍ automaticky měnit Decision Resolver. UNBUCKETED se neinterpretuje; Small = NO DATA; Mid pravděpodobně INCONCLUSIVE (N<30). Zakázáno: edge confirmed / tradable strategy.
