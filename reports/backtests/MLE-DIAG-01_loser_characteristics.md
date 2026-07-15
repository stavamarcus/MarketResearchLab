# MLE-DIAG-01 — Loser Characteristics (DIAGNOSTIC EDA)

## WARNING

IN-SAMPLE deskripce, NE filtr. Survivorship: losery=prezivsi klesajici akcie. Nominalni cena obvykle neni prima pricina rizika.

Varianta: regime200_hold10, trades: 1090
Sim: 2021-07-01..2026-07-02

## Losers vs Winners

| metrika | losers (bottom 20%) | winners (top 20%) |
|---|---|---|
| avg net return % | -11.19 | 17.606 |
| entry price mean | 162.77 | 148.47 |
| entry price median | 90.78 | 87.09 |
| volatilita 20D mean % | 4.077 | 4.383 |
| momentum rank mean | 5.19 | 5.08 |
| historie dni mean | 4326.0 | 4061.0 |
| historie dni median | 4934.0 | 4151.0 |

- losers top sectors: {'Technology': 65, 'Communications': 37, 'Consumer, Cyclical': 33, 'Energy': 21, 'Consumer, Non-cyclical': 20}
- winners top sectors: {'Technology': 75, 'Communications': 37, 'Consumer, Cyclical': 26, 'Energy': 20, 'Consumer, Non-cyclical': 18}
- losers top industries: {'Computers': 31, 'Semiconductors': 23, 'Internet': 18, 'Oil&Gas': 17, 'Retail': 11}
- winners top industries: {'Computers': 37, 'Internet': 26, 'Semiconductors': 26, 'Oil&Gas': 14, 'Software': 12}

### 10 nejvetsich loseru (ticker, net%, entry_price, vol20d, hist_days)

- ('SMCI', np.float64(-38.6878), 62.94, 6.097, 4380)
- ('PLTR', np.float64(-29.3512), 117.9, 6.012, 1099)
- ('APP', np.float64(-28.8719), 473.56, 6.104, 964)
- ('COIN', np.float64(-26.7218), 97.25, 9.817, 335)
- ('HOOD', np.float64(-26.041), 63.3, 4.297, 891)
- ('CVNA', np.float64(-25.8763), 2.03, 6.698, 1498)
- ('FANG', np.float64(-25.2452), 97.76, 2.853, 2193)
- ('HOOD', np.float64(-25.013), 15.06, 5.46, 133)
- ('AMD', np.float64(-24.9673), 184.07, 2.386, 6673)
- ('TPL', np.float64(-24.2933), 534.57, 4.583, 6773)

## Korelace s net_ret

| feature | Pearson | Spearman | n |
|---|---|---|---|
| entry_price | -0.0299 | 0.0207 | 1090 |
| vol_20d_pct | 0.1037 | 0.0503 | 1090 |
| mom_rank | -0.0398 | -0.0001 | 1090 |
| hist_days | -0.0875 | -0.0326 | 1090 |

- Pearson/Spearman blizko 0 = zadny vztah.
- zaporny = vyssi hodnota -> nizsi return.
- kladny = vyssi hodnota -> vyssi return.

## Cenove kvintily (test hypotezy 'mensi cena = loser')

| kvintil | cenove pasmo | avg net% | win_rate | n |
|---|---|---|---|---|
| Q1 | [1.48, 41.19] | 2.734 | 0.5 | 218 |
| Q2 | [41.21, 75.9] | 0.939 | 0.491 | 218 |
| Q3 | [76.48, 130.35] | 1.128 | 0.509 | 218 |
| Q4 | [130.95, 232.26] | 2.092 | 0.564 | 218 |
| Q5 | [232.45, 5705.14] | 1.325 | 0.578 | 218 |

- Q1 = nejlevnejsi akcie, Q5 = nejdrazsi.
- pokud Q1 avg_ret << Q5 -> nizka cena koreluje s horsim vysledkem.
- pokud podobne -> nominalni cena NENI faktor (mytus).

## Interpretace

- pokud losery maji vyssi VOLATILITU (ne nizsi cenu) -> skutecny
  faktor je volatilita, ne cena.
- pokud losery maji kratsi HISTORII -> recent IPO riziko (SNDK-like).
- pokud zadny rozdil -> losery nemaji spolecny viditelny rys
  (jsou to jen nahodne propady momentum akcii).

## Vyhrady

- **IN-SAMPLE deskripce, NE hotovy filtr. Overfit riziko pri
  stavbe filtru z techto nalezu.**
- SURVIVORSHIP: losery = prezivsi klesajici akcie.
- nominalni cena obvykle neni prima pricina (mytus); vol/velikost je.
- diagnostic only.
