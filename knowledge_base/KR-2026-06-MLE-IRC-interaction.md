# Knowledge Record: MLE × IRC Signal Interaction

```yaml
kr_id:          KR-2026-06-MLE-IRC-interaction
status:         ACTIVE
confidence:     MEDIUM
evidence_level: B
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0001-SIGNAL-INTERACTION
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "IRC Audit v4 — Test 7 (test_cross_module.py)"
      type: audit
      note: "Původní zjištění: MLE TOP20 + IRC TOP10 industry → tailwind efekt"
    - ref: KR-2026-06-IRC-persistence-edge
      type: knowledge_record
      note: "IRC validován jako industry-level context modul"

  inspired:
    - ref: "MRL Architecture Candidate validace"
      type: observation
      note: "Reprodukce historického auditu ověřila MRL framework end-to-end"

  produced_rules: []
```

---

## Co bylo zjištěno

### Finding 1 — Metodika určuje výsledek, ne implementace

Dva experimenty se stejnou výzkumnou otázkou ale různou metodikou:

| Verze | MLE filtr | IRC filtr | Metrika | Výsledek |
|---|---|---|---|---|
| v1.0.0 | TOP50 (rank_20d) | TOP20 industries | absolutní return | +0.22pp NOT SUPPORTED |
| v1.1.0 | TOP20 (rank_10d) | TOP10 industries | alpha vs SPY | +1.28pp SUPPORTED |

Rozdíl nebyl chyba v implementaci. Byla to odlišná definice experimentu —
širší/užší selekce a odlišná metrika (absolutní return vs. alpha).

### Finding 2 — MLE + IRC_TOP10 generuje silnou alpha

Na plném datasetu (2025-07-09 → 2026-06-29, 219 obchodních dní):

| Skupina | Median 30D alpha | Win Rate | N |
|---|---|---|---|
| MLE+IRC_TOP10 | **+1.41%** | 55.1% | 1,984 |
| MLE_HEADWIND | +0.13% | 50.5% | 2,396 |

**Spread: +1.28 procentního bodu alpha.**

### Finding 3 — IRC funguje jako kontextový filtr, ne samostatný generátor

MLE+IRC_TOP10 (+1.41% alpha) výrazně převyšuje IRC_strong_only bez MLE
(z v1.0.0 testu: +0.61% absolutní return, slabší metrika).
IRC samo o sobě nestačí — potřebuje silný individuální ticker (MLE) zároveň.

### Finding 4 — Reprodukce historického auditu v MRL

Reprodukce historického auditu (Test 7) v MRL potvrdila že framework
dává konzistentní výsledky se stejnou metodikou. To je první reprodukce
historického referenčního auditu v prostředí MRL — audit vznikl dříve
a mimo MRL, ale je součástí stejného projektu, ne nezávislé externí studie.

---

## Doporučený standard pro budoucí experimenty

**Primární metrika pro selekční moduly (MLE, IMS, IRC): alpha vs. SPY.**

Absolutní return zůstává jako doplňková metrika, ale ne primární — v bull
marketu obsahuje tržní drift který zkresluje srovnání mezi skupinami.

---

## Kdy platí

- S&P 500 universe
- MLE TOP20 podle rank_10d (10D lookback)
- IRC TOP10 industries (z 59), lookback 20D
- Backtest 2025-07-09 → 2026-06-29 (219 dní)
- Point-in-time join (IRC rank známý k datu MLE signálu)

## Kdy neplatí / nevalidováno

- Širší MLE selekce (TOP50+) — efekt slábne (viz v1.0.0)
- RISK_OFF podmínky — nevalidováno, čeká na MRC
- Mimo S&P 500
- Kratší než 30D forward horizon — nevalidováno systematicky přes všechny windows

---

## Evidence

```yaml
supported_by:
  - ref: "MLEIRCDependencyAudit v1.1.0"
    type: experiment
    note: "Reprodukce na plném datasetu, 2025-07-09 -> 2026-06-29"
  - ref: "IRC Audit v4 — Test 7"
    type: audit
    note: "Původní zjištění před vznikem MRL"
```

Tento Knowledge Record je syntéza obou důkazů, ne přepis jednoho reportu.

---

## Confidence: MEDIUM — odůvodnění

- Evidence Level B: jeden backtest, bez rolling validation, bez out-of-sample
- Žádná statistická významnost (bootstrap, Mann-Whitney) — pouze median/WR
- Žádný rozpad podle tržního režimu
- Reprodukce historického auditu zvyšuje důvěryhodnost nad rámec jednoho běhu

---

## Doporučení pro budoucí výzkum

- Bootstrap confidence interval pro diff_top10_vs_headwind
- Mann-Whitney U test mezi MLE+IRC_TOP10 a MLE_HEADWIND
- Rozpad podle tržního režimu (bull/correction/vysoká-nízká breadth)
- Doplnit MLE_WEAK bucket (rank > 10, < HEADWIND threshold) pro úplnost
- Rolling validace přes delší historii (čeká na 5-year dataset)
- Otestovat citlivost na IRC threshold (TOP5 vs TOP10 vs TOP15)
