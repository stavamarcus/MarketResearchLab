# MLE-BT-04 — Yearly/Monthly/Regime Breakdown (DIAGNOSTIC)

## SURVIVORSHIP WARNING

current 503 universe, survivorship bias.

Sim: 2021-07-01..2026-07-02 (1256 dni), cost 15bps

## Overall (4 varianty)

| variant | return% | maxDD% | sharpe | calmar | avg_expo |
|---|---|---|---|---|---|
| baseline_hold10 | 325.796 | -36.583 | 1.034 | 8.906 | 0.999 |
| regime200_hold10 | 375.283 | -25.431 | 1.197 | 14.757 | 0.864 |
| baseline_hold20 | 431.696 | -39.037 | 1.223 | 11.059 | 0.999 |
| regime200_hold20 | 401.452 | -29.298 | 1.236 | 13.702 | 0.88 |

## baseline_hold10 — rocni rozklad

| rok | strat_ret% | bench_ret% | excess% | maxDD% | sharpe | calmar | vol% | expo | pos | trades | avg_net | med_net | win_rate | regime_on% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 5.072 | 8.911 | -3.84 | -12.178 | 0.543 | 0.416 | 22.93 | 0.992 | 9.92 | 120 | 0.474 | 0.543 | 0.558 | 1.0 |
| 2022 | -24.266 | -11.767 | -12.5 | -33.001 | -0.547 | -0.735 | 37.973 | 1.0 | 10.0 | 250 | -0.805 | -0.576 | 0.484 | 0.339 |
| 2023 | 113.217 | 20.635 | 92.58 | -18.462 | 2.69 | 6.133 | 30.202 | 1.0 | 10.0 | 250 | 3.31 | 1.475 | 0.592 | 0.86 |
| 2024 | 39.049 | 17.807 | 21.24 | -17.169 | 1.316 | 2.274 | 28.182 | 1.0 | 10.0 | 250 | 1.662 | 1.602 | 0.548 | 1.0 |
| 2025 | 17.091 | 13.732 | 3.36 | -33.654 | 0.628 | 0.508 | 35.825 | 1.0 | 10.0 | 250 | 0.725 | -0.069 | 0.496 | 0.86 |
| 2026 | 51.608 | 10.458 | 41.15 | -21.147 | 2.17 | 2.44 | 43.345 | 1.0 | 10.0 | 140 | 3.562 | 0.763 | 0.536 | 0.984 |
- **2021** best_trade: MRNA 33.1859% (pnl 3318.59) | worst_trade: FANG -25.2452% (pnl -2524.52)
  - top tickers: [('MRNA', np.float64(5115.0)), ('AMD', np.float64(1974.0)), ('APA', np.float64(1437.0)), ('MOS', np.float64(1227.0)), ('COP', np.float64(1161.0))]
  - worst tickers: [('FANG', np.float64(-2176.0)), ('FSLR', np.float64(-1779.0)), ('TTD', np.float64(-1664.0)), ('OXY', np.float64(-1639.0)), ('LVS', np.float64(-1198.0))]
  - top industries: [('Biotechnology', np.float64(5972.0)), ('Semiconductors', np.float64(2721.0)), ('Software', np.float64(2159.0)), ('REITS', np.float64(1787.0)), ('Chemicals', np.float64(1632.0))]
  - worst industries: [('Computers', np.float64(-1815.0)), ('Energy-Alternate Sources', np.float64(-1779.0)), ('Advertising', np.float64(-1664.0)), ('Lodging', np.float64(-1198.0)), ('Media', np.float64(-1143.0))]
- **2022** best_trade: CVNA 91.5387% (pnl 7721.57) | worst_trade: CVNA -30.3225% (pnl -3104.85)
  - top tickers: [('CVNA', np.float64(4152.0)), ('SMCI', np.float64(3965.0)), ('SLB', np.float64(3303.0)), ('FSLR', np.float64(3255.0)), ('HAL', np.float64(2480.0))]
  - worst tickers: [('COIN', np.float64(-7086.0)), ('DDOG', np.float64(-3457.0)), ('HOOD', np.float64(-3372.0)), ('TTD', np.float64(-3044.0)), ('UBER', np.float64(-2685.0))]
  - top industries: [('Oil&Gas Services', np.float64(7421.0)), ('Oil&Gas', np.float64(5548.0)), ('Energy-Alternate Sources', np.float64(3255.0)), ('Biotechnology', np.float64(2750.0)), ('Commercial Services', np.float64(2066.0))]
  - worst industries: [('Internet', np.float64(-13419.0)), ('Diversified Finan Serv', np.float64(-7900.0)), ('Chemicals', np.float64(-5478.0)), ('Auto Manufacturers', np.float64(-5195.0)), ('Semiconductors', np.float64(-4693.0))]
- **2023** best_trade: CVNA 122.1454% (pnl 10994.52) | worst_trade: SMCI -24.049% (pnl -3488.4)
  - top tickers: [('CVNA', np.float64(26557.0)), ('COIN', np.float64(13720.0)), ('PLTR', np.float64(7778.0)), ('APP', np.float64(5817.0)), ('HOOD', np.float64(5325.0))]
  - worst tickers: [('SATS', np.float64(-4291.0)), ('MOS', np.float64(-2484.0)), ('ABNB', np.float64(-2114.0)), ('MRNA', np.float64(-1619.0)), ('LYV', np.float64(-1400.0))]
  - top industries: [('Retail', np.float64(29486.0)), ('Internet', np.float64(15788.0)), ('Diversified Finan Serv', np.float64(13720.0)), ('Leisure Time', np.float64(8594.0)), ('Software', np.float64(7543.0))]
  - worst industries: [('Telecommunications', np.float64(-4592.0)), ('Oil&Gas', np.float64(-3422.0)), ('Chemicals', np.float64(-2864.0)), ('Banks', np.float64(-2453.0)), ('Biotechnology', np.float64(-1623.0))]
- **2024** best_trade: APP 83.9247% (pnl 16550.19) | worst_trade: SMCI -45.1551% (pnl -9456.15)
  - top tickers: [('APP', np.float64(25835.0)), ('CVNA', np.float64(14847.0)), ('HOOD', np.float64(11685.0)), ('TSLA', np.float64(11262.0)), ('UAL', np.float64(9611.0))]
  - worst tickers: [('SMCI', np.float64(-19265.0)), ('DELL', np.float64(-7753.0)), ('ALB', np.float64(-4866.0)), ('AMD', np.float64(-4233.0)), ('F', np.float64(-3744.0))]
  - top industries: [('Internet', np.float64(40404.0)), ('Retail', np.float64(16218.0)), ('Airlines', np.float64(10227.0)), ('Electric', np.float64(9563.0)), ('Software', np.float64(7958.0))]
  - worst industries: [('Computers', np.float64(-29404.0)), ('Chemicals', np.float64(-6437.0)), ('Biotechnology', np.float64(-3432.0)), ('Lodging', np.float64(-2881.0)), ('Pharmaceuticals', np.float64(-2476.0))]
- **2025** best_trade: PLTR 55.2989% (pnl 12432.96) | worst_trade: APP -36.4444% (pnl -8830.17)
  - top tickers: [('SNDK', np.float64(23711.0)), ('LITE', np.float64(16326.0)), ('CVNA', np.float64(10181.0)), ('PLTR', np.float64(9951.0)), ('STX', np.float64(7822.0))]
  - worst tickers: [('INTC', np.float64(-10634.0)), ('SMCI', np.float64(-9225.0)), ('TSLA', np.float64(-6124.0)), ('MRNA', np.float64(-5497.0)), ('GNRC', np.float64(-5363.0))]
  - top industries: [('Computers', np.float64(44753.0)), ('Retail', np.float64(12825.0)), ('Software', np.float64(6558.0)), ('Machinery-Constr&Mining', np.float64(5690.0)), ('Transportation', np.float64(3251.0))]
  - worst industries: [('Media', np.float64(-9828.0)), ('Biotechnology', np.float64(-6642.0)), ('Auto Manufacturers', np.float64(-6124.0)), ('Healthcare-Services', np.float64(-5576.0)), ('Electrical Compo&Equip', np.float64(-5363.0))]
- **2026** best_trade: SNDK 69.0199% (pnl 18849.84) | worst_trade: PSKY -28.2789% (pnl -10002.72)
  - top tickers: [('SNDK', np.float64(30880.0)), ('INTC', np.float64(25735.0)), ('DDOG', np.float64(21696.0)), ('MRNA', np.float64(19147.0)), ('LITE', np.float64(17391.0))]
  - worst tickers: [('PSKY', np.float64(-10003.0)), ('TER', np.float64(-8944.0)), ('CASY', np.float64(-6909.0)), ('COHR', np.float64(-5852.0)), ('TTD', np.float64(-5426.0))]
  - top industries: [('Computers', np.float64(90312.0)), ('Semiconductors', np.float64(54896.0)), ('Healthcare-Services', np.float64(23058.0)), ('Biotechnology', np.float64(22337.0)), ('Software', np.float64(18721.0))]
  - worst industries: [('Media', np.float64(-10083.0)), ('Advertising', np.float64(-7800.0)), ('Oil&Gas', np.float64(-7471.0)), ('Auto Manufacturers', np.float64(-6066.0)), ('Internet', np.float64(-5588.0))]

## regime200_hold10 — rocni rozklad

| rok | strat_ret% | bench_ret% | excess% | maxDD% | sharpe | calmar | vol% | expo | pos | trades | avg_net | med_net | win_rate | regime_on% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 5.072 | 8.911 | -3.84 | -12.178 | 0.543 | 0.416 | 22.93 | 0.992 | 9.92 | 120 | 0.474 | 0.543 | 0.558 | 1.0 |
| 2022 | -18.006 | -11.767 | -6.24 | -24.79 | -0.858 | -0.726 | 20.794 | 0.458 | 4.58 | 120 | -1.427 | -1.559 | 0.417 | 0.339 |
| 2023 | 82.791 | 20.635 | 62.16 | -20.795 | 2.199 | 3.981 | 29.804 | 0.948 | 9.48 | 230 | 2.619 | 0.914 | 0.574 | 0.86 |
| 2024 | 29.086 | 17.807 | 11.28 | -23.973 | 1.025 | 1.213 | 29.186 | 1.0 | 10.0 | 260 | 1.219 | 0.172 | 0.519 | 1.0 |
| 2025 | 37.295 | 13.732 | 23.56 | -24.919 | 1.173 | 1.497 | 31.665 | 0.924 | 9.24 | 230 | 1.619 | 0.541 | 0.526 | 0.86 |
| 2026 | 69.464 | 10.458 | 59.01 | -13.855 | 2.632 | 5.014 | 44.562 | 0.984 | 9.84 | 130 | 4.727 | 2.517 | 0.546 | 0.984 |
- **2021** best_trade: MRNA 33.1859% (pnl 3318.59) | worst_trade: FANG -25.2452% (pnl -2524.52)
  - top tickers: [('MRNA', np.float64(5115.0)), ('AMD', np.float64(1974.0)), ('APA', np.float64(1437.0)), ('MOS', np.float64(1227.0)), ('COP', np.float64(1161.0))]
  - worst tickers: [('FANG', np.float64(-2176.0)), ('FSLR', np.float64(-1779.0)), ('TTD', np.float64(-1664.0)), ('OXY', np.float64(-1639.0)), ('LVS', np.float64(-1198.0))]
  - top industries: [('Biotechnology', np.float64(5972.0)), ('Semiconductors', np.float64(2721.0)), ('Software', np.float64(2159.0)), ('REITS', np.float64(1787.0)), ('Chemicals', np.float64(1632.0))]
  - worst industries: [('Computers', np.float64(-1815.0)), ('Energy-Alternate Sources', np.float64(-1779.0)), ('Advertising', np.float64(-1664.0)), ('Lodging', np.float64(-1198.0)), ('Media', np.float64(-1143.0))]
- **2022** best_trade: EQT 23.8551% (pnl 2590.71) | worst_trade: HOOD -25.013% (pnl -2659.22)
  - top tickers: [('SMCI', np.float64(2893.0)), ('FSLR', np.float64(2205.0)), ('SLB', np.float64(1815.0)), ('EQT', np.float64(1761.0)), ('XOM', np.float64(1561.0))]
  - worst tickers: [('COIN', np.float64(-2632.0)), ('MOS', np.float64(-2606.0)), ('TSLA', np.float64(-2395.0)), ('TTD', np.float64(-2386.0)), ('CVNA', np.float64(-2318.0))]
  - top industries: [('Oil&Gas Services', np.float64(3902.0)), ('Oil&Gas', np.float64(3006.0)), ('Computers', np.float64(2973.0)), ('Energy-Alternate Sources', np.float64(2205.0)), ('Food', np.float64(762.0))]
  - worst industries: [('Auto Manufacturers', np.float64(-5760.0)), ('Internet', np.float64(-3807.0)), ('Pharmaceuticals', np.float64(-3088.0)), ('Chemicals', np.float64(-2990.0)), ('Retail', np.float64(-2835.0))]
- **2023** best_trade: CVNA 57.2571% (pnl 7505.2) | worst_trade: CVNA -25.8763% (pnl -2600.76)
  - top tickers: [('CVNA', np.float64(11104.0)), ('SMCI', np.float64(8731.0)), ('COIN', np.float64(6251.0)), ('CCL', np.float64(4652.0)), ('COHR', np.float64(3948.0))]
  - worst tickers: [('ABNB', np.float64(-2356.0)), ('EPAM', np.float64(-1901.0)), ('STX', np.float64(-1691.0)), ('DUK', np.float64(-1375.0)), ('BX', np.float64(-1356.0))]
  - top industries: [('Retail', np.float64(10551.0)), ('Internet', np.float64(10117.0)), ('Software', np.float64(9089.0)), ('Diversified Finan Serv', np.float64(8793.0)), ('Computers', np.float64(6197.0))]
  - worst industries: [('Oil&Gas', np.float64(-2963.0)), ('Electric', np.float64(-2723.0)), ('Private Equity', np.float64(-1356.0)), ('Toys/Games/Hobbies', np.float64(-1311.0)), ('Lodging', np.float64(-1253.0))]
- **2024** best_trade: SMCI 85.6472% (pnl 12932.99) | worst_trade: SMCI -38.6878% (pnl -7039.07)
  - top tickers: [('APP', np.float64(16588.0)), ('VST', np.float64(12906.0)), ('HOOD', np.float64(12551.0)), ('SMCI', np.float64(11986.0)), ('CVNA', np.float64(8962.0))]
  - worst tickers: [('DELL', np.float64(-5929.0)), ('WBD', np.float64(-4712.0)), ('AMD', np.float64(-4654.0)), ('TPL', np.float64(-4339.0)), ('MRNA', np.float64(-3344.0))]
  - top industries: [('Internet', np.float64(28971.0)), ('Electric', np.float64(12723.0)), ('Retail', np.float64(9418.0)), ('Machinery-Constr&Mining', np.float64(8506.0)), ('Diversified Finan Serv', np.float64(6781.0))]
  - worst industries: [('Semiconductors', np.float64(-13538.0)), ('Media', np.float64(-8357.0)), ('Banks', np.float64(-5413.0)), ('Electronics', np.float64(-3419.0)), ('Chemicals', np.float64(-3271.0))]
- **2025** best_trade: SNDK 55.5981% (pnl 11429.24) | worst_trade: PLTR -29.3512% (pnl -6078.68)
  - top tickers: [('SNDK', np.float64(32925.0)), ('ALB', np.float64(10172.0)), ('LITE', np.float64(9303.0)), ('CIEN', np.float64(6961.0)), ('SATS', np.float64(5337.0))]
  - worst tickers: [('MRNA', np.float64(-6962.0)), ('AVGO', np.float64(-4475.0)), ('MGM', np.float64(-4055.0)), ('GNRC', np.float64(-3670.0)), ('DDOG', np.float64(-3577.0))]
  - top industries: [('Computers', np.float64(45771.0)), ('Chemicals', np.float64(10906.0)), ('Telecommunications', np.float64(10702.0)), ('Internet', np.float64(8452.0)), ('Electronics', np.float64(6069.0))]
  - worst industries: [('Biotechnology', np.float64(-6962.0)), ('Electrical Compo&Equip', np.float64(-3670.0)), ('Mining', np.float64(-3480.0)), ('Oil&Gas', np.float64(-2658.0)), ('Miscellaneous Manufactur', np.float64(-2484.0))]
- **2026** best_trade: DDOG 57.2706% (pnl 20970.21) | worst_trade: SNDK -19.7056% (pnl -10137.38)
  - top tickers: [('SNDK', np.float64(31537.0)), ('INTC', np.float64(28869.0)), ('DDOG', np.float64(26692.0)), ('MRNA', np.float64(23239.0)), ('DELL', np.float64(19882.0))]
  - worst tickers: [('TER', np.float64(-10207.0)), ('CASY', np.float64(-7712.0)), ('MOS', np.float64(-6777.0)), ('CRWD', np.float64(-5687.0)), ('OXY', np.float64(-5530.0))]
  - top industries: [('Computers', np.float64(78104.0)), ('Semiconductors', np.float64(66829.0)), ('Healthcare-Services', np.float64(27783.0)), ('Software', np.float64(23371.0)), ('Biotechnology', np.float64(23239.0))]
  - worst industries: [('Electronics', np.float64(-7058.0)), ('Airlines', np.float64(-4331.0)), ('Auto Manufacturers', np.float64(-3559.0)), ('Chemicals', np.float64(-3023.0)), ('Media', np.float64(-2493.0))]

## baseline_hold20 — rocni rozklad

| rok | strat_ret% | bench_ret% | excess% | maxDD% | sharpe | calmar | vol% | expo | pos | trades | avg_net | med_net | win_rate | regime_on% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 8.361 | 8.911 | -0.55 | -10.484 | 0.832 | 0.797 | 22.087 | 0.992 | 9.92 | 60 | 1.492 | 0.821 | 0.55 | 1.0 |
| 2022 | -22.291 | -11.767 | -10.52 | -37.474 | -0.459 | -0.595 | 38.894 | 1.0 | 10.0 | 120 | -1.371 | -0.302 | 0.492 | 0.339 |
| 2023 | 66.565 | 20.635 | 45.93 | -19.212 | 1.957 | 3.465 | 28.479 | 1.0 | 10.0 | 130 | 4.379 | 0.416 | 0.523 | 0.86 |
| 2024 | 35.326 | 17.807 | 17.52 | -17.621 | 1.283 | 2.005 | 26.386 | 1.0 | 10.0 | 120 | 3.43 | 1.127 | 0.55 | 1.0 |
| 2025 | 56.387 | 13.732 | 42.66 | -22.033 | 1.722 | 2.559 | 28.677 | 1.0 | 10.0 | 130 | 3.359 | 2.015 | 0.577 | 0.86 |
| 2026 | 75.279 | 10.458 | 64.82 | -13.879 | 2.971 | 5.424 | 41.341 | 1.0 | 10.0 | 70 | 9.053 | 2.748 | 0.6 | 0.984 |
- **2021** best_trade: MRNA 47.2099% (pnl 4720.99) | worst_trade: FANG -21.6091% (pnl -2160.91)
  - top tickers: [('MRNA', np.float64(3934.0)), ('AMD', np.float64(2866.0)), ('DECK', np.float64(1936.0)), ('APA', np.float64(1790.0)), ('DVN', np.float64(1635.0))]
  - worst tickers: [('LVS', np.float64(-1625.0)), ('CRWD', np.float64(-1611.0)), ('TPR', np.float64(-1200.0)), ('SATS', np.float64(-1032.0)), ('NVDA', np.float64(-993.0))]
  - top industries: [('Oil&Gas', np.float64(4958.0)), ('Biotechnology', np.float64(3934.0)), ('Semiconductors', np.float64(3546.0)), ('Chemicals', np.float64(1781.0)), ('Apparel', np.float64(1387.0))]
  - worst industries: [('Software', np.float64(-2071.0)), ('Computers', np.float64(-1918.0)), ('Lodging', np.float64(-1625.0)), ('Telecommunications', np.float64(-1032.0)), ('Electrical Compo&Equip', np.float64(-988.0))]
- **2022** best_trade: TPL 35.5635% (pnl 2652.96) | worst_trade: CVNA -27.4317% (pnl -2797.28)
  - top tickers: [('HAL', np.float64(3863.0)), ('SLB', np.float64(2889.0)), ('TPL', np.float64(2527.0)), ('WYNN', np.float64(1860.0)), ('WSM', np.float64(1813.0))]
  - worst tickers: [('CVNA', np.float64(-4208.0)), ('HOOD', np.float64(-3656.0)), ('UBER', np.float64(-2748.0)), ('DDOG', np.float64(-2623.0)), ('NUE', np.float64(-2451.0))]
  - top industries: [('Oil&Gas Services', np.float64(5828.0)), ('Oil&Gas', np.float64(4636.0)), ('Lodging', np.float64(2647.0)), ('Home Builders', np.float64(1586.0)), ('Mining', np.float64(1518.0))]
  - worst industries: [('Internet', np.float64(-7251.0)), ('Retail', np.float64(-5656.0)), ('Chemicals', np.float64(-3981.0)), ('Diversified Finan Serv', np.float64(-2955.0)), ('Leisure Time', np.float64(-2599.0))]
- **2023** best_trade: CVNA 196.2698% (pnl 17254.46) | worst_trade: CVNA -29.758% (pnl -3634.49)
  - top tickers: [('CVNA', np.float64(16827.0)), ('COIN', np.float64(8918.0)), ('APP', np.float64(5888.0)), ('VRT', np.float64(5637.0)), ('ALGN', np.float64(4255.0))]
  - worst tickers: [('SMCI', np.float64(-2756.0)), ('APA', np.float64(-2494.0)), ('CFG', np.float64(-2304.0)), ('MOS', np.float64(-2103.0)), ('AMD', np.float64(-1833.0))]
  - top industries: [('Retail', np.float64(18553.0)), ('Internet', np.float64(9777.0)), ('Diversified Finan Serv', np.float64(8918.0)), ('Machinery-Constr&Mining', np.float64(5637.0)), ('Media', np.float64(4977.0))]
  - worst industries: [('Oil&Gas', np.float64(-4242.0)), ('Banks', np.float64(-4006.0)), ('Computers', np.float64(-2473.0)), ('Chemicals', np.float64(-2183.0)), ('Telecommunications', np.float64(-1749.0))]
- **2024** best_trade: APP 126.2335% (pnl 20954.54) | worst_trade: EL -31.3569% (pnl -5423.39)
  - top tickers: [('APP', np.float64(31020.0)), ('UAL', np.float64(9821.0)), ('TPL', np.float64(6135.0)), ('NRG', np.float64(4806.0)), ('CVNA', np.float64(4501.0))]
  - worst tickers: [('EL', np.float64(-5423.0)), ('F', np.float64(-4736.0)), ('LITE', np.float64(-4713.0)), ('ALB', np.float64(-3108.0)), ('GLW', np.float64(-2902.0))]
  - top industries: [('Internet', np.float64(35273.0)), ('Airlines', np.float64(10440.0)), ('Oil&Gas', np.float64(4603.0)), ('Mining', np.float64(4464.0)), ('Retail', np.float64(3864.0))]
  - worst industries: [('Cosmetics/Personal Care', np.float64(-3891.0)), ('Chemicals', np.float64(-3108.0)), ('Media', np.float64(-3106.0)), ('Lodging', np.float64(-2745.0)), ('Healthcare-Products', np.float64(-2551.0))]
- **2025** best_trade: SNDK 67.6926% (pnl 19214.1) | worst_trade: GNRC -26.5787% (pnl -7544.18)
  - top tickers: [('SNDK', np.float64(21848.0)), ('LITE', np.float64(11947.0)), ('APP', np.float64(10474.0)), ('VRT', np.float64(10146.0)), ('CVNA', np.float64(9623.0))]
  - worst tickers: [('GNRC', np.float64(-7544.0)), ('MRNA', np.float64(-4982.0)), ('EL', np.float64(-4453.0)), ('RCL', np.float64(-3416.0)), ('IVZ', np.float64(-3087.0))]
  - top industries: [('Computers', np.float64(33918.0)), ('Semiconductors', np.float64(25286.0)), ('Retail', np.float64(19550.0)), ('Internet', np.float64(18843.0)), ('Machinery-Constr&Mining', np.float64(10097.0))]
  - worst industries: [('Electrical Compo&Equip', np.float64(-7544.0)), ('Biotechnology', np.float64(-7487.0)), ('Cosmetics/Personal Care', np.float64(-4453.0)), ('Leisure Time', np.float64(-3416.0)), ('Pharmaceuticals', np.float64(-3222.0))]
- **2026** best_trade: INTC 88.2597% (pnl 30647.7) | worst_trade: IP -23.6524% (pnl -8295.26)
  - top tickers: [('SNDK', np.float64(52236.0)), ('MU', np.float64(36935.0)), ('INTC', np.float64(25698.0)), ('STX', np.float64(21986.0)), ('WDC', np.float64(20555.0))]
  - worst tickers: [('IP', np.float64(-8295.0)), ('SW', np.float64(-7151.0)), ('CASY', np.float64(-6900.0)), ('AKAM', np.float64(-6873.0)), ('TTD', np.float64(-6172.0))]
  - top industries: [('Computers', np.float64(113505.0)), ('Semiconductors', np.float64(80299.0)), ('Miscellaneous Manufactur', np.float64(17641.0)), ('Biotechnology', np.float64(13830.0)), ('Electronics', np.float64(9925.0))]
  - worst industries: [('Forest Products&Paper', np.float64(-8295.0)), ('Packaging&Containers', np.float64(-7151.0)), ('Advertising', np.float64(-6172.0)), ('Building Materials', np.float64(-3615.0)), ('Auto Manufacturers', np.float64(-3229.0))]

## regime200_hold20 — rocni rozklad

| rok | strat_ret% | bench_ret% | excess% | maxDD% | sharpe | calmar | vol% | expo | pos | trades | avg_net | med_net | win_rate | regime_on% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 8.361 | 8.911 | -0.55 | -10.484 | 0.832 | 0.797 | 22.087 | 0.992 | 9.92 | 60 | 1.492 | 0.821 | 0.55 | 1.0 |
| 2022 | -15.206 | -11.767 | -3.44 | -27.731 | -0.719 | -0.548 | 20.251 | 0.51 | 5.1 | 60 | -1.851 | -1.85 | 0.467 | 0.339 |
| 2023 | 62.122 | 20.635 | 41.49 | -19.633 | 1.918 | 3.164 | 27.475 | 0.976 | 9.76 | 120 | 3.738 | 1.465 | 0.533 | 0.86 |
| 2024 | 64.999 | 17.807 | 47.19 | -20.835 | 1.784 | 3.12 | 30.85 | 1.0 | 10.0 | 130 | 4.89 | 2.983 | 0.585 | 1.0 |
| 2025 | 46.134 | 13.732 | 32.4 | -29.298 | 1.318 | 1.575 | 33.425 | 0.924 | 9.24 | 120 | 3.494 | 1.502 | 0.533 | 0.86 |
| 2026 | 35.386 | 10.458 | 24.93 | -21.684 | 1.634 | 1.632 | 43.537 | 0.984 | 9.84 | 70 | 5.84 | -2.016 | 0.429 | 0.984 |
- **2021** best_trade: MRNA 47.2099% (pnl 4720.99) | worst_trade: FANG -21.6091% (pnl -2160.91)
  - top tickers: [('MRNA', np.float64(3934.0)), ('AMD', np.float64(2866.0)), ('DECK', np.float64(1936.0)), ('APA', np.float64(1790.0)), ('DVN', np.float64(1635.0))]
  - worst tickers: [('LVS', np.float64(-1625.0)), ('CRWD', np.float64(-1611.0)), ('TPR', np.float64(-1200.0)), ('SATS', np.float64(-1032.0)), ('NVDA', np.float64(-993.0))]
  - top industries: [('Oil&Gas', np.float64(4958.0)), ('Biotechnology', np.float64(3934.0)), ('Semiconductors', np.float64(3546.0)), ('Chemicals', np.float64(1781.0)), ('Apparel', np.float64(1387.0))]
  - worst industries: [('Software', np.float64(-2071.0)), ('Computers', np.float64(-1918.0)), ('Lodging', np.float64(-1625.0)), ('Telecommunications', np.float64(-1032.0)), ('Electrical Compo&Equip', np.float64(-988.0))]
- **2022** best_trade: HAL 17.9604% (pnl 1821.56) | worst_trade: NUE -24.6268% (pnl -2772.59)
  - top tickers: [('HAL', np.float64(1822.0)), ('WYNN', np.float64(1694.0)), ('FSLR', np.float64(1463.0)), ('EOG', np.float64(1231.0)), ('SLB', np.float64(1207.0))]
  - worst tickers: [('NUE', np.float64(-2773.0)), ('CVNA', np.float64(-2692.0)), ('UBER', np.float64(-1991.0)), ('MOS', np.float64(-1875.0)), ('COIN', np.float64(-1676.0))]
  - top industries: [('Oil&Gas Services', np.float64(3975.0)), ('Lodging', np.float64(2298.0)), ('Energy-Alternate Sources', np.float64(1463.0)), ('Commercial Services', np.float64(1175.0)), ('Food', np.float64(902.0))]
  - worst industries: [('Retail', np.float64(-4568.0)), ('Internet', np.float64(-3081.0)), ('Iron/Steel', np.float64(-2773.0)), ('Chemicals', np.float64(-2696.0)), ('Pharmaceuticals', np.float64(-2529.0))]
- **2023** best_trade: COIN 68.1329% (pnl 8476.16) | worst_trade: CVNA -35.1742% (pnl -3917.88)
  - top tickers: [('VRT', np.float64(11532.0)), ('COIN', np.float64(8741.0)), ('SMCI', np.float64(7442.0)), ('RCL', np.float64(4632.0)), ('COHR', np.float64(4414.0))]
  - worst tickers: [('GNRC', np.float64(-2927.0)), ('NCLH', np.float64(-1885.0)), ('MRNA', np.float64(-1869.0)), ('CRH', np.float64(-1568.0)), ('FIX', np.float64(-1409.0))]
  - top industries: [('Machinery-Constr&Mining', np.float64(11532.0)), ('Computers', np.float64(8788.0)), ('Diversified Finan Serv', np.float64(8741.0)), ('Electronics', np.float64(6289.0)), ('Leisure Time', np.float64(4376.0))]
  - worst industries: [('Electrical Compo&Equip', np.float64(-2927.0)), ('Biotechnology', np.float64(-2333.0)), ('Engineering&Construction', np.float64(-1695.0)), ('Healthcare-Products', np.float64(-1575.0)), ('Banks', np.float64(-1415.0))]
- **2024** best_trade: TSLA 48.8637% (pnl 10679.41) | worst_trade: SMCI -27.4537% (pnl -4499.53)
  - top tickers: [('HOOD', np.float64(19318.0)), ('APP', np.float64(15940.0)), ('COIN', np.float64(11391.0)), ('PLTR', np.float64(10712.0)), ('TSLA', np.float64(10679.0))]
  - worst tickers: [('MRNA', np.float64(-5939.0)), ('PSKY', np.float64(-5117.0)), ('MU', np.float64(-3443.0)), ('DELL', np.float64(-2396.0)), ('RMD', np.float64(-1724.0))]
  - top industries: [('Internet', np.float64(36126.0)), ('Diversified Finan Serv', np.float64(14305.0)), ('Electric', np.float64(13750.0)), ('Auto Manufacturers', np.float64(12096.0)), ('Machinery-Constr&Mining', np.float64(11107.0))]
  - worst industries: [('Media', np.float64(-6138.0)), ('Biotechnology', np.float64(-4773.0)), ('Semiconductors', np.float64(-3645.0)), ('Pharmaceuticals', np.float64(-3605.0)), ('Chemicals', np.float64(-1777.0))]
- **2025** best_trade: SNDK 95.4834% (pnl 21892.32) | worst_trade: APP -35.3007% (pnl -9091.42)
  - top tickers: [('SNDK', np.float64(30152.0)), ('LITE', np.float64(26728.0)), ('WDC', np.float64(16472.0)), ('STX', np.float64(9778.0)), ('HOOD', np.float64(9179.0))]
  - worst tickers: [('PLTR', np.float64(-12355.0)), ('MRNA', np.float64(-10198.0)), ('MU', np.float64(-5595.0)), ('MGM', np.float64(-5524.0)), ('WBD', np.float64(-5431.0))]
  - top industries: [('Computers', np.float64(80457.0)), ('Semiconductors', np.float64(12719.0)), ('Pharmaceuticals', np.float64(8715.0)), ('Retail', np.float64(7942.0)), ('Telecommunications', np.float64(7484.0))]
  - worst industries: [('Biotechnology', np.float64(-10198.0)), ('Software', np.float64(-5884.0)), ('Media', np.float64(-5431.0)), ('Miscellaneous Manufactur', np.float64(-3782.0)), ('Apparel', np.float64(-3360.0))]
- **2026** best_trade: SNDK 119.0148% (pnl 43167.9) | worst_trade: ON -27.9403% (pnl -15277.73)
  - top tickers: [('SNDK', np.float64(40789.0)), ('DDOG', np.float64(30845.0)), ('AMD', np.float64(24835.0)), ('MU', np.float64(18371.0)), ('HUM', np.float64(17826.0))]
  - worst tickers: [('TER', np.float64(-10208.0)), ('WDC', np.float64(-10018.0)), ('AXON', np.float64(-9831.0)), ('FSLR', np.float64(-7324.0)), ('HPQ', np.float64(-7151.0))]
  - top industries: [('Semiconductors', np.float64(62524.0)), ('Computers', np.float64(42833.0)), ('Software', np.float64(30845.0)), ('Healthcare-Services', np.float64(26608.0)), ('Biotechnology', np.float64(16321.0))]
  - worst industries: [('Oil&Gas', np.float64(-10964.0)), ('Miscellaneous Manufactur', np.float64(-9831.0)), ('Energy-Alternate Sources', np.float64(-7324.0)), ('Auto Manufacturers', np.float64(-6054.0)), ('Advertising', np.float64(-4631.0))]

## baseline_hold10 — TOP 5 drawdown epizod

1. depth -36.583% | 2024-12-06 -> trough 2025-04-21 -> recovery 2025-11-07 | dur 230d | recovered True | regime_on 0.769
   loss_tickers: [('APP', np.float64(-8830.0)), ('SMCI', np.float64(-8650.0)), ('HOOD', np.float64(-6756.0)), ('INTC', np.float64(-6046.0)), ('MU', np.float64(-6007.0))]
   loss_industries: [('Internet', np.float64(-22135.0)), ('Semiconductors', np.float64(-14219.0)), ('Computers', np.float64(-7735.0)), ('Biotechnology', np.float64(-7059.0)), ('Healthcare-Services', np.float64(-7006.0))]
2. depth -33.384% | 2021-11-29 -> trough 2022-10-14 -> recovery 2023-02-02 | dur 296d | recovered True | regime_on 0.369
   loss_tickers: [('COIN', np.float64(-7086.0)), ('DDOG', np.float64(-3457.0)), ('TTD', np.float64(-3044.0)), ('UBER', np.float64(-2685.0)), ('EXPE', np.float64(-2599.0))]
   loss_industries: [('Internet', np.float64(-9754.0)), ('Diversified Finan Serv', np.float64(-7718.0)), ('Chemicals', np.float64(-5478.0)), ('Auto Manufacturers', np.float64(-5195.0)), ('Semiconductors', np.float64(-4675.0))]
3. depth -21.147% | 2026-03-02 -> trough 2026-04-15 -> recovery 2026-05-08 | dur 48d | recovered True | regime_on 0.938
   loss_tickers: [('PSKY', np.float64(-10003.0)), ('COHR', np.float64(-5852.0)), ('TTD', np.float64(-5426.0)), ('APA', np.float64(-5142.0)), ('OXY', np.float64(-4954.0))]
   loss_industries: [('Oil&Gas', np.float64(-15772.0)), ('Media', np.float64(-10003.0)), ('Electronics', np.float64(-7869.0)), ('Advertising', np.float64(-7800.0)), ('Diversified Finan Serv', np.float64(-4516.0))]
4. depth -18.462% | 2023-07-19 -> trough 2023-11-09 -> recovery 2023-12-06 | dur 98d | recovered True | regime_on 0.679
   loss_tickers: [('SMCI', np.float64(-4841.0)), ('SATS', np.float64(-3460.0)), ('CVNA', np.float64(-2090.0)), ('WBD', np.float64(-1739.0)), ('INTC', np.float64(-1450.0))]
   loss_industries: [('Computers', np.float64(-5877.0)), ('Telecommunications', np.float64(-4103.0)), ('Semiconductors', np.float64(-3314.0)), ('Banks', np.float64(-1854.0)), ('Oil&Gas', np.float64(-1813.0))]
5. depth -17.169% | 2024-07-16 -> trough 2024-09-06 -> recovery 2024-11-08 | dur 82d | recovered True | regime_on 1.0
   loss_tickers: [('SMCI', np.float64(-6838.0)), ('NVDA', np.float64(-3215.0)), ('COHR', np.float64(-2232.0)), ('HBAN', np.float64(-1864.0)), ('CFG', np.float64(-1852.0))]
   loss_industries: [('Computers', np.float64(-7894.0)), ('Banks', np.float64(-5097.0)), ('Electronics', np.float64(-3607.0)), ('Semiconductors', np.float64(-3215.0)), ('Retail', np.float64(-1121.0))]

## regime200_hold10 — TOP 5 drawdown epizod

1. depth -25.431% | 2024-12-06 -> trough 2025-04-08 -> recovery 2025-09-09 | dur 187d | recovered True | regime_on 0.843
   loss_tickers: [('MRNA', np.float64(-7260.0)), ('APP', np.float64(-5979.0)), ('MU', np.float64(-5075.0)), ('MGM', np.float64(-4055.0)), ('WBD', np.float64(-3975.0))]
   loss_industries: [('Semiconductors', np.float64(-9005.0)), ('Biotechnology', np.float64(-7260.0)), ('Internet', np.float64(-5608.0)), ('Computers', np.float64(-5376.0)), ('Lodging', np.float64(-5211.0))]
2. depth -24.79% | 2022-04-04 -> trough 2022-09-07 -> recovery 2023-06-08 | dur 296d | recovered True | regime_on 0.185
   loss_tickers: [('COIN', np.float64(-2632.0)), ('MOS', np.float64(-2606.0)), ('CVNA', np.float64(-2318.0)), ('OXY', np.float64(-1226.0)), ('TTD', np.float64(-1118.0))]
   loss_industries: [('Oil&Gas', np.float64(-3376.0)), ('Chemicals', np.float64(-3372.0)), ('Retail', np.float64(-3070.0)), ('Diversified Finan Serv', np.float64(-2632.0)), ('Advertising', np.float64(-1118.0))]
3. depth -23.973% | 2024-07-16 -> trough 2024-09-06 -> recovery 2024-11-22 | dur 92d | recovered True | regime_on 1.0
   loss_tickers: [('SMCI', np.float64(-7039.0)), ('NVDA', np.float64(-3826.0)), ('MU', np.float64(-3791.0)), ('MPWR', np.float64(-2753.0)), ('COHR', np.float64(-2630.0))]
   loss_industries: [('Computers', np.float64(-10444.0)), ('Semiconductors', np.float64(-10370.0)), ('Electronics', np.float64(-4351.0)), ('Banks', np.float64(-3896.0)), ('Media', np.float64(-2915.0))]
4. depth -20.795% | 2023-07-19 -> trough 2023-10-20 -> recovery 2023-12-19 | dur 107d | recovered True | regime_on 0.806
   loss_tickers: [('STX', np.float64(-2160.0)), ('ABNB', np.float64(-1826.0)), ('WDC', np.float64(-1664.0)), ('HOOD', np.float64(-1596.0)), ('COIN', np.float64(-1526.0))]
   loss_industries: [('Computers', np.float64(-4093.0)), ('Internet', np.float64(-2497.0)), ('Retail', np.float64(-1799.0)), ('Diversified Finan Serv', np.float64(-1709.0)), ('Oil&Gas', np.float64(-1397.0))]
5. depth -13.855% | 2026-06-02 -> trough 2026-07-02 -> recovery None | dur 21d | recovered False | regime_on 1.0
   loss_tickers: [('SNDK', np.float64(-10137.0)), ('TER', np.float64(-9675.0)), ('WDC', np.float64(-8636.0)), ('CASY', np.float64(-7712.0)), ('MU', np.float64(-7451.0))]
   loss_industries: [('Semiconductors', np.float64(-20377.0)), ('Computers', np.float64(-16170.0)), ('Telecommunications', np.float64(-6402.0)), ('Airlines', np.float64(-2385.0)), ('Retail', np.float64(-364.0))]

## baseline_hold20 — TOP 5 drawdown epizod

1. depth -39.037% | 2021-11-29 -> trough 2022-09-30 -> recovery 2023-02-01 | dur 295d | recovered True | regime_on 0.387
   loss_tickers: [('CVNA', np.float64(-4208.0)), ('UBER', np.float64(-2748.0)), ('DDOG', np.float64(-2623.0)), ('NUE', np.float64(-2451.0)), ('TTD', np.float64(-2281.0))]
   loss_industries: [('Retail', np.float64(-5656.0)), ('Internet', np.float64(-5131.0)), ('Chemicals', np.float64(-3981.0)), ('Diversified Finan Serv', np.float64(-2975.0)), ('Leisure Time', np.float64(-2599.0))]
2. depth -23.275% | 2024-12-06 -> trough 2025-04-08 -> recovery 2025-05-13 | dur 106d | recovered True | regime_on 0.843
   loss_tickers: [('MRNA', np.float64(-4029.0)), ('IVZ', np.float64(-2879.0)), ('RCL', np.float64(-2347.0)), ('BEN', np.float64(-2191.0)), ('FOXA', np.float64(-2153.0))]
   loss_industries: [('Diversified Finan Serv', np.float64(-6142.0)), ('Biotechnology', np.float64(-4994.0)), ('Media', np.float64(-4304.0)), ('Oil&Gas', np.float64(-3198.0)), ('Leisure Time', np.float64(-2347.0))]
3. depth -19.212% | 2023-07-19 -> trough 2023-10-03 -> recovery 2023-12-14 | dur 104d | recovered True | regime_on 0.926
   loss_tickers: [('SMCI', np.float64(-3214.0)), ('CFG', np.float64(-2304.0)), ('KEY', np.float64(-1702.0)), ('MRNA', np.float64(-1671.0)), ('NVDA', np.float64(-1255.0))]
   loss_industries: [('Banks', np.float64(-4006.0)), ('Computers', np.float64(-3214.0)), ('Biotechnology', np.float64(-1658.0)), ('Semiconductors', np.float64(-1255.0)), ('Electrical Compo&Equip', np.float64(-849.0))]
4. depth -17.621% | 2024-07-16 -> trough 2024-08-07 -> recovery 2024-11-11 | dur 83d | recovered True | regime_on 1.0
   loss_tickers: []
   loss_industries: []
5. depth -17.36% | 2023-02-15 -> trough 2023-04-26 -> recovery 2023-07-13 | dur 101d | recovered True | regime_on 0.898
   loss_tickers: [('CVNA', np.float64(-2905.0)), ('TSLA', np.float64(-2296.0)), ('MOS', np.float64(-2103.0)), ('APA', np.float64(-1183.0)), ('SATS', np.float64(-930.0))]
   loss_industries: [('Retail', np.float64(-2399.0)), ('Auto Manufacturers', np.float64(-2296.0)), ('Chemicals', np.float64(-2183.0)), ('Oil&Gas', np.float64(-1183.0)), ('Telecommunications', np.float64(-930.0))]

## regime200_hold20 — TOP 5 drawdown epizod

1. depth -29.298% | 2025-02-18 -> trough 2025-04-08 -> recovery 2025-09-19 | dur 148d | recovered True | regime_on 0.639
   loss_tickers: [('SNDK', np.float64(-8626.0)), ('MU', np.float64(-6620.0)), ('MRNA', np.float64(-5123.0)), ('AES', np.float64(-3522.0)), ('CCI', np.float64(-840.0))]
   loss_industries: [('Computers', np.float64(-8626.0)), ('Semiconductors', np.float64(-6620.0)), ('Biotechnology', np.float64(-5123.0)), ('Electric', np.float64(-3522.0)), ('REITS', np.float64(-840.0))]
2. depth -27.731% | 2022-03-29 -> trough 2022-09-06 -> recovery 2023-06-08 | dur 300d | recovered True | regime_on 0.216
   loss_tickers: [('NUE', np.float64(-2773.0)), ('CVNA', np.float64(-2692.0)), ('MOS', np.float64(-1875.0)), ('COIN', np.float64(-1676.0)), ('VRTX', np.float64(-1672.0))]
   loss_industries: [('Retail', np.float64(-4568.0)), ('Iron/Steel', np.float64(-2773.0)), ('Chemicals', np.float64(-2265.0)), ('Diversified Finan Serv', np.float64(-1676.0)), ('Biotechnology', np.float64(-1672.0))]
3. depth -21.684% | 2026-03-04 -> trough 2026-04-17 -> recovery 2026-05-08 | dur 46d | recovered True | regime_on 0.938
   loss_tickers: [('LYB', np.float64(-4840.0)), ('OXY', np.float64(-3563.0)), ('APA', np.float64(-3350.0)), ('CF', np.float64(-3041.0)), ('EOG', np.float64(-3002.0))]
   loss_industries: [('Oil&Gas', np.float64(-10505.0)), ('Chemicals', np.float64(-10210.0)), ('Beverages', np.float64(-2962.0)), ('Oil&Gas Services', np.float64(5467.0))]
4. depth -20.835% | 2024-05-20 -> trough 2024-09-06 -> recovery 2024-10-02 | dur 93d | recovered True | regime_on 1.0
   loss_tickers: [('SMCI', np.float64(-4500.0)), ('MRNA', np.float64(-4172.0)), ('MU', np.float64(-2736.0)), ('DELL', np.float64(-2396.0)), ('FSLR', np.float64(-1807.0))]
   loss_industries: [('Computers', np.float64(-6367.0)), ('Biotechnology', np.float64(-4172.0)), ('Semiconductors', np.float64(-2938.0)), ('Telecommunications', np.float64(-1948.0)), ('Banks', np.float64(-1863.0))]
5. depth -20.256% | 2026-06-02 -> trough 2026-07-02 -> recovery None | dur 21d | recovered False | regime_on 1.0
   loss_tickers: [('SNDK', np.float64(-10696.0)), ('TER', np.float64(-10208.0)), ('WDC', np.float64(-9111.0)), ('MU', np.float64(-7861.0)), ('GLW', np.float64(-6755.0))]
   loss_industries: [('Semiconductors', np.float64(-21499.0)), ('Computers', np.float64(-19807.0)), ('Telecommunications', np.float64(-6755.0)), ('Airlines', np.float64(-2516.0)), ('Healthcare-Products', np.float64(-97.0))]

## Regime200 effectiveness

### hold10

- baseline overall: {'total_return_pct': np.float64(325.796), 'max_drawdown_pct': -36.583, 'sharpe': 1.034, 'calmar': np.float64(8.906), 'avg_exposure': 0.999}
- regime overall: {'total_return_pct': np.float64(375.283), 'max_drawdown_pct': -25.431, 'sharpe': 1.197, 'calmar': np.float64(14.757), 'avg_exposure': 0.864}
- good_months_missed_by_regime: 0
- bad_months_avoided_by_regime: 2

| rok | base_ret | regime_ret | ret_diff | base_dd | regime_dd | dd_improve | regime_on% |
|---|---|---|---|---|---|---|---|
| 2021 | 5.072 | 5.072 | 0.0 | -12.178 | -12.178 | 0.0 | 1.0 |
| 2022 | -24.266 | -18.006 | 6.26 | -33.001 | -24.79 | 8.211 | 0.339 |
| 2023 | 113.217 | 82.791 | -30.426 | -18.462 | -20.795 | -2.333 | 0.86 |
| 2024 | 39.049 | 29.086 | -9.963 | -17.169 | -23.973 | -6.804 | 1.0 |
| 2025 | 17.091 | 37.295 | 20.204 | -33.654 | -24.919 | 8.735 | 0.86 |
| 2026 | 51.608 | 69.464 | 17.856 | -21.147 | -13.855 | 7.292 | 0.984 |

### hold20

- baseline overall: {'total_return_pct': np.float64(431.696), 'max_drawdown_pct': -39.037, 'sharpe': 1.223, 'calmar': np.float64(11.059), 'avg_exposure': 0.999}
- regime overall: {'total_return_pct': np.float64(401.452), 'max_drawdown_pct': -29.298, 'sharpe': 1.236, 'calmar': np.float64(13.702), 'avg_exposure': 0.88}
- good_months_missed_by_regime: 2
- bad_months_avoided_by_regime: 2

| rok | base_ret | regime_ret | ret_diff | base_dd | regime_dd | dd_improve | regime_on% |
|---|---|---|---|---|---|---|---|
| 2021 | 8.361 | 8.361 | 0.0 | -10.484 | -10.484 | 0.0 | 1.0 |
| 2022 | -22.291 | -15.206 | 7.085 | -37.474 | -27.731 | 9.743 | 0.339 |
| 2023 | 66.565 | 62.122 | -4.443 | -19.212 | -19.633 | -0.421 | 0.86 |
| 2024 | 35.326 | 64.999 | 29.673 | -17.621 | -20.835 | -3.214 | 1.0 |
| 2025 | 56.387 | 46.134 | -10.253 | -22.033 | -29.298 | -7.265 | 0.86 |
| 2026 | 75.279 | 35.386 | -39.893 | -13.879 | -21.684 | -7.805 | 0.984 |

## Special checks (ticker koncentrace)

### baseline_hold10
- total_pnl: 333119.0
- top5_tickers_pnl: [('SNDK', np.float64(54591.0)), ('CVNA', np.float64(52227.0)), ('APP', np.float64(37214.0)), ('LITE', np.float64(30697.0)), ('DDOG', np.float64(20222.0))] (share 58.52%)
- CVNA: pnl 52227.0 (15.68% of total)
- SMCI: pnl -20740.0 (-6.23% of total)
- SNDK: pnl 54591.0 (16.39% of total)
- INTC: pnl 14688.0 (4.41% of total)

### regime200_hold10
- total_pnl: 383458.0
- top5_tickers_pnl: [('SNDK', np.float64(64463.0)), ('INTC', np.float64(28558.0)), ('DDOG', np.float64(25894.0)), ('APP', np.float64(24114.0)), ('CVNA', np.float64(21431.0))] (share 42.89%)
- CVNA: pnl 21431.0 (5.59% of total)
- SMCI: pnl 20811.0 (5.43% of total)
- SNDK: pnl 64463.0 (16.81% of total)
- INTC: pnl 28558.0 (7.45% of total)

### baseline_hold20
- total_pnl: 440841.0
- top5_tickers_pnl: [('SNDK', np.float64(74084.0)), ('APP', np.float64(47146.0)), ('MU', np.float64(41438.0)), ('INTC', np.float64(29464.0)), ('CVNA', np.float64(25719.0))] (share 49.42%)
- CVNA: pnl 25719.0 (5.83% of total)
- SMCI: pnl -2839.0 (-0.64% of total)
- SNDK: pnl 74084.0 (16.81% of total)
- INTC: pnl 29464.0 (6.68% of total)

### regime200_hold20
- total_pnl: 410077.0
- top5_tickers_pnl: [('SNDK', np.float64(70941.0)), ('LITE', np.float64(31510.0)), ('DDOG', np.float64(29265.0)), ('AMD', np.float64(27701.0)), ('HOOD', np.float64(27408.0))] (share 45.56%)
- CVNA: pnl 10764.0 (2.62% of total)
- SMCI: pnl 10354.0 (2.52% of total)
- SNDK: pnl 70941.0 (17.3% of total)
- INTC: pnl 17155.0 (4.18% of total)

## Vyhrady

- **SURVIVORSHIP: current 503 universe.**
- diagnostic only, NE optimalizace.
- regime index = equal-weight universe (ne SPY).
- DD epizoda recovery = navrat na predchozi peak.
- attribution z pnl trades v obdobi.
- Sharpe/DD orientacni; in-sample jeden 5lety window.
