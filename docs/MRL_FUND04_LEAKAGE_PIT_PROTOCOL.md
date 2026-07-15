# FUND-04 Leakage & PIT Protocol (závazný pro FUND-05)

1. **PIT tvrdé pravidlo:** `sf1_datekey <= candidate_date` — výhradně
   adapter lookup (zamčený). Žádná výjimka.
2. **Žádné filed-as-of domýšlení mimo provider** — MRL nesmí posouvat,
   interpolovat ani "opravovat" datekey.
3. **Žádné pozdější fundamentals** — restatementy s pozdějším datekey
   nejsou pro dřívější candidate_date viditelné (garantuje sort/take-last
   logika provideru); MRL je nesmí obcházet čtením snapshotu napřímo.
4. **Žádné fieldy odvozené z budoucí ceny** — price-derived pole zakázána
   globálně; forward returns vznikají až v experiment layer z MDSM cen
   a NIKDY nevstupují do feature konstrukce.
5. **Return sloupce se nesmí použít pro feature selection** — whitelist
   a prahy jsou pre-registrované v FUND-04, před jakýmkoli výpočtem
   výnosů. Post-hoc úprava prahů podle výsledků = STOP.
6. **snapshot_id pinovaný** — `sf1art_20260704_005521` pro první run;
   `latest` odmítá wrapper i factory.
7. **source_hashes v reportu** — sf1_data_hash, extraction manifest hashe
   (MLE/IRC/universe/candidate_days.csv), price file hashe (stávající
   ContextBuilder mechanismus).
8. **Staleness reporting + buckety:**
   ```text
   0–90d:   normal
   91–180d: allowed, flagged (per-záznam staleness_days v tabulce)
   >180d:   allowed pouze jako sensitivity bucket; defaultně ne hard fail
            (FUND-03: bucket prázdný — 0 záznamů)
   ```
9. **Alias rows označeny** — `is_alias` per záznam; alias_count/pct
   v reportu; nevylučují se.
10. **Missing values ⇒ žádný tichý drop** — request-level: EXCLUDED +
    reason_code (wrapper 1:1 invarianta); field-level NaN:
    `field_null_excluded` počítadlo per varianta (whitelist null policy).

## revenue_yoy — specifický PIT postup

Dva nezávislé PIT lookupy: `get_snapshot(conid, candidate_date)` a
`get_snapshot(conid, candidate_date − 365d)`. Oba splňují bod 1
(druhý je PIT k staršímu datu, tedy přísnější). Zakázáno: srovnávat
snapshoty dvou RŮZNÝCH candidate_dates z běhu jako "growth" mimo tento
definovaný postup. Coverage druhého lookupu se počítá do coverage
varianty C (starší datum může legitimně vrátit NO_SF1_ASOF_DATE).
