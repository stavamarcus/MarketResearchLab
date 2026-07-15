# MLE-BT-03 — Drawdown Control (MLE-only)

## !!! SURVIVORSHIP WARNING

current-universe test, MAY CONTAIN SURVIVORSHIP BIAS. NOT survivorship-free.

## Predem dane parametry (NEoptimalizovane)

- stop_loss: 0.08 (8%, O'Neil/CAN SLIM standard)
- regime_ma: 200 (200D trend filtr)
- konvencni defaulty, NEladene na data

## Simulacni okno

- 2021-07-01..2026-07-02 (1256 dni), signal_days 1256

## Varianty

- baseline: bez kontroly (= MLE-BT-02)
- stop8: stop-loss 8% (close-based)
- regime200: nove pozice jen kdyz index > 200D MA
- stop8_regime200: obe kombinovane

## hold 10D

### 0 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 38.9264 | 414.8223 | -35.722 | 1.147 | 1.09 | 1260 | 0 | 0.9992 | 0.5413 |
| stop8 | 26.9454 | 228.4281 | -36.614 | 0.882 | 0.736 | 1467 | 383 | 0.9909 | 0.4949 |
| regime200 | 41.2987 | 460.1535 | -24.5796 | 1.307 | 1.68 | 1090 | 0 | 0.8639 | 0.533 |
| stop8_regime200 | 28.0108 | 242.3971 | -32.1006 | 0.986 | 0.873 | 1222 | 295 | 0.849 | 0.5016 |

### 5 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 37.1734 | 383.2487 | -36.0103 | 1.11 | 1.032 | 1260 | 0 | 0.9992 | 0.5389 |
| stop8 | 25.1224 | 205.5832 | -37.4567 | 0.839 | 0.671 | 1467 | 383 | 0.9909 | 0.4928 |
| regime200 | 39.7545 | 430.2991 | -24.8312 | 1.27 | 1.601 | 1090 | 0 | 0.8639 | 0.5294 |
| stop8_regime200 | 26.4723 | 222.3729 | -32.451 | 0.944 | 0.816 | 1222 | 295 | 0.8489 | 0.4984 |

### 15 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 33.7338 | 325.7959 | -36.5828 | 1.034 | 0.922 | 1260 | 0 | 0.9991 | 0.5333 |
| stop8 | 21.5549 | 164.5553 | -39.4759 | 0.752 | 0.546 | 1467 | 383 | 0.9908 | 0.4908 |
| regime200 | 36.7167 | 375.2828 | -25.4306 | 1.197 | 1.444 | 1090 | 0 | 0.8638 | 0.5284 |
| stop8_regime200 | 23.4511 | 185.7738 | -33.1462 | 0.862 | 0.708 | 1222 | 295 | 0.8489 | 0.4967 |

### 25 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 30.3807 | 275.1784 | -37.1502 | 0.958 | 0.818 | 1260 | 0 | 0.9991 | 0.5286 |
| stop8 | 18.0896 | 129.0408 | -41.9596 | 0.665 | 0.431 | 1467 | 383 | 0.9908 | 0.486 |
| regime200 | 33.7453 | 325.979 | -26.0252 | 1.123 | 1.297 | 1090 | 0 | 0.8638 | 0.5202 |
| stop8_regime200 | 20.5027 | 153.3367 | -33.834 | 0.78 | 0.606 | 1222 | 295 | 0.8488 | 0.4918 |

## hold 20D

### 0 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 42.5274 | 484.8554 | -38.1167 | 1.284 | 1.116 | 630 | 0 | 0.9992 | 0.5476 |
| stop8 | 21.8946 | 168.2608 | -43.6756 | 0.783 | 0.501 | 829 | 333 | 0.989 | 0.4717 |
| regime200 | 40.5653 | 445.8131 | -29.1928 | 1.292 | 1.39 | 560 | 0 | 0.8798 | 0.5339 |
| stop8_regime200 | 19.0184 | 138.1605 | -39.9581 | 0.762 | 0.476 | 714 | 282 | 0.8611 | 0.4566 |

### 5 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 41.6219 | 466.569 | -38.4249 | 1.264 | 1.083 | 630 | 0 | 0.9992 | 0.546 |
| stop8 | 20.9122 | 157.6572 | -43.8681 | 0.757 | 0.477 | 829 | 333 | 0.989 | 0.4692 |
| regime200 | 39.7707 | 430.6056 | -29.228 | 1.274 | 1.361 | 560 | 0 | 0.8798 | 0.5268 |
| stop8_regime200 | 18.1871 | 129.9845 | -40.1536 | 0.737 | 0.453 | 714 | 282 | 0.8611 | 0.4552 |

### 15 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 39.8282 | 431.6961 | -39.0367 | 1.223 | 1.02 | 630 | 0 | 0.9991 | 0.5444 |
| stop8 | 18.9712 | 137.69 | -44.2509 | 0.706 | 0.429 | 829 | 333 | 0.9889 | 0.468 |
| regime200 | 38.1949 | 401.4521 | -29.2981 | 1.236 | 1.304 | 560 | 0 | 0.8797 | 0.5268 |
| stop8_regime200 | 16.5423 | 114.4677 | -40.5426 | 0.686 | 0.408 | 714 | 282 | 0.861 | 0.4538 |

### 25 bps

| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | trades | stops | avg_expo | win_rate |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 38.0575 | 398.9729 | -39.6423 | 1.183 | 0.96 | 630 | 0 | 0.9991 | 0.5429 |
| stop8 | 17.0616 | 119.2739 | -44.6311 | 0.654 | 0.382 | 829 | 333 | 0.9889 | 0.468 |
| regime200 | 36.637 | 373.9031 | -29.3682 | 1.197 | 1.248 | 560 | 0 | 0.8797 | 0.5232 |
| stop8_regime200 | 14.9207 | 100.0011 | -40.929 | 0.636 | 0.365 | 714 | 282 | 0.861 | 0.4538 |

## Jak cist (Calmar = CAGR / |maxDD|)

- Calmar vyssi = lepsi pomer vynos/drawdown.
- cil: snizit maxDD pri co nejmensi ztrate CAGR -> nejvyssi Calmar.

## Klicove otazky

- ktera varianta ma nejvyssi Calmar (nejlepsi vynos/DD pomer)?
- kolik CAGR se obetuje za snizeni maxDD?
- whipsaw: kolik stop_exits (vysoke = stop uriznul hodne pozic)?

## Vyhrady (souhrn)

- **SURVIVORSHIP BIAS: current 503 universe.**
- parametry PREDEM dane (8%, 200D), NEladene -> ale i tak IN-SAMPLE
  na jednom 5letem okne. Ne out-of-sample dukaz.
- stop CLOSE-based (aproximace, ne intraday fill).
- regime index = equal-weight universe (ne SPY).
- Sharpe/DD orientacni; bez kapacity/likvidity/slippage nad bps.
