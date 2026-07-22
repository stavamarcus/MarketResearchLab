# MLE-BT-06 — Whole-Share Execution Reality

Sim: 2021-07-01..2026-07-02 (1256 dni), pandas 3.0.3
Engine: MLE-BT-04R run_causal (import) + local whole-share copy

**Validation gate: PASS** (anchor reprodukuje BT-04R: True, lokalni kopie verna: True, trade-ledger identicky: True)

**Audit:** min_cash napric behy = 0.193922 (>=0: True); gate trade-ledger identicky: True

## Edge vs capital — headline

| capital | frac CAGR% | whole CAGR% | ΔCAGR | whole cash_drag | whole days<10/10 | TOO_EXPENSIVE skips |
|---|---|---|---|---|---|---|
| 3,000 | 34.504 | 32.779 | -1.725 | 0.317 | 726 | 170 |
| 5,000 | 34.504 | 28.741 | -5.763 | 0.284 | 460 | 45 |
| 10,000 | 34.504 | 33.507 | -0.997 | 0.252 | 274 | 3 |
| 25,000 | 34.504 | 33.665 | -0.839 | 0.229 | 271 | 1 |
| 30,000 | 34.504 | 33.769 | -0.735 | 0.227 | 271 | 1 |
| 50,000 | 34.504 | 34.442 | -0.062 | 0.221 | 268 | 0 |
| 100,000 | 34.504 | 34.505 | 0.001 | 0.217 | 268 | 0 |
| 250,000 | 34.504 | 34.461 | -0.043 | 0.215 | 268 | 0 |

## Per-capital detail

### capital = 3,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 310.393 | -27.259 |
| cagr_pct | 34.504 | 32.779 | -1.725 |
| max_drawdown_pct | -32.7 | -30.087 | 2.613 |
| sharpe | 1.182 | 1.233 | 0.051 |
| trades | 990 | 972 | -18 |
| avg_exposure | 0.787 | 0.683 | -0.104 |
| cash_drag | 0.213 | 0.317 | 0.104 |
| deployment_ratio | 0.787 | 0.683 | -0.104 |
| avg_positions | 7.87 | 7.71 | -0.16 |
| days_10_of_10 | 988 | 530 | -458 |
| days_under_10 | 268 | 726 | 458 |
| skips (whole) | — | TOO_EXP 170 / INSUF 0 / DATA 0 | — |

### capital = 5,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 251.895 | -85.757 |
| cagr_pct | 34.504 | 28.741 | -5.763 |
| max_drawdown_pct | -32.7 | -33.922 | -1.222 |
| sharpe | 1.182 | 1.096 | -0.086 |
| trades | 990 | 987 | -3 |
| avg_exposure | 0.787 | 0.716 | -0.071 |
| cash_drag | 0.213 | 0.284 | 0.071 |
| deployment_ratio | 0.787 | 0.716 | -0.071 |
| avg_positions | 7.87 | 7.84 | -0.03 |
| days_10_of_10 | 988 | 796 | -192 |
| days_under_10 | 268 | 460 | 192 |
| skips (whole) | — | TOO_EXP 45 / INSUF 0 / DATA 0 | — |

### capital = 10,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 321.726 | -15.926 |
| cagr_pct | 34.504 | 33.507 | -0.997 |
| max_drawdown_pct | -32.7 | -31.127 | 1.573 |
| sharpe | 1.182 | 1.197 | 0.015 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.748 | -0.039 |
| cash_drag | 0.213 | 0.252 | 0.039 |
| deployment_ratio | 0.787 | 0.748 | -0.039 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 982 | -6 |
| days_under_10 | 268 | 274 | 6 |
| skips (whole) | — | TOO_EXP 3 / INSUF 0 / DATA 0 | — |

### capital = 25,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 324.223 | -13.429 |
| cagr_pct | 34.504 | 33.665 | -0.839 |
| max_drawdown_pct | -32.7 | -33.169 | -0.469 |
| sharpe | 1.182 | 1.175 | -0.007 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.771 | -0.016 |
| cash_drag | 0.213 | 0.229 | 0.016 |
| deployment_ratio | 0.787 | 0.771 | -0.016 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 985 | -3 |
| days_under_10 | 268 | 271 | 3 |
| skips (whole) | — | TOO_EXP 1 / INSUF 0 / DATA 0 | — |

### capital = 30,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 325.863 | -11.789 |
| cagr_pct | 34.504 | 33.769 | -0.735 |
| max_drawdown_pct | -32.7 | -33.433 | -0.733 |
| sharpe | 1.182 | 1.176 | -0.006 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.773 | -0.014 |
| cash_drag | 0.213 | 0.227 | 0.014 |
| deployment_ratio | 0.787 | 0.773 | -0.014 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 985 | -3 |
| days_under_10 | 268 | 271 | 3 |
| skips (whole) | — | TOO_EXP 1 / INSUF 0 / DATA 0 | — |

### capital = 50,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 336.639 | -1.013 |
| cagr_pct | 34.504 | 34.442 | -0.062 |
| max_drawdown_pct | -32.7 | -32.305 | 0.395 |
| sharpe | 1.182 | 1.188 | 0.006 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.779 | -0.008 |
| cash_drag | 0.213 | 0.221 | 0.008 |
| deployment_ratio | 0.787 | 0.779 | -0.008 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 988 | 0 |
| days_under_10 | 268 | 268 | 0 |
| skips (whole) | — | TOO_EXP 0 / INSUF 0 / DATA 0 | — |

### capital = 100,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 337.658 | 0.006 |
| cagr_pct | 34.504 | 34.505 | 0.001 |
| max_drawdown_pct | -32.7 | -32.489 | 0.211 |
| sharpe | 1.182 | 1.186 | 0.004 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.783 | -0.004 |
| cash_drag | 0.213 | 0.217 | 0.004 |
| deployment_ratio | 0.787 | 0.783 | -0.004 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 988 | 0 |
| days_under_10 | 268 | 268 | 0 |
| skips (whole) | — | TOO_EXP 0 / INSUF 0 / DATA 0 | — |

### capital = 250,000

| metric | fractional | whole_share | delta |
|---|---|---|---|
| total_return_pct | 337.652 | 336.952 | -0.7 |
| cagr_pct | 34.504 | 34.461 | -0.043 |
| max_drawdown_pct | -32.7 | -32.631 | 0.069 |
| sharpe | 1.182 | 1.183 | 0.001 |
| trades | 990 | 990 | 0 |
| avg_exposure | 0.787 | 0.785 | -0.002 |
| cash_drag | 0.213 | 0.215 | 0.002 |
| deployment_ratio | 0.787 | 0.785 | -0.002 |
| avg_positions | 7.87 | 7.87 | 0.0 |
| days_10_of_10 | 988 | 988 | 0 |
| days_under_10 | 268 | 268 | 0 |
| skips (whole) | — | TOO_EXP 0 / INSUF 0 / DATA 0 | — |

## Vyhrady

- BT-06 nemeni signal, regime ani DecisionResolver.
- fractional = bt04r.run_causal (import). whole_share = lokalni verna kopie, jedina zmena floor + skip taxonomie (Model A, bez recyklace, bez rank-11 substituce).
- cash_drag = 1 - avg_exposure; deployment = avg_exposure (denni MTM).
- Jedno in-sample okno, survivorship (current 503). Bodova hodnota neni dukaz.
