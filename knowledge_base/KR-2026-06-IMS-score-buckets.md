# Knowledge Record: IMS Score Bucket Edge

```yaml
kr_id:          KR-2026-06-IMS-score-buckets
status:         ACTIVE
confidence:     LOW
evidence_level: B
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-2026-06-IMS-SCORE-EDGE
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: "IMS_audit/tests/return_analysis.py"
      type: audit
      note: "Legacy logika migrovaná do MRL jako Reference Experiment #2"
  inspired:
    - ref: KR-2026-06-MLE-IRC-interaction
      type: knowledge_record
      note: "Tento KR identifikoval limitaci absolutního returnu,
             která vedla k zavedení standardu alpha vs SPY"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "IMSScoreBucketEdge v1.0.0"
    type: experiment
    note: "Reference Experiment #2, plný dataset 2025-07-09 -> 2026-06-29"
```

---

## Co bylo zjištěno

### Finding 1 — Monotónní vztah IMS score → forward return

| Bucket | Median 30D return | Win Rate | N |
|---|---|---|---|
| RADAR (60–69) | +0.63% | — | 8,722 |
| H70-79 | — | — | 7,644 |
| H80-89 | — | — | 4,106 |
| H90-94 (ELITE) | +2.77% | ~60% | 366 |
| H95+ | +4.54% | — | 15 |

Spread ELITE–RADAR: **+2.14pp** (threshold 0.5pp). H-001 SUPPORTED.

### Finding 2 — H95+ bucket statisticky nespolehlivý

N=15 pro nejvyšší bucket je příliš malé pro spolehlivý odhad.
Hodnota +4.54% může být zkreslena outliery.

### Finding 3 — KRITICKÁ LIMITACE: absolutní return, ne alpha

Tento experiment byl spuštěn **před zavedením standardu alpha vs SPY**
(viz SYSTEM_ARCHITECTURE.md sekce 9, zavedeno na základě
KR-2026-06-MLE-IRC-interaction).

Měřená metrika je absolutní 30D forward return, ne alpha vs SPY.
V bull marketu (2025-07-09 → 2026-06-29) absolutní return obsahuje
tržní drift. Spread +2.14pp mezi ELITE a RADAR mohl by být nižší
nebo vyšší po očištění o pohyb trhu — nevalidováno.

**Toto je hlavní důvod nízké Confidence (LOW, ne MEDIUM).**

---

## Kdy platí

- S&P 500 universe
- IMS score buckety dle legacy definice (RADAR 60-69, H70-79, H80-89, H90-94, H95+)
- Backtest 2025-07-09 → 2026-06-29
- Metrika: absolutní forward return (NE alpha)

## Kdy neplatí / nevalidováno

- Nevalidováno jako alpha-adjusted edge — viz Finding 3
- H95+ bucket nespolehlivý (N=15)
- RISK_OFF podmínky — nevalidováno
- Mimo S&P 500

---

## Confidence: LOW — odůvodnění

Sníženo z MEDIUM na LOW oproti běžné Evidence Level B kvůli:
- Absolutní return jako metrika (porušuje aktuální standard)
- H95+ bucket s N=15 — statisticky nespolehlivý
- Bez rolling validace, bez out-of-sample testu
- Bez statistické významnosti (bootstrap, Mann-Whitney)

---

## Doporučení pro budoucí výzkum

**Priorita 1 — Re-test s alpha vs SPY**
Spustit `IMSScoreBucketEdge v1.1.0` s metrikou alpha vs SPY (analogicky
k MLEIRCDependencyAudit v1.0 → v1.1 migraci). Bez tohoto re-testu nelze
potvrdit zda je IMS score edge reálný nebo je to z velké části tržní drift.

**Priorita 2 — Statistická významnost**
Bootstrap CI pro spread ELITE-RADAR. Mann-Whitney U test.

**Priorita 3 — H95+ bucket**
Rozšířit datový rozsah nebo sloučit s H90-94 dokud N nebude dostatečné.
