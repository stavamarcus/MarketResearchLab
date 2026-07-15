# MRL ↔ Sharadar Fundamental Provider — integrační kontrakt (návrh v0.1)

**Fáze:** MRL-FUND-00 (design only, ke schválení architektem)
**Strany:** MarketResearchLab (konzument) ↔ sharadar_mdsm_adapter v1.0 (read-safe dependency)

---

## 1. Principy

1. Adapter je uzavřená dependency — MRL používá výhradně jeho veřejné API
   (`load_config`, `SF1Store.load`, `SF1Provider.get_snapshot`, `CoverageAccumulator`).
   Žádné čtení parquet/manifestů mimo toto API.
2. PIT garance nese adapter (zamčené pravidlo `datekey <= candidate_date`).
   MRL ji nesmí obcházet ani "vylepšovat".
3. **Missing fundamentals nejsou tichý drop.** Každý request má výstupní řádek;
   každý fail má explicitní `reason_code`.
4. Read-only, žádné API volání, žádný refresh během experimentů
   (analogie MDSM CACHE_ONLY; adapter read path API mít nemůže — vynuceno jeho kontraktními testy).
5. Snapshot pinning: experiment deklaruje konkrétní `snapshot_id` (ne `latest`);
   `snapshot_id` + manifest `data_hash` + `contract_versions` jdou do run metadata
   (`source_hashes`) pro reprodukovatelnost.

## 2. Input schema (batch)

`pd.DataFrame`, jeden řádek = jeden fundamental request:

| sloupec | typ | povinné | poznámka |
|---|---|---|---|
| conid | int | ano | IBKR conid (identity resolve dělá adapter) |
| candidate_date | date | ano | PIT referenční datum (signal_date experimentu) |
| ticker | str | ne | pouze informativní/audit; nikdy se nepoužívá k resolve |
| experiment_id | str | ne | propaguje se do coverage reportu |
| source_signal_label | str | ne | např. "MLE_TOP10×IRC_TOP10"; audit segmentace coverage |

Pravidla: duplicitní (conid, candidate_date) řádky jsou povolené a každý = samostatný
provider request (v0.1 bez memoizace; viz otevřené otázky).

## 3. Output schema (batch)

`pd.DataFrame`, **1:1 s inputem** (stejný počet řádků, stejné pořadí):

| sloupec | typ | poznámka |
|---|---|---|
| conid | int | echo inputu |
| candidate_date | date | echo inputu |
| sf1_datekey | date/NaT | datekey vybraného SF1 řádku; NaT při EXCLUDED |
| staleness_days | int/NaN | candidate_date − sf1_datekey |
| staleness_flag | str/None | "STALE_SNAPSHOT" při >180d (warning-only, řádek zůstává OK) |
| identity_tier | str/None | z IdentityRecord |
| is_alias | bool/None | alias_flag != None |
| coverage_status | str | "OK" \| "EXCLUDED" |
| reason_code | str/None | None při OK; jinak kód dle §4 |
| revenue, netinc, eps, fcf, roe, grossmargin, netmargin, debt, de, assets, equity | float/NaN | FUNDAMENTAL_FIELDS adapteru; NaN při EXCLUDED |

Price-derived pole (`marketcap, pe, ps, pb`): **v0.1 v MRL integraci zakázána**
(MDSM/IBKR je canonical price source; alias konzistence; eliminace price-leakage šedé zóny).
Znovuotevření možné samostatným rozhodnutím architekta.

## 4. Reason codes

Kompatibilní 1:1 s adapter coverage vrstvou (`COVERAGE_REASON_CODES`):

```text
IDENTITY_MISSING            conid není v resolved identity mapě
IDENTITY_AMBIGUOUS          duplicitní conid (defenzivní)
IDENTITY_TIER_NOT_ALLOWED   tier mimo INCLUDE policy / config subset
NO_SF1_ROWS                 permaticker bez SF1 ART řádků
NO_SF1_ASOF_DATE            žádný datekey <= candidate_date
ALIAS_PRICE_FIELD_FORBIDDEN nemělo by v MRL nastat (price pole zakázána §3); pokud nastane → bug wrapperu
CACHE_MISSING               snapshot/manifest chybí (setup-level fail celého runu)
SCHEMA_MISMATCH             schema/hash mismatch (setup-level fail celého runu)
UNKNOWN_ERROR               ne-SharadarProviderError výjimka (coverage-interní kategorie)
```

Sémantika úrovní:
- **Request-level** (IDENTITY_*, NO_SF1_*): řádek → EXCLUDED, run pokračuje.
- **Setup-level** (CACHE_MISSING, SCHEMA_MISMATCH při store load): celý běh
  experimentu FAILED ve `validate()` — nedává smysl pokračovat nad nevalidním snapshotem.

## 5. Coverage accounting (povinné, adapter kontrakt §11)

Každý experiment run s fundamentals produkuje coverage report přes adapter
`CoverageAccumulator` (žádná paralelní implementace v MRL):

- `record_success` / `record_failure` per provider request
- výstup: `coverage_<run_id>.md` do run adresáře experimentu
  (`results/{name}/{version}/{run_folder}/artifacts/`)
- coverage dict navíc do `ExperimentResult.tables["fundamental_coverage"]`
- **Bez coverage reportu je fundamentální MRL výsledek NEVALIDNÍ** (adapter kontrakt §11).

Minimální metriky (názvy = adapter): requested_candidate_days, returned_snapshots,
identity_excluded, missing_sf1, no_asof_date, stale_warnings, alias_count,
coverage_pct, excluded_candidate_days, reason_code_counts, snapshot_id, contract_versions.

## 6. Exclusion policy

- EXCLUDED řádky zůstávají v output DataFrame (auditovatelné), do statistik
  edge testu vstupují pouze OK řádky.
- Experiment MUSÍ reportovat coverage_pct a reason_code distribuci v report.md.
- Prahové hodnoty coverage (kdy je vzorek nepoužitelný) definuje
  MRL_FUNDAMENTAL_EDGE_TEST_GATE.md, ne tento kontrakt.

## 7. Verzování

- Tento kontrakt: `mrl_fundamental_integration v0.1` (DRAFT).
- Vázán na: `identity_contract v1.0`, `fundamental_provider_contract v1.0`, adapter `1.0.0`.
- Změna adapter kontraktů ⇒ povinná revize tohoto dokumentu.

## 8. Otevřené otázky (k rozhodnutí architekta před FUND-01)

1. Memoizace duplicitních (conid, candidate_date) requestů — v0.1 ne; potvrdit.
2. Price-derived pole trvale zakázat, nebo povolit non-alias s `price_derived=True` flagem?
3. Staleness: pass-through warning-only (v0.1), nebo hard-exclude >180d už na wrapper úrovni?
4. Feature whitelist pro první edge test (podmnožina 11 fundamentals vs. všechna).
