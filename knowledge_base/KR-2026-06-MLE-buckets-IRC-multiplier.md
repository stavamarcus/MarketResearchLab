# Knowledge Record: IRC jako multiplikator, ne zachranny filtr

```yaml
kr_id:          KR-2026-06-MLE-buckets-IRC-multiplier
status:         ACTIVE
confidence:     MEDIUM-HIGH
evidence_level: B+
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0008-MLE-BUCKETS-IRC
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-rank-value-decay
      type: knowledge_record
      note: "MLE rank decay — hranice edge mezi TOP30 a TOP50"
    - ref: KR-2026-06-MLE-IRC-rolling
      type: knowledge_record
      note: "MLE x IRC TOP20 dosahl HIGH confidence — tento KR testuje
             jemnejsi MLE buckety"
  inspired:
    - ref: "budouci: Decision Resolver priority tiers (revidovana hypoteza)"
      type: observation
      note: "Puvodni hypoteza 'IRC zachranuje slabe' VYVRACENA —
             spravna struktura je 'IRC multiplikuje silne'"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLEBucketsIRCGrid v1.0.0"
    type: experiment
    note: "12 kombinaci (6 MLE bucketu x 2 IRC skupiny), plny dataset
           2025-07-09 -> 2026-06-29, 219 obchodnich dni"
```

---

## Co bylo zjisteno

### Grid (alpha vs SPY, 30D, HEADWIND vs IRC_TOP10)

```
Bucket          HEADWIND    IRC_TOP    Diff
MLE_1_10         +0.23%      +2.49%   +2.26%
MLE_11_20        -0.06%      +0.12%   +0.18%
MLE_21_30        -0.42%      -0.58%   -0.15%
MLE_31_50        -0.60%      -0.44%   +0.16%
MLE_51_70        -1.11%      -1.47%   -0.35%
MLE_71_100       -1.32%      -1.00%   +0.31%
```

### Finding 1 — Puvodni hypoteza vyvracena

Vstupni hypoteza projektu byla: "IRC zachranuje slabsi MLE buckety."
Vysledek ukazuje OPAK: **IRC efekt je nejsilnejsi prave u TOP10**
(+2.26pp), kde MLE uz samo o sobe funguje. U bucketu 21-30 a 51-70
ma IRC dokonce mirne ZAPORNY dopad (-0.15pp, -0.35pp).

### Finding 2 — Spravny model: multiplikator, ne zachranny filtr

```
NESPRAVNY model: IRC zachranuje slabe MLE kandidaty
SPRAVNY model:   IRC multiplikuje uz existujici silny signal
```

Toto je tretí nezávisle vznikly dukaz stejne struktury:
1. MLERobustnessGrid (RP-0004): nejsilnejsi efekt u MLE TOP10 napric IRC prahy
2. MLE rank decay (RP-0007): MLE TOP10 nese vetsinu informacni hodnoty
3. Tento KR: IRC diff nejvetsi prave u TOP10, ne u slabsich bucketu

### Finding 3 — Castecne potvrzeni H-002, castecne vyvraceni

```
H-001 (TOP10 funguje i bez IRC):        ANO — HEADWIND je kladna (+0.23%)
H-002 (11-30 potrebuje IRC):            CASTECNE
   MLE_11_20: HEADWIND zaporna, IRC_TOP kladna -> ANO, IRC pomaha
   MLE_21_30: diff -0.15pp -> V TOMTO DATASETU SE NEPOTVRDILO,
              ze IRC zlepsuje tento bucket
H-003 (51+ mrtve i s IRC):              ANO — zadny zachranny efekt
```

**Opatrna formulace (architekt, 2026-06-30):** Rozdil u 21-30 (-0.15pp)
je maly a jde o jediny experiment bez statisticke vyznamnosti. Spravna
formulace NENI "21-30 IRC nepotrebuje" — to je prilis silne tvrzeni.
Spravna formulace je: "V tomto datasetu se nepotvrdilo, ze IRC zlepsuje
vysledky pro MLE bucket 21-30." Rozdil mezi negativnim potvrzenim a
absenci potvrzeni je dulezity pro presnost Knowledge Base.

Hranice "IRC prokazatelne pomaha" konci nekde mezi 11-20 a 21-30, ale
toto neni definitivni hranice — pouze pozorovani z jednoho experimentu.

---

## Architektonicky dopad — revidovana hypoteza priority tiers

**Puvodni navrh (KR-2026-06-MLE-rank-value-decay):**
```
Priority A: TOP10      -> muze projit samostatne
Priority B: TOP11-30   -> potrebuje IRC potvrzeni
Priority C: TOP30+     -> potrebuje silnou dalsi evidenci
```

**Revidovany navrh na zaklade tohoto KR:**
```
Priority A: TOP10            -> nejsilnejsi i samostatne, IRC ho dale VYRAZNE posiluje
Priority B: TOP11-20         -> slaby samostatne, IRC pomaha mirne
Priority C: TOP21-30         -> slaby, IRC NEPOMAHA (mozna i skodi)
Priority D: TOP30+           -> mrtve, IRC nezachranuje
```

**Toto je stale hypoteza, ne schvalene pravidlo.** Vyzaduje formalni
Resolution pred pouzitim v Decision Resolveru.

---

## Kdy plati

- S&P 500, MLE rank_10d, IRC TOP10 (lookback 20D)
- Backtest 2025-07-09 -> 2026-06-29 (219 dni)

## Kdy neplati / nevalidovano

- Pouze ~1 rok dat — stabilita pres trzni cykly nevalidovana
- RISK_OFF podminky
- Statisticka vyznamnost jednotlivych bunek gridu (N kolisa, nekompletni
  rolling validace pro tento konkretni grid)

---

## Confidence: MEDIUM-HIGH — odůvodnění

- Testovaci a plny dataset davaji konzistentni vysledky
  (diff TOP10: +2.13pp test -> +2.26pp plny dataset)
- Treti nezavisly dukaz stejne strukturalni hypotezy (multiplikator,
  ne zachranny filtr) — konvergence napric ruznymi experimenty

NE HIGH:
- Chybi rolling validation specificky pro tento grid
- Mensi buckety (21-30, 51-70) maji nizsi N — vyssi sum
- Negativni diff u 21-30 a 51-70 nejsou vysvetleny (mohou byt sum)

---

## Doporuceni pro budouci vyzkum

- Rolling validation tohoto gridu (analogicky k RP-0005)
- Overit zda negativni diff u 21-30/51-70 je systematicky nebo sum
  (bootstrap CI pro kazdou bunku)
- Formalni navrh revidovanych priority tiers jako samostatny
  Research Project pred jakymkoliv pouzitim v Decision Resolveru
