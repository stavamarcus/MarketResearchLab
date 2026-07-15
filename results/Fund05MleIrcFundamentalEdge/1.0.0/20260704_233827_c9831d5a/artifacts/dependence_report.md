# FUND-05 Dependence Report

- nominal_N: 1144
- unique_conids: 151
- unique_dates: 244
- avg_candidate_days_per_conid: 7.58
- per_date_min: 1
- per_date_median: 5.0
- per_date_max: 10
- window_overlap_note: okna [5, 10, 20] kalendářních dní se překrývají u conidů s opakovanými candidate-days; efektivní N < nominální N

## Top 10 nejopakovanějších conidů

| conid | ticker | count |
|---|---|---|
| 270639 | INTC | 54 |
| 9939 | MU | 51 |
| 4391 | AMD | 44 |
| 491932113 | STX | 31 |
| 201113895 | LITE | 28 |
| 13681 | WDC | 26 |
| 12729 | TER | 24 |
| 732440574 | LRCX | 23 |
| 474515500 | APA | 22 |
| 72529783 | GNRC | 21 |

## Non-overlap subsample (median/hit 20D)

| variant | n | median_20d | hit_20d |
|---|---|---|---|
| A | 266 | 1.9699 | 0.6203 |
| B | 221 | 1.739 | 0.6063 |
| C | 201 | 2.0953 | 0.6169 |
| D | 148 | 1.8433 | 0.6284 |
| E | 168 | 1.7906 | 0.625 |
| F | 174 | 1.8433 | 0.6149 |

Efektivní N < nominální N (opakované conidy, překryv oken, regime clustering). Závěry pouze: statistically suggestive / not conclusive / inconclusive.
