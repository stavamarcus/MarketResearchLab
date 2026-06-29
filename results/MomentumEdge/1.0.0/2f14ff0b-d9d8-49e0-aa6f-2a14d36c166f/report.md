# MomentumEdge — v1.0.0

**Run ID:** `2f14ff0b-d9d8-49e0-aa6f-2a14d36c166f`
**Datum spuštění:** 2026-06-29 09:26:55 UTC
**Datový rozsah:** 2024-08-01 → 2026-06-20
**Universum:** sp500_rank_calendar

## Hypotéza

Akcie S&P 500 v TOP decilu podle 20D price momentum vykazují vyšší median 10D forward return než akcie v BOTTOM decilu.

## Konfigurace

_(žádné parametry)_

**Poznámky:** Reference Experiment #1

## Metriky

| Metrika | Hodnota |
|---------|---------|
| n_periods | 442 |
| n_observations | 219554 |
| lookback_days | 20 |
| forward_days | 10 |
| n_deciles | 10 |
| top_decile_median_ret | 0.00812 |
| top_decile_mean_ret | 0.014567 |
| top_decile_win_rate | 0.5525 |
| top_decile_n | 22100 |
| bottom_decile_median_ret | 0.004583 |
| bottom_decile_mean_ret | 0.007007 |
| bottom_decile_win_rate | 0.5331 |
| bottom_decile_n | 22100 |
| top_minus_bottom_spread | 0.003537 |
| hypothesis_supported | False |

## Summary

Momentum Edge (20D → 10D forward), S&P 500

TOP decil median return:    0.81%
BOTTOM decil median return: 0.46%
Spread (TOP - BOTTOM):      0.35%

Hypotéza H-001: ✗ NOT SUPPORTED (spread < 0.5% threshold)

Pozorování: Momentum efekt přítomen (TOP > BOTTOM), ale pod prahem.
Možné vysvětlení: Krátké backtestové období (2024–2026), bez RISK_OFF filtru.
N pozorování: 219,554 | N period: 442 dní

## Reprodukovatelnost

**Result hash:** `73a7af1614ea026b`
