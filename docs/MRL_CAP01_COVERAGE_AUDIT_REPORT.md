# CAP-01 Market Cap Coverage Audit Report

**Status: COMPLETED (CAP-01B corrected run)** — run_id
`cap01_market_cap_coverage_20260705_050531_sf1art_20260704_005521`.

> CAP-01 není performance test — žádné forward returns, žádná
> profitabilita. Měří dostupnost a distribuci market cap.

Historie: původní CAP-01 run skončil STOP (coverage 56,91 %) kvůli
falešným MARKET_CAP_SUSPECT. CAP-01A diagnóza (ANCHOR_DATE_MISMATCH,
anchor_adjusted ≈1 v 96,3 %) identifikovala příčinu: vendor marketcap
je vztažen k sf1_datekey, ne candidate_date. CAP-01B opravil sanity
anchor na date-konzistentní srovnání.

## Parametry (LOCKED)

```text
market_cap_asof (bucket source) = close(candidate_date) × sharesbas(PIT)
sanity anchor (CAP-01B)         = close(sf1_datekey) × sharesbas vs vendor
tolerance = 25 % | boundary band ±10 % | anchor band [0.5, 2.0]
snapshot: sf1art_20260704_005521 (pinned, data_hash verified)
```

## 1. Field gate

```text
sharesbas: ANO | sharefactor: ANO | marketcap: ANO — GATE: OK
```

## 2. Coverage

```text
candidate-days: 1144 | unique conids: 151 | 2025-07-09 → 2026-06-27
MARKET_CAP_OK: 1123 | coverage_pct: 98.16
```

## 3. Bucket distribution

| bucket | candidate_days | unique_conids | unique_dates |
|---|---|---|---|
| Mega | 263 | 32 | 129 |
| Large-high | 355 | 64 | 189 |
| Large-low | 487 | 77 | 215 |
| Mid | 18 | 7 | 16 |
| Small | 0 | 0 | 0 |
| UNBUCKETED | 21 | 5 | 19 |

Small prázdný, Mid řídký (N=18) — konzistentní s CAP-00 predikcí pro
S&P 500 leaders. Těžiště: Large-low > Large-high > Mega.

## 4. Reason code distribution

```text
MARKET_CAP_OK: 1123 | PRICE_MISSING: 3 | SHARES_MISSING: 0
SUSPECT: 18 | INVALID: 0 | UNKNOWN_ERROR: 0
```

## 5. Sanity anchor + boundary sensitivity

```text
relative_diff_pct (date-konzistentní): median=0.00 p95=0.00 max=900.00
median(datekey_computed/vendor) ratio: 1.0 (v pásmu [0.5, 2.0])
boundary sensitivity (±10 % od hranice): 145 OK řádků
```

median=p95=0.00 → ~98 % řádků má datekey_computed EXAKTNĚ rovný vendor
marketcap. Potvrzuje, že Sharadar marketcap = close(datekey) × sharesbas.
Rozdělení diff je bimodální: ~1123 řádků ≈0, 18 řádků extrémní (max 900 %).

## 6. Zbývajících 18 SUSPECT

Netriviální zbytek nevysvětlený cenovým pohybem. Příčina jednotlivých
řádků NENÍ ze summary určitelná (chybí per-row rozbor). Hypotézy
(neověřené): share-count change mezi datekey a filing (sekundární
nabídka/buyback), vendor marketcap NaN/0, corner case lookupu.
Top UNBUCKETED conidy (CRWD 10×, KLAC 8×) jsou reálné large-cap →
suspect, ne chybějící data. Nejsou blokující (coverage 98,16 %).

## 7. RESULT: PASS

```text
coverage 98.16 % >= 95 %
UNKNOWN_ERROR = 0
median anchor ratio v pásmu [0.5, 2.0]
žádný silent drop (1:1 zachováno)
```

## 8. Doporučení

READY for CAP-02. Výhrady:
- Mid (N=18) a Small (N=0) budou v CAP-02 pravděpodobně INCONCLUSIVE
  (N < 30). Použitelná diferenciace jen mezi Mega/Large-high/Large-low.
- CAP-01 PASS neznamená prediktivní hodnotu bucketů — to je předmět CAP-02.

## 9. Poznámka

Forward returns nepoužity (manifest forward_returns_used=false),
current market cap nepoužit (current_market_cap_used=false). Výsledek
je datový audit, ne výpověď o profitabilitě.

## 10. Known issue — vendor-anchor anomaly (CAP-01B, ACCEPTED)

18 candidate-days (1.57 %) je UNBUCKETED kvůli anomálii vendor
marketcap anchoru, koncentrované do 2 conidů:

```text
CRWD (370757467): 9 řádků, vendor faktor ~4× pod computed
KLAC (270957):    9 řádků, vendor faktor ~10× pod computed
relative_diff_pct konstantní (300 % / 900 %) napříč řádky conidu
→ není cenový drift ani staleness; vendor marketcap pole je vadné
```

Computed market cap (candidate close × sharesbas) je u obou plausibilní
a řádově správný (CRWD ~500-670 mld, KLAC ~1,2-2,2 bil). Řádky ponechány
UNBUCKETED jako konzervativní exkluze — bez ad-hoc override anchoru,
bez změny tolerance, bez změny bucket thresholdů.

Dopad: 18/1144 = 1.57 %; CAP-01B zůstává PASS. Případné standardizované
pravidlo pro vendor-anchor anomálie je mimo scope CAP-01/CAP-02.
