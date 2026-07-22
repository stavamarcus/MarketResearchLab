# MLE-BT-06 — Diagnostic Addendum

Minimalni provozni kapital (TOO_EXPENSIVE <= 5 a ΔCAGR >= -1.0): **10000**

## Rocni whole-share CAGR/return by capital (%)

| rok | 3k | 5k | 10k | 30k | 50k |
|---|---|---|---|---|---|
| 2021 | 14.487 | 9.493 | 14.525 | 14.638 | 15.915 |
| 2022 | -21.435 | -26.657 | -24.075 | -25.575 | -24.921 |
| 2023 | 78.826 | 57.986 | 70.232 | 70.964 | 71.279 |
| 2024 | 44.756 | 60.731 | 37.716 | 39.178 | 39.304 |
| 2025 | 21.74 | 25.616 | 37.696 | 38.572 | 39.021 |
| 2026 | 44.783 | 37.375 | 50.245 | 51.381 | 51.258 |

## Rocni exposure / cash_drag (whole_share)

### 3,000
| rok | return% | avg_exposure | cash_drag | dni |
|---|---|---|---|---|
| 2021 | 14.487 | 0.7524 | 0.2476 | 128 |
| 2022 | -21.435 | 0.3363 | 0.6637 | 251 |
| 2023 | 78.826 | 0.7565 | 0.2435 | 250 |
| 2024 | 44.756 | 0.8118 | 0.1882 | 252 |
| 2025 | 21.74 | 0.7343 | 0.2657 | 250 |
| 2026 | 44.783 | 0.8038 | 0.1962 | 125 |

### 5,000
| rok | return% | avg_exposure | cash_drag | dni |
|---|---|---|---|---|
| 2021 | 9.493 | 0.8088 | 0.1912 | 128 |
| 2022 | -26.657 | 0.3741 | 0.6259 | 251 |
| 2023 | 57.986 | 0.807 | 0.193 | 250 |
| 2024 | 60.731 | 0.833 | 0.167 | 252 |
| 2025 | 25.616 | 0.7516 | 0.2484 | 250 |
| 2026 | 37.375 | 0.8199 | 0.1801 | 125 |

### 10,000
| rok | return% | avg_exposure | cash_drag | dni |
|---|---|---|---|---|
| 2021 | 14.525 | 0.8384 | 0.1616 | 128 |
| 2022 | -24.075 | 0.3917 | 0.6083 | 251 |
| 2023 | 70.232 | 0.8499 | 0.1501 | 250 |
| 2024 | 37.716 | 0.8701 | 0.1299 | 252 |
| 2025 | 37.696 | 0.7799 | 0.2201 | 250 |
| 2026 | 50.245 | 0.8562 | 0.1438 | 125 |

### 30,000
| rok | return% | avg_exposure | cash_drag | dni |
|---|---|---|---|---|
| 2021 | 14.638 | 0.8802 | 0.1198 | 128 |
| 2022 | -25.575 | 0.4087 | 0.5913 | 251 |
| 2023 | 70.964 | 0.8803 | 0.1197 | 250 |
| 2024 | 39.178 | 0.894 | 0.106 | 252 |
| 2025 | 38.572 | 0.8013 | 0.1987 | 250 |
| 2026 | 51.381 | 0.8787 | 0.1213 | 125 |

### 50,000
| rok | return% | avg_exposure | cash_drag | dni |
|---|---|---|---|---|
| 2021 | 15.915 | 0.8916 | 0.1084 | 128 |
| 2022 | -24.921 | 0.4122 | 0.5878 | 251 |
| 2023 | 71.279 | 0.8864 | 0.1136 | 250 |
| 2024 | 39.304 | 0.9014 | 0.0986 | 252 |
| 2025 | 39.021 | 0.806 | 0.194 | 250 |
| 2026 | 51.258 | 0.8816 | 0.1184 | 125 |

## Nejcasteji skipnute tickery (TOO_EXPENSIVE_FOR_TARGET)

- **3,000**: FICO(22), LULU(19), LLY(14), MRNA(12), TSLA(12), MPWR(11), SNDK(10), EPAM(8), URI(8), WST(7), FIX(6), ALGN(5), INTU(5), MTD(4), SBAC(3)
- **5,000**: FICO(16), INTU(4), MTD(4), REGN(3), EPAM(3), LLY(3), MPWR(3), SNDK(3), POOL(1), NVR(1), DE(1), MSCI(1), UNH(1), URI(1)
- **10,000**: NVR(2), AZO(1)
- **25,000**: NVR(1)
- **30,000**: NVR(1)

## 5k anomalie — atribuce minulych obchodu (forgone pnl)

Obchody z fractional baseline, ktere whole_share vubec nevzal:

| capital | #missed | forgone_pnl | top missed (ticker/entry/pnl) |
|---|---|---|---|
| 3,000 | 456 | 3339.17 | INTC 2026-04-17 (508.47); AMD 2026-05-19 (425.75); SNDK 2026-06-04 (391.59); APA 2026-03-13 (363.8); LITE 2026-02-10 (340.37) |
| 5,000 | 170 | 1595.6 | GLW 2026-02-10 (431.75); MU 2025-12-22 (333.09); HOOD 2025-01-30 (229.69); TPL 2024-11-07 (210.37); TPL 2024-10-23 (204.8) |
| 10,000 | 6 | -7.6 | OXY 2022-01-10 (122.37); NVR 2021-12-08 (20.3); JBL 2021-12-23 (4.64); AZO 2021-12-08 (4.26); CIEN 2021-12-23 (-44.8) |

## Poznamka

- forgone_pnl je prvni-radova atribuce (pnl z fractional behu pro obchody, ktere whole_share neotevrel); nezahrnuje under-sizing zachycenych obchodu. Slouzi k vysvetleni, proc konkretni kapital vysel hur (path-dependence konkretnich jmen).
- Jedno in-sample okno, survivorship (current 503). Bodova hodnota neni dukaz.
