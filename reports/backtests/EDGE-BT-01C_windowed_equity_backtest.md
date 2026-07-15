# EDGE-BT-01C — Windowed Equity Backtest

## Simulacni okno (OPRAVA)

- sim_start: 2025-07-09
- sim_end: 2026-07-02
- sim_days: 248
- signal_days: 244
- **sim_days_not_7169: True** (overeni, ze okno je overlap, ne cela historie)

Oprava: Oprava vs 01B: equity loop iteruje jen pres sim okno (overlap + exit buffer), ne cely close_matrix (7169 dni od 1997).

Initial capital: 100000.0, max_positions: 10

**Vyhrady: skutecna denni equity pres SIM okno. Sharpe/DD orientacni (kratky sample). Survivorship 503 soucasnych. Bez kapacity/likvidity/fillu.**

## hold 10D

| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | max_expo | avg_pos | days_mkt/sim | trades | avg_net | median_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 151.2113 | 154.9714 | 2.803 | -14.0744 | 0.9212 | 1.0 | 9.27 | 246/248 | 233 | 4.2186 | 2.1494 | 0.5923 | OK |
| 0bps | mle_top10_only | 165.4318 | 169.6441 | 2.889 | -16.4348 | 0.9919 | 1.0 | 9.92 | 246/248 | 250 | 4.1544 | 1.886 | 0.564 | OK |
| 5bps | edge | 148.319 | 151.9887 | 2.77 | -14.1287 | 0.9211 | 1.0 | 9.27 | 246/248 | 233 | 4.1665 | 2.0983 | 0.5923 | OK |
| 5bps | mle_top10_only | 162.1266 | 166.2327 | 2.854 | -16.4762 | 0.9919 | 1.0 | 9.92 | 246/248 | 250 | 4.1023 | 1.8351 | 0.564 | OK |
| 15bps | edge | 142.6346 | 146.1284 | 2.705 | -14.237 | 0.9211 | 1.0 | 9.27 | 246/248 | 233 | 4.0624 | 1.9963 | 0.5837 | OK |
| 15bps | mle_top10_only | 155.6397 | 159.5392 | 2.783 | -16.5591 | 0.9918 | 0.9999 | 9.92 | 246/248 | 250 | 3.9983 | 1.7332 | 0.564 | OK |
| 25bps | edge | 137.0808 | 140.4048 | 2.64 | -14.3452 | 0.9211 | 0.9999 | 9.27 | 246/248 | 233 | 3.9584 | 1.8943 | 0.5708 | OK |
| 25bps | mle_top10_only | 149.314 | 153.0147 | 2.711 | -16.6418 | 0.9918 | 0.9999 | 9.92 | 246/248 | 250 | 3.8943 | 1.6316 | 0.552 | OK |

## hold 20D

| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | max_expo | avg_pos | days_mkt/sim | trades | avg_net | median_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 100.8267 | 103.098 | 2.16 | -16.4229 | 0.9522 | 1.0 | 9.61 | 246/248 | 122 | 6.5089 | 2.5404 | 0.5984 | OK |
| 0bps | mle_top10_only | 155.8072 | 159.7119 | 2.794 | -14.771 | 0.9919 | 1.0 | 9.92 | 246/248 | 130 | 8.0277 | 3.2271 | 0.5846 | OK |
| 5bps | edge | 99.6165 | 101.8545 | 2.143 | -16.4504 | 0.9521 | 1.0 | 9.61 | 246/248 | 122 | 6.4557 | 2.4892 | 0.5984 | OK |
| 5bps | mle_top10_only | 154.1452 | 157.9975 | 2.776 | -14.8133 | 0.9919 | 1.0 | 9.92 | 246/248 | 130 | 7.9737 | 3.1754 | 0.5846 | OK |
| 15bps | edge | 97.2183 | 99.3905 | 2.108 | -16.5054 | 0.9521 | 1.0 | 9.61 | 246/248 | 122 | 6.3493 | 2.3868 | 0.5984 | OK |
| 15bps | mle_top10_only | 150.8537 | 154.6026 | 2.738 | -14.8979 | 0.9918 | 0.9999 | 9.92 | 246/248 | 130 | 7.8658 | 3.0724 | 0.5846 | OK |
| 25bps | edge | 94.8491 | 96.9568 | 2.073 | -16.5604 | 0.952 | 0.9999 | 9.61 | 246/248 | 122 | 6.243 | 2.2844 | 0.5902 | OK |
| 25bps | mle_top10_only | 147.6052 | 151.2527 | 2.7 | -14.9823 | 0.9918 | 0.9999 | 9.92 | 246/248 | 130 | 7.758 | 2.9693 | 0.5769 | OK |

### edge hold10 15bps — detail
- final_equity: 242634.62
- days_in_market/sim_days: 246/248
- avg_exposure: 0.9211 max: 1.0 avg_pos: 9.27
- audit_clean: True
- best_trade: SNDK 80.7187% pnl=8357.57
- worst_trade: SMCI -31.6532% pnl=-7819.46
- trades_by_industry_top: {'Semiconductors': 50, 'Computers': 35, 'Telecommunications': 13, 'Oil&Gas': 12, 'Airlines': 10, 'Internet': 9, 'Healthcare-Services': 9, 'Software': 7}

### mle_top10_only hold10 15bps — detail
- final_equity: 255639.72
- days_in_market/sim_days: 246/248
- avg_exposure: 0.9918 max: 0.9999 avg_pos: 9.92
- audit_clean: True
- best_trade: SNDK 57.4933% pnl=7744.54
- worst_trade: SMCI -27.8366% pnl=-7530.91
- trades_by_industry_top: {'Computers': 49, 'Semiconductors': 39, 'Telecommunications': 16, 'Software': 12, 'Internet': 12, 'Chemicals': 10, 'Oil&Gas': 8, 'Media': 7}

### edge hold20 15bps — detail
- final_equity: 197218.31
- days_in_market/sim_days: 246/248
- avg_exposure: 0.9521 max: 1.0 avg_pos: 9.61
- audit_clean: True
- best_trade: INTC 108.0491% pnl=15316.82
- worst_trade: SMCI -39.9487% pnl=-8143.12
- trades_by_industry_top: {'Semiconductors': 27, 'Computers': 19, 'Airlines': 8, 'Telecommunications': 8, 'Software': 6, 'Internet': 4, 'Oil&Gas': 4, 'Oil&Gas Services': 4}

### mle_top10_only hold20 15bps — detail
- final_equity: 250853.72
- days_in_market/sim_days: 246/248
- avg_exposure: 0.9918 max: 0.9999 avg_pos: 9.92
- audit_clean: True
- best_trade: SNDK 119.0148% pnl=17535.16
- worst_trade: MRNA -20.6151% pnl=-2061.51
- trades_by_industry_top: {'Computers': 29, 'Semiconductors': 21, 'Telecommunications': 10, 'Internet': 9, 'Software': 7, 'Healthcare-Products': 4, 'Electronics': 4, 'Biotechnology': 3}

## Audit checks

- sim_days ~244-270 (ne 7169): 248 -> OK
- positions <= 10, cash >= 0, exposure <= 100%: viz audit sloupec
- total_return z final_equity/initial-1
- Sharpe/maxDD z equity krivky POUZE v sim okne

## Klicove otazky (po oprave)

- ma EDGE vyssi validni portfolio return? viz tot_ret/ann.
- ma EDGE nizsi drawdown / lepsi Sharpe? viz maxDD/sharpe.
- stoji IRC filtr za ztratu breadth? porovnej n_trades + avg_net.
- je IRC lepsi jako vaha nez tvrdy filtr? (indikace z avg_net vs n_trades trade-off)

## Vyhrady (souhrn)

- equity loop POUZE pres sim okno (oprava 01B bugu 7169 dni).
- sizing 10% aktualni equity, cash ucet, MTM denne.
- entry open[t+1], exit close[entry+H], konec okna -> partial.
- naklady half round-trip (bps/2) na stranu.
- survivorship 503 soucasnych; kratky sample; bez kapacity/fillu.
