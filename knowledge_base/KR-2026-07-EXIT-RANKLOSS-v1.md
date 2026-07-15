# KR-2026-07-EXIT-RANKLOSS-v1

**Class:** exit-validation (signal-native / rank-based)
**Research Project:** RP-0012-LEADERSHIP-LOSS-EXIT
**Experiment:** LeadershipLossEdge_v1
**Status:** VALIDATED (negative result — signifikantní OPAČNÝ směr)

```yaml
kr_id:          KR-2026-07-EXIT-RANKLOSS-v1
confidence:     HIGH (v rámci běhového období)
evidence_level: B+
run_id:         008f4f12-ef5d-4ece-9c90-1ea5e28ef82c
result_hash:    2ad1d862a8d9f4bf6906
archive:        results/LeadershipLossEdge/1.0.0/20260702_071345_008f4f12/
period:         2025-07-09 → 2026-06-29
universe:       MLE TOP10 × IRC TOP10 (lookback 20D)
created:        2026-07-02
supersedes:     null
```

> KR = current best knowledge, not truth.

---

## Hypotéza (pre-registrováno, zamčeno 2026-07-02, PM approval)

- **H0:** RANK_50 exit nemění mean return uvnitř fixního 20D okna proti fixed 20D hold.
- **H1a:** RANK_50 exit (MLE_Rank_10d > 50, fill next open) zvyšuje mean return.

```
entry close(D) | okno fixní D→D+20 | rank as-of close(k) | fill open(k+1)
rank série = MLE_Rank_10d (táž jako selekce) | cash 0 % po exitu
missing rank = CENSORED (bez imputace) | clustered bootstrap B=10000 seed=42
PASS ⇔ 95% CI celé > 0 | RANK_25/100 sensitivity | žádný price warmup
```

## Výsledek (autoritativní běh 2026-07-02)

```
N = 1044 candidate-days | 147 tickerů | censored missing rank 0 (0.00 %)
H1a: paired diff -4.353pp  CI[-6.32, -2.256]  → NOT SUPPORTED
     CI celé POD nulou → exit ničí ~60 % baseline výnosu.
baseline TIME_20 mean: 7.233 %

Sensitivity (monotónní):
  RANK_25 : -4.939pp | early 98.95 % | hold 6.94d
  RANK_50 : -4.353pp | early 98.08 % | hold 8.23d
  RANK_100: -3.494pp | early 93.97 % | hold 9.85d

Leadership survival TOP50 (deskriptivní, preregistrovaná statistika):
  5d 61.49 % | 10d 17.72 % | 15d 5.27 % | 20d 1.63 %
  loss v okně 98.37 % | median time-to-loss 7.0d
NEZÁVISLE REPLIKOVÁNO nad surovým rank_matrix_archive.csv
(bez IRC filtru, N=2290): 58.2/15.5/4.9/2.0 %, median 6d — shoda.
```

## Mechanismus (diagnosticky doložený)

1. **Rank churn je strukturální, ne informační.** rank_10d = rank 10D
   relativního výnosu; po vyrolování hnacího pohybu z lookbacku rank padá
   konstrukčně (median t-to-loss 6–7d ≈ ½ lookbacku), cena pokračuje.
   Ukázka: AES rank 1→96 za jeden den bez cenového kolapsu.
2. **Trajektorie po breach (diagnostika, exploratorní):** 84.7 % breachů
   jde až za rank 250 (bucket „oscilace 51–100" jen 3.5 %) — hloubka
   propadu nerozlišuje oscilaci vs ztrátu leadershipu, rozlišuje délku
   konsolidace. Post-breach return kladný i v bucketu >250 (+2.9 % mean).
3. **IRC vrstva (diagnostika, exploratorní; stav pozorovatelný při breach):**
   73 % MLE breachů nastává při plně intaktní IRC industry (STRONG ≤10,
   post-breach +5.15 %). COLLAPSED (>20, 10.3 % případů) je reálný
   diskriminátor (post-breach +0.53 %), ale i tam forward return kladný
   → kombinovaný MLE+IRC exit má záporný prior (~-0.05pp odhad).
   Exit tedy zahazuje přesně tu kontextovou sílu, na které edge stojí.
   IRC delta-5d: nemonotónní, bez signálu.
   Data: results/diagnostics/RP-0012_rank_trajectory*.csv, _irc*.csv.

## Edge Lifetime Hypothesis (exploratorní — NENÍ prokázáno)

Diagnostika hold-profilu (run_hold_profile_diagnostic.py, common
completable subset H=60, N=816, entries do 2026-04-08):

```
hold   alpha vs SPY   alpha/den
20D        2.52 %      12.6 bps
30D        5.03 %      16.8 bps
40D        6.76 %      16.9 bps
60D       11.77 %      19.6 bps
marginální segmenty 20→60D: +17 až +27 bps/den (žádný rozpad)
```

Interpretační posun: MLE zřejmě neidentifikuje krátkodobého leadera,
ale ZAČÁTEK delšího pozitivního driftu; 20D hold je pracovní volba,
ne nalezená hranice edge. Konzistentní se všemi třemi negativy
(pullback entry, EMA exit, rank exit): edge přežívá krátkodobou slabost.

ZÁVAZNÉ VÝHRADY:
- Deskriptivní; masivní překryv oken, bez clusteringu; jeden režim.
- Subset NENÍ reprezentativní: 20D mean 4.15 % vs 7.23 % plný vzorek
  (chybí silné entries 04–06/2026). Tvar křivky v posledním kvartálu
  nelze spolehlivě vyhodnotit.
- Výběr horizontu z této křivky pro test = selekce z 8 kandidátů;
  konfirmační běh na týchž datech má sníženou hodnotu. PM rozhodnutí
  2026-07-02: RP-0013 (Edge Lifetime Characterization) NEpreregistrovat
  na základě této křivky; cíl budoucího RP = charakterizace rozpadu
  alpha (kdy/jak), ne hledání „lepšího" parametru. Kandidátní cesty:
  OOS akumulace archivu, nebo explicitní korekce za rodinu horizontů.
- Trade-level ≠ portfolio: v MSL může být optimum ~20D kvůli kapitálu
  a příchodu nových signálů, i když alpha trvá déle.

## Limitace

1. Jedno běhové období; leadership-loss frekvence režimově závislá.
2. Entry close(D) look-ahead sdílený párem.
3. Survival po 20d jen na trades s rank pokrytím D+20 (deskriptivní subset).

## Důsledky

- Rank-loss exit rodina (rank_10d prahy) pro MLE×IRC pool UZAVŘENA.
- Kombinovaný MLE+IRC exit NEpreregistrovávat (záporný prior z diagnostiky).
- Nepromovat do MSL; fixed 20D hold zůstává baseline — nyní podepřen
  negativně ze tří stran a Edge Lifetime diagnostika naznačuje, že je
  spíše konzervativní než optimální (neprokázáno).
- rank_20d varianta jen jako nový preregistrovaný RP s a-priori
  zdůvodněním; roll-off mechanismus platí i pro ni (nízký prior).

## Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-07-EXIT-EMA-v1
      note: "price-based exit selhal → test signálově nativního pravidla"
    - ref: KR-2026-06-MLE-rank-value-decay
      note: "a-priori opora prahu 50 (selection-time profil)"
  inspired:
    - ref: "budoucí: RP Edge Lifetime Characterization"
      note: "hold-profile diagnostika; PM 2026-07-02: bez okamžité preregistrace"
  produced_rules:
    - "MLE_Rank_10d je ENTRY signál (čerstvost pohybu), ne hold-state signál"
```
