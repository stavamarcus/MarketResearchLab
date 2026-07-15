# Research Project: Exit Timing Edge

```yaml
project_id:        RP-0011-EXIT-TIMING
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

> Realizuje dynamický exit (close < EMA20, fill next open) větší část
> validovaného MLE×IRC selection edge uvnitř fixního 20D okna než
> baseline fixed 20D hold — na trade-level, nezávisle na portfolio
> simulaci?

První exit-edge projekt MRL. Otevírá třídu Exit Validation
(`experiments/exit_validation/`). Selection edge je znám (MLE×IRC,
HIGH confidence); otázka není *co koupit*, ale *kdy přestat držet*.

---

## Background

```yaml
sources:
  - type: knowledge_record
    ref:  "KR-2026-06-MLE-IRC-SYNTHESIS"
    note: "validovaný selection edge — vstupní množina kandidátů"
  - type: knowledge_record
    ref:  "KR-2026-06-ENTRY-TIMING-v1"
    note: "metodický protokol: matched comparison, strategy-level net,
           ticker-clustered bootstrap, common completable subset"
  - type: hypothesis
    ref:  "architekt — návrh EXIT_001, PM approval 2026-07-02"
    note: "EMA exit jako první kandidát exit validace"
```

---

## Motivation

Pokud H1a projde → STR-0002 v MSL (MLE×IRC + EMA20 exit, portfolio-level).
Pokud neprojde → fixed 20D hold zůstává baseline a negativní výsledek
uzavírá EMA-break rodinu exitů pro tento candidate pool (analogicky
k uzavření pullback entry v RP-0009).

---

## Dependencies

```yaml
dependencies:
  - id: DEP-001
    type: dataset
    ref:  "MDSM-Lite D1 cache (CACHE_ONLY)"
    description: "closes + opens pro candidate pool, EMA warmup ≥60 barů před entry"
    status: COMPLETE
  - id: DEP-002
    type: research_project
    ref:  "RP-0004/0005/0008 (MLE×IRC validace)"
    description: "validovaný selection edge definuje candidate pool"
    status: COMPLETE
  - id: DEP-003
    type: module
    ref:  "candidate pool generátor z RP-0009 (MLE TOP10 × IRC TOP10)"
    description: "sdílená definice kandidátů — identická množina jako entry experimenty"
    status: COMPLETE
```

---

## Hypotheses (pre-registrováno, zamčeno 2026-07-02)

### H-001 (H1a) — PRIMÁRNÍ

- **H0:** EMA20 exit nemění mean return uvnitř fixního 20D okna proti
  fixed 20D hold (paired diff = 0).
- **H1:** EMA20 exit zvyšuje mean return uvnitř fixního 20D okna
  (dřívější odchod ze ztrátových trajektorií > ušlý zisk z whipsaw).

```
Jednotka:    candidate-day (ticker, D), MLE TOP10 × IRC TOP10
Entry:       close(D)  — baseline standard (konzistentní s RP-0009 / STR-0001)
Okno:        fixní D → D+20 (comparison window pro OBĚ větve)
Baseline:    hold do close(D+20)
Varianta:    signal close(k) < EMA20(k), D < k < D+20 → fill open(k+1);
             po exitu cash 0 % do konce okna
Primární metrika: mean paired return difference (varianta − baseline)
Inference:   ticker-clustered bootstrap, 95% CI, 10 000 resamplů
Rozhodnutí:  H1 podpořena ⇔ CI celé > 0
```

### Sensitivity analysis (NE samostatné hypotézy)

```
EMA10, EMA30 — stejný protokol, pouze citlivostní kontrola robustnosti
směru výsledku EMA20. Žádné vlastní rozhodovací kritérium. Žádný
a-posteriori výběr "nejlepší" periody.
```

### H-002 (H1b) — EXPLORATORNÍ (bez rozhodovacího kritéria)

- Uncapped/extended hold: exit až na EMA20 break, time-stop fallback 60D.
- Cenzoring: trade bez ukončení do konce datového okna → vyloučen
  z exploratorní větve (reportovat počet).
- Metrika: return/den (normalizace na nestejnou délku držení) +
  distribuce hold length.
- Výstup pouze deskriptivní; případný edge → nový preregistrovaný projekt.

---

## Metodické zámky

```
- matched comparison: stejní kandidáti, stejné okno, párový rozdíl
- common completable subset: min_future_days = 22
  (D+20 close pro baseline; exit signál nejpozději close(D+19),
   fill open(D+20))
- EMA definice: alpha = 2/(n+1), seed = SMA prvních n closes,
  počítáno z price provider closes ≤ k (žádný look-ahead)
- EMA warmup: ≥ 60 barů před D z price provideru (ne ze signál. archivu)
- signal na close, fill na next open — bez výjimek
- chybějící open(k+1) (halt): fill první dostupný open, flag do metadat
- CACHE_ONLY (CacheMissError = fail fast, žádný fetch)
- žádný window sweep, žádný a-posteriori práh
- regime split: DEFERRED (Regime Engine) — do KR jako limitace;
  očekávaná režimová podmíněnost exit pravidel je vyšší než u selection
- deterministic result_hash + versioned archiv
```

---

## Metriky

**Primární:** mean paired return difference + clustered 95% CI (jen EMA20).

**Deskriptivní (obě větve, všechny varianty):**
mean/median return, expectancy, win rate, avg winner, avg loser,
hold length (mean/median/distribuce), early exit frequency,
avoided losers (exit fired ∧ zbytek okna podkladu < 0),
missed winners (exit fired ∧ zbytek okna podkladu > 0).

**Vyloučeno:** fill ratio (exit next open je vždy realizovatelný),
portfolio metriky (CAGR/Sharpe/MDD/turnover/exposure → MSL STR-0002).

---

## Architektura

```
experiments/exit_validation/
├── __init__.py
├── exit_rules.py        # ExitRule ABC; TimeExit(n); EMAExit(period)
├── exit_engine.py       # trade simulace: entry fill → bar iterace →
│                        #   exit signál → next-open fill; fill logika
│                        #   POUZE zde, pravidla jen signalizují
├── exit_timing_edge.py  # ExitTimingEdge_v1: candidate pool → matched
│                        #   comparison → bootstrap → archiv
└── config/EXIT_001.yaml # preregistrace: varianty, zámky, parametry
```

Zásady:
- Baseline fixed 20D = `TimeExit(20)` — běží identickou pipeline jako
  EMA varianty (eliminace implementační asymetrie).
- `ExitRule.check(position_state, bar) -> ExitSignal | None`;
  rozšíření (ATR stop, Chandelier, Highest Close) = nová třída,
  žádná změna enginu.
- Launcher: `run_exit_timing_edge_v1.py` (root MRL).

---

## Výstup

```
results/ExitTimingEdge/1.0.0/{timestamp}_{run_id}/
├── metadata.json     (run_id, result_hash, config snapshot, git stav)
├── trades_*.parquet  (per-variant trade log)
├── summary.md        (report)
└── KR draft → knowledge_base/KR-2026-07-EXIT-EMA-v1.md
```

---

## Status

COMPLETED — autoritativní běh 2026-07-02.

H1a NOT SUPPORTED (signif. opačný směr): EMA20 -2.719pp CI[-4.548,-1.112]. Sensitivity monotónní (EMA10 -4.47, EMA30 -1.87). EMA-break exit rodina uzavřena.
Viz `knowledge_base/KR-2026-07-EXIT-EMA-v1.md`.

## Experimenty v tomto projektu

1. **ExitTimingEdge_v1** — EMA20 primární, EMA10/30 sensitivity,
   H1b exploratorní. Status: DONE (viz KR).
