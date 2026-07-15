# EDGE-BT-01B — Equity Accounting Audit

Overlap: 2025-07-09..2026-06-27 (244 obchodnich dni)
Initial capital: 100000.0, max_positions: 10, target_weight: 0.1

**Oprava vs EDGE-BT-01:** EDGE-BT-01 total_return byl aproximace (suma trade returns / max_pos), ignoroval cash a nizke exposure. Tento audit pouziva skutecnou denni equity krivku s cash uctem.

**Vyhrady: skutecna denni equity + cash ucet. Sharpe/DD orientacni (245 dni). Survivorship 503 soucasnych. Bez kapacity/likvidity/fillu.**

## hold 10D

| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | max_expo | avg_pos | days_mkt | trades | avg_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 151.2113 | 3.2909 | 0.513 | -14.0744 | 0.0319 | 1.0 | 0.32 | 246 | 233 | 4.2186 | 0.5923 | OK |
| 0bps | mle_top10_only | 165.4318 | 3.491 | 0.528 | -16.4348 | 0.0343 | 1.0 | 0.34 | 246 | 250 | 4.1544 | 0.564 | OK |
| 5bps | edge | 148.319 | 3.2488 | 0.507 | -14.1287 | 0.0319 | 1.0 | 0.32 | 246 | 233 | 4.1665 | 0.5923 | OK |
| 5bps | mle_top10_only | 162.1266 | 3.4454 | 0.522 | -16.4762 | 0.0343 | 1.0 | 0.34 | 246 | 250 | 4.1023 | 0.564 | OK |
| 15bps | edge | 142.6346 | 3.1648 | 0.495 | -14.237 | 0.0319 | 1.0 | 0.32 | 246 | 233 | 4.0624 | 0.5837 | OK |
| 15bps | mle_top10_only | 155.6397 | 3.3543 | 0.509 | -16.5591 | 0.0343 | 0.9999 | 0.34 | 246 | 250 | 3.9983 | 0.564 | OK |
| 25bps | edge | 137.0808 | 3.0809 | 0.484 | -14.3452 | 0.0319 | 0.9999 | 0.32 | 246 | 233 | 3.9584 | 0.5708 | OK |
| 25bps | mle_top10_only | 149.314 | 3.2633 | 0.496 | -16.6418 | 0.0343 | 0.9999 | 0.34 | 246 | 250 | 3.8943 | 0.552 | OK |

## hold 20D

| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | max_expo | avg_pos | days_mkt | trades | avg_net | win_rate | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0bps | edge | 100.8267 | 2.4813 | 0.397 | -16.4229 | 0.0329 | 1.0 | 0.33 | 246 | 122 | 6.5089 | 0.5984 | OK |
| 0bps | mle_top10_only | 155.8072 | 3.3567 | 0.511 | -14.771 | 0.0343 | 1.0 | 0.34 | 246 | 130 | 8.0277 | 0.5846 | OK |
| 5bps | edge | 99.6165 | 2.4595 | 0.394 | -16.4504 | 0.0329 | 1.0 | 0.33 | 246 | 122 | 6.4557 | 0.5984 | OK |
| 5bps | mle_top10_only | 154.1452 | 3.333 | 0.508 | -14.8133 | 0.0343 | 1.0 | 0.34 | 246 | 130 | 7.9737 | 0.5846 | OK |
| 15bps | edge | 97.2183 | 2.416 | 0.388 | -16.5054 | 0.0329 | 1.0 | 0.33 | 246 | 122 | 6.3493 | 0.5984 | OK |
| 15bps | mle_top10_only | 150.8537 | 3.2857 | 0.501 | -14.8979 | 0.0343 | 0.9999 | 0.34 | 246 | 130 | 7.8658 | 0.5846 | OK |
| 25bps | edge | 94.8491 | 2.3725 | 0.382 | -16.5604 | 0.0329 | 0.9999 | 0.33 | 246 | 122 | 6.243 | 0.5902 | OK |
| 25bps | mle_top10_only | 147.6052 | 3.2384 | 0.494 | -14.9823 | 0.0343 | 0.9999 | 0.34 | 246 | 130 | 7.758 | 0.5769 | OK |

### edge hold10 15bps — detail
- final_equity: 242634.62
- days_in_market: 246/7169
- avg_exposure: 0.0319 max: 1.0
- audit_clean: True
- best_trade: SNDK 80.7187% pnl=8357.57
- worst_trade: SMCI -31.6532% pnl=-7819.46
- trades_by_industry_top: {'Semiconductors': 50, 'Computers': 35, 'Telecommunications': 13, 'Oil&Gas': 12, 'Airlines': 10, 'Internet': 9, 'Healthcare-Services': 9, 'Software': 7}

### mle_top10_only hold10 15bps — detail
- final_equity: 255639.72
- days_in_market: 246/7169
- avg_exposure: 0.0343 max: 0.9999
- audit_clean: True
- best_trade: SNDK 57.4933% pnl=7744.54
- worst_trade: SMCI -27.8366% pnl=-7530.91
- trades_by_industry_top: {'Computers': 49, 'Semiconductors': 39, 'Telecommunications': 16, 'Software': 12, 'Internet': 12, 'Chemicals': 10, 'Oil&Gas': 8, 'Media': 7}

### edge hold20 15bps — detail
- final_equity: 197218.31
- days_in_market: 246/7169
- avg_exposure: 0.0329 max: 1.0
- audit_clean: True
- best_trade: INTC 108.0491% pnl=15316.82
- worst_trade: SMCI -39.9487% pnl=-8143.12
- trades_by_industry_top: {'Semiconductors': 27, 'Computers': 19, 'Airlines': 8, 'Telecommunications': 8, 'Software': 6, 'Internet': 4, 'Oil&Gas': 4, 'Oil&Gas Services': 4}

### mle_top10_only hold20 15bps — detail
- final_equity: 250853.72
- days_in_market: 246/7169
- avg_exposure: 0.0343 max: 0.9999
- audit_clean: True
- best_trade: SNDK 119.0148% pnl=17535.16
- worst_trade: MRNA -20.6151% pnl=-2061.51
- trades_by_industry_top: {'Computers': 29, 'Semiconductors': 21, 'Telecommunications': 10, 'Internet': 9, 'Software': 7, 'Healthcare-Products': 4, 'Electronics': 4, 'Biotechnology': 3}

## Klicove otazky

- porazi EDGE MLE-only po SPRAVNEM cash accountingu? viz tot_ret/sharpe.
- ma EDGE vyssi avg_trade/win_rate? viz tabulky.
- kolik EDGE ztraci nizsi exposure/mene obchody? porovnej days_in_market + n_trades + avg_exposure.

## Vyhrady (souhrn)

- skutecna denni equity: cash + MTM pozic. Cash ucet sledovan.
- sizing: 10% aktualni equity na pozici (dle equity_now).
- entry open[t+1], exit close[entry+H], konec dat -> partial.
- naklady: half round-trip na kazde strane (bps/2).
- Sharpe/DD orientacni, kratky sample 245 dni.
- survivorship 503 soucasnych; bez kapacity/likvidity/fillu.
