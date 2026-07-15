# CAP-00 Market Cap Source Review

**Fáze:** MRL-CAP-00 (design only). Cíl: PIT-safe `market_cap_asof_candidate_date`
pro bucketing MLE × IRC candidate-days.

---

## 1. Zmapované zdroje

| Zdroj | Popis | PIT-safety | Stav |
|---|---|---|---|
| **A. computed** | `mdsm_close(candidate_date) × sharesbas(PIT)` | price: přesně PIT; shares: PIT k datekey (staleness ≤ ~1Q) | **DOPORUČENO** |
| B. Sharadar `marketcap` | SF1 pole, hodnota k datekey | PIT k datekey, ale OBĚ komponenty (price i shares) stale ≤ ~1Q; navíc price-derived → globálně zakázané (policy gate §2), alias řádky ho nemají vůbec | fallback pouze s explicitní výjimkou architekta |
| C. archived market cap | hledáno napříč projekty (MDSM cache, universe CSV, MLE/IMS/IRC archivy) | — | **NEEXISTUJE** (ověřeno grep) |
| D. current market cap | dnešní kapitalizace zpětně | **ZAKÁZÁNO** | viz §7 |

## 2. Doporučený zdroj: A (computed)

```text
market_cap_asof_candidate_date =
    mdsm_close(conid, candidate_date)            [MDSM cache, canonical price source]
  × sharesbas(conid, PIT datekey <= candidate_date)  [SF1 přes adapter]
```

**Klíčový nález (ověřeno z build_snapshot.py):** `process_raw` sloupce
neořezává a API fetch nemá column restrikci → processed parquet snapshotu
`sf1art_20260704_005521` s vysokou pravděpodobností JIŽ OBSAHUJE
`sharesbas` (basic shares outstanding), `shareswa`, `sharefactor`.
Důsledek: **žádný nový API fetch, žádný rebuild snapshotu.**

Ověření (read-only, adapter API, 1 příkaz — první krok CAP-01):

```python
# přes StoreHandle.dataframe — žádné přímé čtení parquet mimo API
cols = SF1Store(cfg).load("sf1art_20260704_005521").dataframe.columns
# očekávání: 'sharesbas' in cols
```

Pokud `sharesbas` v snapshotu NENÍ → **BLOCKER**: append-only rozšíření
build fetch + nový snapshot (samostatné schválení, API mimo CAP fáze).
Neimprovizovat.

## 3. Zpřístupnění shares přes provider

`schemas.FUNDAMENTAL_FIELDS` + `sharesbas` (příp. `sharefactor`) —
**append-only rozšíření je kontraktem výslovně povoleno** (schemas.py
docstring: „Rozšíření fundamentals = append-only doplněk kontraktu").
`sf1_provider.py`, `sf1_store.py`, `coverage.py` se NEMĚNÍ (fields filtr
čte schemas). Wrapper whitelist akceptuje automaticky. Shares NENÍ
price-derived pole (filing fakt). Změna schemas.py vyžaduje schválení
architekta (soubor není na neměnit listu, ale je součástí adapter repa
→ post-v1.0 append-only extension, analogie pyproject rozhodnutí).

## 4. Price source / shares field / missing handling

```text
price:  MDSM close (adjusted), candidate_date přesně; chybí-li den
        v cache → MARKET_CAP_PRICE_MISSING (explicitní kategorie)
shares: sharesbas z PIT snapshotu (datekey <= candidate_date);
        NaN/<=0/řádek EXCLUDED → MARKET_CAP_SHARES_MISSING
missing market cap celkem → bucket = UNBUCKETED + reason_code;
        ŽÁDNÝ silent drop (1:1 invarianta zachována)
```

## 5. Splits / share changes — HLAVNÍ APPROXIMATION RISK

MDSM close je split-adjusted; `sharesbas` je as-filed k datekey.
Split mezi datekey a candidate_date ⇒ adjusted_price × unadjusted_shares
= chybná kapitalizace (typicky násobek/zlomek 2×–10×).

Mitigace (CAP-01, povinné):
```text
1. sanity anchor: computed_mc(datekey) = mdsm_close(datekey) × sharesbas
   vs. Sharadar marketcap(datekey); ratio mimo toleranční pásmo
   (návrh 0.5–2.0) → MARKET_CAP_SUSPECT, řádek UNBUCKETED
   (marketcap zde slouží POUZE jako validační kotva, ne jako feature —
   vyžaduje potvrzení architekta, že to není porušení price-derived banu)
2. sharefactor pole (pokud v snapshotu) jako korekční vstup — rozhodnutí
   architekta po ověření dostupnosti
3. boundary sensitivity report: počet jmen do ±10 % od bucket hranice
```

## 6. Reproducibility

```text
snapshot pinned (sf1art_20260704_005521) + data_hash
MDSM price file hashes (stávající file_hash mechanismus)
candidate_days.csv sha256 (FUND-03 manifest)
bucket thresholdy v manifestu runu; forward_returns_used=false (CAP-01)
```

## 7. Proč nikdy current market cap zpětně

Dnešní kapitalizace = f(historický výnos). Bucketing podle ní zpětně
vkládá měřenou veličinu do klasifikátoru (look-ahead + survivorship):
dnešní mega-cap je zčásti mega-cap PROTOŽE měl vysoké forward returns
v testovaném okně. Výsledek by byl mechanicky zkreslený. ZAKÁZÁNO.
