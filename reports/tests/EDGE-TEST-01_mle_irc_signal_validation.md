# EDGE-TEST-01 — MLE x IRC Signal Validation

## Verdikt: PASS

Overlap: 2025-07-09..2026-06-27 (245 obchodnich dni)

MLE ranky fresh z DATA-06. IRC z archivu. Join pres industry.

**Vyhrada: t-stat nadhodnoceny (prekryvna okna + cross-section korelace). Orientacni, ne rigorozni.**

## EDGE uplift (close-to-close)

| horizon | edge | mle_top10 | irc_top10 | baseline | uplift_vs_mle | uplift_vs_irc |
|---|---|---|---|---|---|---|
| 1D | 0.3361 | 0.3454 | 0.0804 | 0.0652 | -0.0093 | 0.2557 |
| 5D | 1.9395 | 1.5855 | 0.4765 | 0.3337 | 0.354 | 1.463 |
| 10D | 4.0117 | 3.3135 | 1.1387 | 0.6462 | 0.6982 | 2.873 |
| 20D | 8.1684 | 6.632 | 2.7532 | 1.3012 | 1.5364 | 5.4152 |

## EDGE uplift PO vylouceni exceptions (close-to-close)

| horizon | edge_ex | mle_ex | uplift_vs_mle_ex |
|---|---|---|---|
| 1D | 0.3094 | 0.2702 | 0.0392 |
| 5D | 1.6828 | 1.1435 | 0.5393 |
| 10D | 3.2435 | 2.4329 | 0.8106 |
| 20D | 6.6753 | 4.7962 | 1.8791 |

## Detailni statistiky per skupina (close-to-close)

### universe_baseline
- avg_candidates_per_day: 502.62
- days_zero_candidates: 0
- 1D: n=122640 mean=0.0652 med=0.0468 wr=0.5115 std=2.2767 t=10.023 | uniq_tk=503 uniq_ind=59 top1_share=0.0262
- 5D: n=122137 mean=0.3337 med=0.2066 wr=0.5225 std=5.0875 t=22.922 | uniq_tk=503 uniq_ind=59 top1_share=0.0273
- 10D: n=119622 mean=0.6462 med=0.37 wr=0.5301 std=7.2706 t=30.74 | uniq_tk=503 uniq_ind=59 top1_share=0.0287
- 20D: n=114592 mean=1.3012 med=0.6359 wr=0.5341 std=10.7189 t=41.094 | uniq_tk=503 uniq_ind=59 top1_share=0.0319
- 10D top contrib tickers: [('SNDK', np.float64(4660.2)), ('MU', np.float64(2588.71)), ('WDC', np.float64(2533.14)), ('LITE', np.float64(2497.01)), ('STX', np.float64(2147.8))]
- 10D worst contrib tickers: [('TTD', np.float64(-1216.53)), ('FISV', np.float64(-998.82)), ('CSGP', np.float64(-970.52)), ('INTU', np.float64(-928.16)), ('CHTR', np.float64(-892.88))]
- 10D top contrib industries: [('Semiconductors', np.float64(16091.45)), ('Computers', np.float64(12828.96)), ('Telecommunications', np.float64(6247.38)), ('Banks', np.float64(5195.65)), ('Electric', np.float64(3807.09))]

### mle_top10
- avg_candidates_per_day: 10.0
- days_zero_candidates: 0
- 1D: n=2440 mean=0.3454 med=0.1278 wr=0.5238 std=4.0181 t=4.246 | uniq_tk=222 uniq_ind=48 top1_share=0.1472
- 5D: n=2430 mean=1.5855 med=0.8329 wr=0.5519 std=8.9899 t=8.694 | uniq_tk=222 uniq_ind=48 top1_share=0.1631
- 10D: n=2380 mean=3.3135 med=1.9299 wr=0.5798 std=12.639 t=12.79 | uniq_tk=222 uniq_ind=48 top1_share=0.1812
- 20D: n=2280 mean=6.632 med=2.6665 wr=0.5829 std=20.4389 t=15.494 | uniq_tk=216 uniq_ind=47 top1_share=0.2092
- 10D top contrib tickers: [('SNDK', np.float64(2549.57)), ('LITE', np.float64(955.35)), ('INTC', np.float64(733.84)), ('MU', np.float64(626.46)), ('AMD', np.float64(579.11))]
- 10D worst contrib tickers: [('SMCI', np.float64(-311.34)), ('COIN', np.float64(-175.06)), ('AXON', np.float64(-174.28)), ('HOOD', np.float64(-123.46)), ('FSLR', np.float64(-112.26))]
- 10D top contrib industries: [('Computers', np.float64(4172.2)), ('Semiconductors', np.float64(2767.58)), ('Telecommunications', np.float64(740.75)), ('Healthcare-Services', np.float64(374.95)), ('Chemicals', np.float64(233.49))]

### irc_top10_industry
- avg_candidates_per_day: 92.52
- days_zero_candidates: 0
- 1D: n=22575 mean=0.0804 med=0.0329 wr=0.5072 std=2.5601 t=4.719 | uniq_tk=480 uniq_ind=44 top1_share=0.0237
- 5D: n=22481 mean=0.4765 med=0.1352 wr=0.515 std=5.7689 t=12.384 | uniq_tk=480 uniq_ind=44 top1_share=0.0311
- 10D: n=22138 mean=1.1387 med=0.3197 wr=0.5247 std=8.5607 t=19.79 | uniq_tk=480 uniq_ind=44 top1_share=0.0337
- 20D: n=21150 mean=2.7532 med=0.8961 wr=0.5483 std=12.8814 t=31.083 | uniq_tk=480 uniq_ind=44 top1_share=0.0394
- 10D top contrib tickers: [('MU', np.float64(1796.48)), ('SNDK', np.float64(1782.35)), ('SATS', np.float64(1313.15)), ('AMD', np.float64(1230.7)), ('INTC', np.float64(1025.93))]
- 10D worst contrib tickers: [('ACN', np.float64(-265.45)), ('LDOS', np.float64(-227.75)), ('NOW', np.float64(-221.88)), ('IT', np.float64(-214.02)), ('INTU', np.float64(-211.3))]
- 10D top contrib industries: [('Semiconductors', np.float64(9759.16)), ('Computers', np.float64(6148.65)), ('Telecommunications', np.float64(2459.11)), ('Banks', np.float64(2438.58)), ('Machinery-Constr&Mining', np.float64(1626.19))]

### mle_top10_x_irc_top10
- avg_candidates_per_day: 4.61
- days_zero_candidates: 3
- 1D: n=1124 mean=0.3361 med=0.2046 wr=0.532 std=4.1147 t=2.738 | uniq_tk=149 uniq_ind=35 top1_share=0.0855
- 5D: n=1121 mean=1.9395 med=1.096 wr=0.5647 std=9.3038 t=6.98 | uniq_tk=148 uniq_ind=35 top1_share=0.0978
- 10D: n=1103 mean=4.0117 med=2.4084 wr=0.6038 std=12.7047 t=10.487 | uniq_tk=147 uniq_ind=35 top1_share=0.1425
- 20D: n=1057 mean=8.1684 med=4.4813 wr=0.6395 std=20.4271 t=13.001 | uniq_tk=146 uniq_ind=35 top1_share=0.1665
- 10D top contrib tickers: [('SNDK', np.float64(1003.04)), ('INTC', np.float64(734.09)), ('MU', np.float64(551.08)), ('AMD', np.float64(547.72)), ('LITE', np.float64(412.39))]
- 10D worst contrib tickers: [('SMCI', np.float64(-270.84)), ('IBM', np.float64(-72.34)), ('NOW', np.float64(-52.43)), ('XYZ', np.float64(-49.66)), ('HOOD', np.float64(-48.66))]
- 10D top contrib industries: [('Semiconductors', np.float64(2457.12)), ('Computers', np.float64(1505.73)), ('Telecommunications', np.float64(337.93)), ('Oil&Gas', np.float64(186.61)), ('Machinery-Constr&Mining', np.float64(128.78))]

### mle_top25_x_irc_top10
- avg_candidates_per_day: 11.09
- days_zero_candidates: 0
- 1D: n=2705 mean=0.2705 med=0.0882 wr=0.5146 std=3.609 t=3.897 | uniq_tk=264 uniq_ind=41 top1_share=0.0509
- 5D: n=2698 mean=1.2962 med=0.5653 wr=0.5415 std=8.2277 t=8.183 | uniq_tk=264 uniq_ind=41 top1_share=0.0762
- 10D: n=2658 mean=3.0403 med=1.3645 wr=0.576 std=11.5256 t=13.6 | uniq_tk=264 uniq_ind=41 top1_share=0.0981
- 20D: n=2558 mean=5.7361 med=2.5583 wr=0.6001 std=17.5051 t=16.573 | uniq_tk=260 uniq_ind=41 top1_share=0.1125
- 10D top contrib tickers: [('MU', np.float64(1245.95)), ('SNDK', np.float64(1178.07)), ('INTC', np.float64(734.76)), ('AMD', np.float64(726.38)), ('LITE', np.float64(457.83))]
- 10D worst contrib tickers: [('NOW', np.float64(-117.72)), ('LUV', np.float64(-92.02)), ('ORCL', np.float64(-87.84)), ('HOOD', np.float64(-75.64)), ('HPQ', np.float64(-73.46))]
- 10D top contrib industries: [('Semiconductors', np.float64(4012.38)), ('Computers', np.float64(3029.04)), ('Telecommunications', np.float64(454.96)), ('Machinery-Constr&Mining', np.float64(356.54)), ('Oil&Gas', np.float64(262.95))]

### mle_top50_x_irc_top10
- avg_candidates_per_day: 20.48
- days_zero_candidates: 0
- 1D: n=4996 mean=0.1502 med=0.0441 wr=0.5088 std=3.2168 t=3.301 | uniq_tk=376 uniq_ind=44 top1_share=0.0477
- 5D: n=4980 mean=0.9194 med=0.3647 wr=0.5317 std=7.2701 t=8.925 | uniq_tk=376 uniq_ind=44 top1_share=0.069
- 10D: n=4900 mean=2.2448 med=0.9301 wr=0.5539 std=10.5542 t=14.888 | uniq_tk=373 uniq_ind=44 top1_share=0.085
- 20D: n=4701 mean=4.2766 med=1.7846 wr=0.5722 std=15.845 t=18.506 | uniq_tk=368 uniq_ind=44 top1_share=0.0935
- 10D top contrib tickers: [('MU', np.float64(1601.98)), ('SNDK', np.float64(1248.7)), ('AMD', np.float64(767.14)), ('DELL', np.float64(723.54)), ('INTC', np.float64(688.54))]
- 10D worst contrib tickers: [('NOW', np.float64(-162.77)), ('ORCL', np.float64(-136.92)), ('TEL', np.float64(-108.32)), ('WDAY', np.float64(-97.52)), ('LUV', np.float64(-95.6))]
- 10D top contrib industries: [('Semiconductors', np.float64(5076.75)), ('Computers', np.float64(4153.99)), ('Telecommunications', np.float64(585.82)), ('Oil&Gas', np.float64(539.23)), ('Machinery-Constr&Mining', np.float64(489.51))]

## Klicove otazky

- MLE×IRC > MLE TOP10 only (5/10/20D): [True, True, True]
- prezije po vylouceni exceptions: [True, True, True]
- koncentrovany 10D (top1 ticker >50% abs): False

## PASS/WARN/FAIL

- PASS: edge > MLE TOP10 na 5/10/20D, neni koncentrovany, prezije bez exceptions.
- WARN: edge existuje ale slaby/koncentrovany/nekonzistentni.
- FAIL: edge <= MLE TOP10, IRC filtr nepridava hodnotu.

## Vyhrady (souhrn)

- t-stat nadhodnoceny (nezavislost porusena).
- signal diagnostic, NE tradable backtest (bez nakladu, slippage).
- metrika B (next-open) je aproximace, ne realny fill.
- MLE ranky fresh z DATA-06 (survivorship: 503 soucasnych).
- overlap 245 dni = kratky sample pro edge inference.
