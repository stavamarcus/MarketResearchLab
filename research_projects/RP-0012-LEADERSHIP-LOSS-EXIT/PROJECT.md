# Research Project: Leadership Loss Exit

```yaml
project_id:        RP-0012-LEADERSHIP-LOSS-EXIT
portfolio_area:    Execution / Exit
research_status:   COMPLETED
production_status: NOT_EVALUATED
created:           2026-07-02
last_updated:      2026-07-02
priority:          HIGH
class:             exit-edge
```

---

## Research Question

> Realizuje exit podmíněný ztrátou leadership statusu (MLE_Rank_10d > 50,
> fill next open) větší část validovaného MLE×IRC selection edge uvnitř
> fixního 20D okna než baseline fixed 20D hold?

Druhý experiment třídy Exit Validation. Na rozdíl od EXIT_001 (externí
technická aproximace trendu — EMA) používá informaci přímo z validovaného
selekčního signálu.

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  "KR-2026-07-EXIT-EMA-v1 (draft)"
    note: "EXIT_001: EMA exit signifikantně ZHORŠUJE fixní 20D okno
           (EMA20 -2.72pp, CI[-4.55,-1.11]); monotónní přes periody.
           Price-based exit odřezává pokračování leaderů."
  - type: knowledge_record
    ref:  "KR-2026-06-MLE-rank-value-decay"
    note: "Kumulativní profil: TOP30 poslední kladný bod (+0.23%),
           TOP50 -0.09%. A-priori opora prahu 50 jako hranice, za níž
           rank nenese edge. Měřeno v okamžiku selekce, NE během holdu —
           hold-conditional rank trajektorie dosud netestována."
  - type: hypothesis
    ref:  "architekt — návrh EXIT_002, PM approval 2026-07-02"
```

Prior-check (povinný, proveden): žádný předchozí experiment netestoval
držení podmíněné rank trajektorií během holdu. RP-0007 = selection-time
profil; PRE-LEADERS = konverze DO TOP50 (entry strana). EXIT_002 je nový.

---

## Motivation

Pokud H1a projde → MSL STR-0002 (MLE×IRC + Leadership Loss exit).
Pokud neprojde → fixed 20D hold potvrzený proti druhé, signálově nativní
exit rodině. Survival statistika má hodnotu i při nerozhodném výsledku
(frekvence leadership loss uvnitř 20D = nová deskriptivní znalost).

---

## Dependencies

```yaml
dependencies:
  - id: DEP-001
    type: dataset
    ref:  "MDSM-Lite D1 cache (CACHE_ONLY)"
    status: COMPLETE
  - id: DEP-002
    type: dataset
    ref:  "MLE archiv — MLE_Rank_10d denně, plné pokrytí okna"
    description: "exit rule čte rank D+1..D+19; mezery → censored"
    status: COMPLETE
  - id: DEP-003
    type: module
    ref:  "exit_validation framework z RP-0011 (ExitRule, exit_engine)"
    status: COMPLETE
```

---

## Hypotheses (pre-registrováno, zamčeno 2026-07-02)

### H-001 (H1a) — PRIMÁRNÍ

- **H0:** RANK_50 exit nemění mean return uvnitř fixního 20D okna proti
  fixed 20D hold (paired diff = 0).
- **H1:** RANK_50 exit zvyšuje mean return uvnitř fixního 20D okna.

```
Jednotka:    candidate-day (ticker, D), MLE TOP10 × IRC TOP10
Entry:       close(D)
Okno:        fixní D → D+20 (obě větve)
Baseline:    hold do close(D+20)  [TIME_20, identický engine]
Varianta:    signal: MLE_Rank_10d(k) > 50, D < k < D+20, rank as-of
             close(k) → fill open(k+1); po exitu cash 0 %
Rank série:  MLE_Rank_10d — TÁŽ série jako selekce (zámek)
Primární metrika: mean paired return difference
Inference:   ticker-clustered bootstrap, B=10000, seed=42, 95% CI
Rozhodnutí:  H1 podpořena ⇔ CI celé > 0
```

### Sensitivity analysis (NE hypotézy)

```
RANK_25, RANK_100 — táž rodina (stock leadership loss), pouze
robustnost směru. Žádné vlastní kritérium, žádný a-posteriori práh.
IRC varianty (industry leadership loss, OR/AND kombinace) VYLOUČENY —
jiný mechanismus, patří do samostatného RP podmíněného výsledkem.
Práh 30 se dodatečně NEPŘIDÁVÁ (byl by sweep).
```

### Doprovodná statistika — Leadership Survival (deskriptivní, povinná)

```
Pro included trades a prahy {25, 50, 100}:
  pct_in_topN_after_{5,10,15,20}d  (přežití = žádný breach v D+1..D+k)
  median time-to-loss mezi trades s breachem
Účel: interpretace H1a. Vysoké přežití (např. 95 % po 20D) předem
vysvětluje nulový efekt; rychlý dropout činí negativní výsledek
překvapivým. Bez rozhodovacího kritéria.
```

---

## Metodické zámky

```
- matched comparison: stejní kandidáti, stejné okno, párový rozdíl
- min_future_days = 22 (převzato z EXIT_001)
- MISSING RANK = CENSORED (PM 2026-07-02): trade s JAKOUKOLIV chybějící
  rank hodnotou v signal window D+1..D+19 se vylučuje ze VŠECH variant
  i baseline (identický matched set, žádná imputace/carry-forward).
  Report počtu + podílu; podíl > 1 % → investigace před interpretací.
  Censoring nesmí záviset na chování varianty (kontrola úplnosti
  pokrytí je variantově nezávislá).
- signal na close (rank as-of close k, D1 batch), fill next open;
  baseline TIME_20 close-to-close; fill exekuce výhradně exit_engine
- žádný price warmup (rank rule nepotřebuje) → N větší než EXIT_001
- chybějící open při fillu: posun na první dostupný, flag (engine z RP-0011)
- CACHE_ONLY; žádný window/threshold sweep; regime split DEFERRED
- deterministic result_hash (fixní seed)
```

---

## Metriky

**Primární:** mean paired diff RANK_50 − TIME_20 + clustered 95% CI.

**Deskriptivní (všechny varianty):** mean/median return, expectancy,
win rate, avg winner/loser, hold length, early exit frequency,
avoided losers / missed winners (+ mean zbytkového returnu obou skupin),
fill gap flagy.

**Censoring:** censored_missing_rank_n, censored_missing_rank_pct.

**Survival:** tabulka přežití dle definice výše.

**Vyloučeno:** fill ratio, portfolio metriky (→ MSL), H1b/uncapped větev
(mimo scope EXIT_002).

---

## Architektura

```
experiments/exit_validation/
├── exit_rules.py            # + RankLossExit(threshold) — aux série
│                            #   přes set_series(); ABC beze změny
├── exit_engine.py           # BEZE ZMĚNY (převzato z RP-0011)
├── leadership_loss_edge.py  # LeadershipLossEdge_v1
└── config/EXIT_002.yaml     # preregistrace + integritní kontrola
Launcher: run_leadership_loss_edge_v1.py
Výstup:   results/LeadershipLossEdge/1.0.0/... + KR-2026-07-EXIT-RANKLOSS-v1
```

---

## Známé limitace (a priori)

1. Očekávaná nízká frekvence signálu (TOP10 → za 50 uvnitř 20D je
   vzácná událost) → riziko širokého CI / nerozhodného výsledku.
   Survival statistika to kvantifikuje. [označená spekulace]
2. Jedno běhové období, regime deferred (zděděno).
3. Práh 50 a-priori podložený decay profilem, ale hranice TOP30/TOP50
   je pásmo, ne bod.

---

## Status

COMPLETED — autoritativní běh 2026-07-02.

H1a NOT SUPPORTED (signif. opačný směr): RANK_50 -4.353pp CI[-6.32,-2.256]. Survival: 98.4 % leaderů ztratí TOP50 do 20D (strukturální roll-off). Diagnostiky: IRC vrstva (73 % breachů při STRONG industry), hold-profil (Edge Lifetime Hypothesis). Rank-loss exit rodina uzavřena.
Viz `knowledge_base/KR-2026-07-EXIT-RANKLOSS-v1.md`.

## Experimenty v tomto projektu

1. **LeadershipLossEdge_v1** — RANK_50 primární, RANK_25/100 sensitivity,
   survival statistika. Status: DONE (viz KR).
