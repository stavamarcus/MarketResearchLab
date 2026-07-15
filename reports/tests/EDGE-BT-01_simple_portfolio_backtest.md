# EDGE-BT-01 — Simple Portfolio Backtest

Overlap: 2025-07-09..2026-06-27 (244 obchodnich dni)
Max positions: 10

Universe baseline: {'total_return_pct': 16.7561, 'max_drawdown_pct': -7.8709, 'sharpe_annualized_orientacni': 1.401, 'daily_vol_pct': 0.7512}
SPY: NENI v DATA-06 (universe=S&P clenove, ne ETF); proxy = universe_baseline

**Vyhrady: signal->tradable aproximace. Sharpe/DD orientacni (kratky sample 245 dni, prekryvne drzeni). Survivorship 503 soucasnych. Bez kapacity/likvidity.**

## Varianta: all

### hold 10D

| cost | strat | total_ret% | avg_trade_net | win_rate | maxDD% | sharpe | n_trades | avg_expo | turnover |
|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 159.2812 | 4.2186 | 0.5923 | -7.481 | 0.739 | 233 | 0.0321 | 0.0325 |
| 0bps | mle_top10_only | 165.4319 | 4.1544 | 0.564 | -5.2228 | 0.53 | 250 | 0.0343 | 0.0349 |
| 5bps | edge | 156.303 | 4.1686 | 0.5923 | -7.5416 | 0.731 | 233 | 0.0321 | 0.0325 |
| 5bps | mle_top10_only | 162.2543 | 4.1044 | 0.564 | -5.3201 | 0.525 | 250 | 0.0343 | 0.0349 |
| 15bps | edge | 150.448 | 4.0686 | 0.5837 | -7.6627 | 0.716 | 233 | 0.0321 | 0.0325 |
| 15bps | mle_top10_only | 156.0083 | 4.0044 | 0.564 | -5.5147 | 0.516 | 250 | 0.0343 | 0.0349 |
| 25bps | edge | 144.7254 | 3.9686 | 0.5708 | -7.7836 | 0.701 | 233 | 0.0321 | 0.0325 |
| 25bps | mle_top10_only | 149.9052 | 3.9044 | 0.552 | -5.709 | 0.507 | 250 | 0.0343 | 0.0349 |

### hold 20D

| cost | strat | total_ret% | avg_trade_net | win_rate | maxDD% | sharpe | n_trades | avg_expo | turnover |
|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 115.0997 | 6.5089 | 0.5984 | -9.8579 | 0.616 | 122 | 0.0332 | 0.017 |
| 0bps | mle_top10_only | 155.8071 | 8.0277 | 0.5846 | -7.0568 | 0.401 | 130 | 0.0343 | 0.0181 |
| 5bps | edge | 113.7979 | 6.4589 | 0.5984 | -9.8946 | 0.612 | 122 | 0.0332 | 0.017 |
| 5bps | mle_top10_only | 154.2571 | 7.9777 | 0.5846 | -7.1068 | 0.399 | 130 | 0.0343 | 0.0181 |
| 15bps | edge | 111.2173 | 6.3589 | 0.5984 | -9.9678 | 0.603 | 122 | 0.0332 | 0.017 |
| 15bps | mle_top10_only | 151.1831 | 7.8777 | 0.5846 | -7.2068 | 0.396 | 130 | 0.0343 | 0.0181 |
| 25bps | edge | 108.6672 | 6.2589 | 0.5902 | -10.0411 | 0.594 | 122 | 0.0332 | 0.017 |
| 25bps | mle_top10_only | 148.1433 | 7.7777 | 0.5769 | -7.3068 | 0.393 | 130 | 0.0343 | 0.0181 |

#### all hold10 15bps edge — koncentrace
- trades_by_sector: {'Technology': 92, 'Consumer, Cyclical': 31, 'Industrial': 30, 'Consumer, Non-cyclical': 29, 'Communications': 24, 'Energy': 18, 'Basic Materials': 5, 'Utilities': 3}
- trades_by_industry_top: {'Semiconductors': 50, 'Computers': 35, 'Telecommunications': 13, 'Oil&Gas': 12, 'Airlines': 10, 'Internet': 9, 'Healthcare-Services': 9, 'Software': 7}
- best_trade: SNDK 80.84% (2025-09-03->2025-09-17)
- worst_trade: SMCI -31.7006% (2026-05-29->2026-06-12)

## Varianta: ex_exceptions

### hold 10D

| cost | strat | total_ret% | avg_trade_net | win_rate | maxDD% | sharpe | n_trades | avg_expo | turnover |
|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 99.1998 | 3.0792 | 0.5957 | -8.9358 | 0.676 | 230 | 0.0316 | 0.0321 |
| 0bps | mle_top10_only | 120.0286 | 3.2754 | 0.56 | -6.6123 | 0.613 | 250 | 0.0342 | 0.0349 |
| 5bps | edge | 96.9323 | 3.0292 | 0.5957 | -9.0335 | 0.666 | 230 | 0.0316 | 0.0321 |
| 5bps | mle_top10_only | 117.3336 | 3.2254 | 0.556 | -6.6983 | 0.606 | 250 | 0.0342 | 0.0349 |
| 15bps | edge | 92.4738 | 2.9292 | 0.5783 | -9.2287 | 0.646 | 230 | 0.0316 | 0.0321 |
| 15bps | mle_top10_only | 112.0397 | 3.1254 | 0.556 | -6.8701 | 0.59 | 250 | 0.0342 | 0.0349 |
| 25bps | edge | 88.1152 | 2.8292 | 0.5652 | -9.4235 | 0.626 | 230 | 0.0316 | 0.0321 |
| 25bps | mle_top10_only | 106.8718 | 3.0254 | 0.548 | -7.0417 | 0.575 | 250 | 0.0342 | 0.0349 |

### hold 20D

| cost | strat | total_ret% | avg_trade_net | win_rate | maxDD% | sharpe | n_trades | avg_expo | turnover |
|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 105.0176 | 6.0584 | 0.6066 | -10.3701 | 0.663 | 122 | 0.0332 | 0.017 |
| 0bps | mle_top10_only | 115.261 | 6.301 | 0.5846 | -6.5847 | 0.456 | 130 | 0.0343 | 0.0181 |
| 5bps | edge | 103.7765 | 6.0084 | 0.6066 | -10.4066 | 0.658 | 122 | 0.0332 | 0.017 |
| 5bps | mle_top10_only | 113.9148 | 6.251 | 0.5846 | -6.6813 | 0.454 | 130 | 0.0343 | 0.0181 |
| 15bps | edge | 101.3164 | 5.9084 | 0.6066 | -10.4794 | 0.648 | 122 | 0.0332 | 0.017 |
| 15bps | mle_top10_only | 111.246 | 6.151 | 0.5846 | -6.8745 | 0.449 | 130 | 0.0343 | 0.0181 |
| 25bps | edge | 98.8855 | 5.8084 | 0.5984 | -10.5523 | 0.638 | 122 | 0.0332 | 0.017 |
| 25bps | mle_top10_only | 108.6087 | 6.051 | 0.5769 | -7.0674 | 0.443 | 130 | 0.0343 | 0.0181 |

#### ex_exceptions hold10 15bps edge — koncentrace
- trades_by_sector: {'Technology': 85, 'Consumer, Cyclical': 35, 'Industrial': 31, 'Consumer, Non-cyclical': 29, 'Communications': 23, 'Energy': 18, 'Basic Materials': 5, 'Utilities': 3}
- trades_by_industry_top: {'Semiconductors': 52, 'Computers': 26, 'Telecommunications': 13, 'Oil&Gas': 12, 'Airlines': 11, 'Healthcare-Services': 10, 'Internet': 9, 'Software': 7}
- best_trade: INTC 54.664% (2026-04-27->2026-05-11)
- worst_trade: SMCI -31.7006% (2026-05-29->2026-06-12)

## Vyhrady (souhrn)

- total_return aproximace: equity z realized trades / MAX_POSITIONS.
- Sharpe/DD orientacni, kratky sample.
- entry open[t+1], exit close[entry+H]; konec dat -> partial exit.
- naklady odectene jako round-trip bps z trade returnu.
- SPY chybi v DATA-06; proxy universe_baseline.
- survivorship: 503 soucasnych tickeru.
- bez kapacity, likvidity, realneho fillu.
