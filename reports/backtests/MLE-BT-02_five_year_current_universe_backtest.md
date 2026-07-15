# MLE-BT-02 — Five-Year Current-Universe Backtest (MLE-only)

## !!! SURVIVORSHIP WARNING

This is a current-universe extended test and MAY CONTAIN SURVIVORSHIP BIAS. Universe = 503 CURRENT tickers. NOT the final survivorship-free historical proof.

## Simulacni okno

- period_requested: 2021-07-01..2026-07-02
- sim_start: 2021-07-01
- sim_end: 2026-07-02
- sim_days: 1256
- signal_days: 1256
- initial_capital: 100000.0, max_positions: 10

## Benchmarky

- equal_weight_universe: {'total_return_pct': np.float64(71.933), 'cagr_pct': np.float64(11.4864), 'max_drawdown_pct': -21.0385, 'sharpe_annualized': 0.734}
- buy_and_hold_universe: {'total_return_pct': np.float64(78.6491), 'cagr_pct': np.float64(12.3468), 'max_drawdown_pct': -20.8921, 'sharpe_annualized': 0.775}
- SPY: NENI v DATA-06 (universe=S&P clenove, ne ETF); proxy = equal_weight_universe.

## MLE-only strategie

### hold 10D

| cost | tot_ret% | CAGR% | sharpe | maxDD% | avg_expo | avg_pos | days_mkt/sim | trades | avg_net | median_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | 414.8223 | 38.9264 | 1.147 | -35.722 | 0.9992 | 9.99 | 1255/1256 | 1260 | 1.5639 | 0.7411 | 0.5413 | OK |
| 5bps | 383.2487 | 37.1734 | 1.11 | -36.0103 | 0.9992 | 9.99 | 1255/1256 | 1260 | 1.5131 | 0.6907 | 0.5389 | OK |
| 15bps | 325.7959 | 33.7338 | 1.034 | -36.5828 | 0.9991 | 9.99 | 1255/1256 | 1260 | 1.4117 | 0.5901 | 0.5333 | OK |
| 25bps | 275.1784 | 30.3807 | 0.958 | -37.1502 | 0.9991 | 9.99 | 1255/1256 | 1260 | 1.3103 | 0.4896 | 0.5286 | OK |

#### hold10 15bps detail
- final_equity: 425795.89 (z 100000.0)
- CAGR: 33.7338% | maxDD: -36.5828% | sharpe: 1.034
- best_trade: CVNA 122.1454% pnl=10994.52
- worst_trade: SMCI -45.1551% pnl=-9456.15
- trades_by_industry_top: {'Internet': 109, 'Computers': 102, 'Semiconductors': 99, 'Oil&Gas': 86, 'Retail': 84, 'Software': 71, 'Chemicals': 40, 'Telecommunications': 40, 'Electric': 37, 'Diversified Finan Serv': 37}

### hold 20D

| cost | tot_ret% | CAGR% | sharpe | maxDD% | avg_expo | avg_pos | days_mkt/sim | trades | avg_net | median_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | 484.8554 | 42.5274 | 1.284 | -38.1167 | 0.9992 | 9.99 | 1255/1256 | 630 | 3.2919 | 1.0652 | 0.5476 | OK |
| 5bps | 466.569 | 41.6219 | 1.264 | -38.4249 | 0.9992 | 9.99 | 1255/1256 | 630 | 3.2402 | 1.0147 | 0.546 | OK |
| 15bps | 431.6961 | 39.8282 | 1.223 | -39.0367 | 0.9991 | 9.99 | 1255/1256 | 630 | 3.137 | 0.9137 | 0.5444 | OK |
| 25bps | 398.9729 | 38.0575 | 1.183 | -39.6423 | 0.9991 | 9.99 | 1255/1256 | 630 | 3.034 | 0.8129 | 0.5429 | OK |

#### hold20 15bps detail
- final_equity: 531696.1 (z 100000.0)
- CAGR: 39.8282% | maxDD: -39.0367% | sharpe: 1.223
- best_trade: CVNA 196.2698% pnl=17254.46
- worst_trade: SMCI -32.4517% pnl=-6659.92
- trades_by_industry_top: {'Retail': 55, 'Internet': 51, 'Computers': 46, 'Oil&Gas': 45, 'Semiconductors': 45, 'Software': 33, 'Healthcare-Products': 21, 'Diversified Finan Serv': 21, 'Chemicals': 19, 'Telecommunications': 19}

## Klicove otazky

- zustane MLE edge silny i mimo posledni rok (5 let)?
- porazi MLE-only equal-weight universe a buy-and-hold?
- jak vysoky je maxDD pres vice rezimu (5 let vc. 2022 bear)?

## Audit

- sim okno: 1256 dni (windowed, ne cela historie)
- cash/exposure audit: viz audit sloupec

## Vyhrady (souhrn)

- **SURVIVORSHIP BIAS: current 503 universe, prezivsi tickery.**
- NENI survivorship-free historicky dukaz (chybi delistovane/vypadle).
- windowed equity (oprava 01B/01C), cash ucet, MTM.
- entry open[t+1], exit close[entry+H], konec okna -> partial.
- Sharpe/DD orientacni; bez kapacity/likvidity/fillu.
- recent IPO tickery bez 2021 dat -> rank az od jejich prvniho data.
