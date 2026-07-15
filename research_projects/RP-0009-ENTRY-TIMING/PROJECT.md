# Research Project: Entry Timing Edge

```yaml
project_id:        RP-0009-ENTRY-TIMING
portfolio_area:    Execution / Entry
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
last_updated:      2026-06-30
priority:          MEDIUM
class:             entry-edge
```

---

## Research Question

> Přidává ZPŮSOB VSTUPU (čekání na cenový pullback) inkrementální
> forward-return edge nad baseline close-entry, nad množinou MLE×IRC
> kandidátů — nezávisle na portfolio simulaci?

První entry-edge projekt MRL. Oddělený od selection-edge (edge_validation).
Motivace: MSL STR-0001 ukázal, že cap=5 je kapacitně nasycený (fill ~5 %),
takže STR-0002 pullback jako portfolio sim by byl kapacitně kontaminovaný.
Čistý entry-timing read = forward returns bez capu → patří do MRL.

---

## Varianty (pre-registrováno a priori 2026-06-30)

```
ENTRY_001  baseline   — buy close v den signálu,           hold 20D
ENTRY_002  1 pullback — první close < prev (wait 5),        hold 20D
ENTRY_003  2 pullbacks— dva po sobě jdoucí poklesy (wait 7),hold 20D
                        flat den (==) přerušuje sekvenci
```

Metodické zámky: matched comparison povinně; opportunity cost = return
přeskočených; oddělit entry alpha vs strategy-level net; ticker-clustered
bootstrap; common completable subset (min_future_days=27); regime split deferred.

---

## Experiment

`experiments/entry_validation/entry_timing_edge_v1.py` (EntryTimingEdge_v1)
Launcher: `run_entry_timing_edge_v1.py`

---

## Status / výsledek

Viz `knowledge_base/KR-2026-06-ENTRY-TIMING-v1.md`.

Verifikační běh (archivy 2026-06-30): ani jedna pullback varianta nepřidává
strategy-level edge; ENTRY_003 má signif. conditional entry alfu (+3.3pp), ale
strategy-level -2.27pp (míjí nejsilnější movery, K3 +22 % vs S3 +7 %).
Doporučení: nepromovat do MSL. Regime-vázané — re-run po Regime Engine.

---

## Navazující (samostatné, ne v1)

- X sweep (wait dní) jako samostatný pre-registrovaný experiment.
- Re-run se stratifikací režimů.


## Experimenty v tomto projektu

1. **EntryTimingEdge_v1** — pullback varianty (ENTRY_001/002/003).
   Výsledek: pullback nepřidává strategy-level edge. Viz KR-2026-06-ENTRY-TIMING-v1.
2. **EntryTimingNextOpen_v1** — close(D) vs open(D+1) čistý timing.
   Výsledek: next-open ≈ close (matched alpha ~0) → produkčně použitelná náhrada.
   Viz KR-2026-06-ENTRY-NEXTOPEN-v1. PROMOTED as production-compatible entry proxy.
