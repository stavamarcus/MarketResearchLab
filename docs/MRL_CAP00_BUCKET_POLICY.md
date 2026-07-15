# CAP-00 Market Cap Bucket Policy

**Fixní, pre-registrované prahy. Po výsledku se NEMĚNÍ.**

| Bucket | Rozsah |
|---|---|
| Mega | ≥ 200B |
| Large-high | 50B – 200B |
| Large-low | 10B – 50B |
| Mid | 2B – 10B |
| Small | < 2B |
| UNBUCKETED | missing market cap (explicitní reason_code) |

Hraniční konvence: dolní mez inclusive, horní exclusive
(`10B <= mc < 50B` → Large-low).

## Pravidla

```text
žádné pooled percentily, žádné per-day terciles
žádné in-sample optimalizované prahy
bucket VÝHRADNĚ z market_cap_asof_candidate_date
missing market cap = explicitní reason_code + UNBUCKETED, žádný silent drop
thresholdy se po výsledku nemění; prázdný bucket se reportuje jako prázdný
(žádné re-binning)
```

## Vhodnost pro S&P 500 universe — POCTIVÉ UPOZORNĚNÍ

S&P 500 má vstupní market-cap floor v desítkách miliard (drženy jen
klesnuvší členy pod ním). Očekávání pro 151 leader conidů:

```text
Small (<2B):  N ≈ 0 — bucket téměř jistě prázdný
Mid (2–10B):  nízké jednotky jmen → téměř jistě N < 30 → per-bucket
              INCONCLUSIVE by design v CAP-02
těžiště:      Large-low / Large-high / Mega
```

Rozhodnutí: prahy PONECHAT (standardní tržní definice, srovnatelnost
s budoucími universe rozšířeními); prázdnost Small/Mid je sama o sobě
odpověď na otázku 1 zadání („které buckety tvoří leaders"), ne důvod
k překreslení hranic. Alternativa (jemnější dělení Mega/Large) se
zavrhuje — byla by in-sample volba podle očekávané distribuce.
Skutečnou distribuci změří CAP-01; případná revize prahů by musela
proběhnout PŘED CAP-02 a jako architektonické rozhodnutí.
