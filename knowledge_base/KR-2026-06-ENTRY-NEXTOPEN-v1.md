# KR-2026-06-ENTRY-NEXTOPEN-v1

**Class:** entry-edge (Entry Validation)
**Research Project:** RP-0009-ENTRY-TIMING
**Experiment:** EntryTimingNextOpen_v1
**Status:** VALIDATED

```yaml
run_id:       5f6008e2-1bdb-4f81-ac78-130492be6915
result_hash:  8f3a1ebd2960165c22ff
archive:      results/EntryTimingNextOpen/1.0.0/20260701_031149_5f6008e2/
determinism:  3 běhy, 3 run_id, 1 identický result_hash (8f3a1ebd…)
period:       2025-07-09 → 2026-06-27
universe:     MLE TOP10 × IRC TOP10 (lookback 20D)
created:      2026-06-30
```

> KR = current best knowledge, not truth.

---

## Hypotéza

Vstup na open(D+1) dává stejný forward return jako vstup na close(D) nad MLE×IRC
kandidáty (matched alpha ~0) → next-open je produkčně realizovatelná náhrada za
close-entry research baseline.

## Metodika

```
ENTRY_001 baseline : close(D) → close(D+20)      [look-ahead caveat]
ENTRY_004          : open(D+1) → close(D+1+20)   [první realizovatelná cena]
MIN_FUTURE_DAYS=21 | ticker-clustered bootstrap (B=2000, seed=42)
100% fill obou variant — čistý timing, množina se NEMĚNÍ (žádný skipped)
baseline pro alpha = ENTRY_001 | regime split: DEFERRED
```

## Metriky (autoritativní běh, N=1049 candidate-days, 147 unikátních tickerů)

| varianta | mean fwd ret | median | win | matched alpha vs 001 |
|---|---|---|---|---|
| ENTRY_001 close(D) | +7.167 % | — | 64.92 % | — (baseline) |
| ENTRY_004 open(D+1) | +7.141 % | — | 65.11 % | **-0.026 pp** CI[-0.30, +0.23] **nesignif.** |

## Závěr

**Next-open vstup je produkčně použitelná náhrada za close-entry baseline bez
měřitelné degradace edge v dostupném období.**

Přesná formulace:
- NE „next-open je lepší".
- NE „close a open jsou identické".
- ANO „žádný prakticky významný rozdíl nebyl nalezen".

```
Signál vznikne po close D → BOT vstoupí na open D+1 → edge zůstává zachován
```

- ENTRY_001 (close D) nese look-ahead caveat (vstup na close, z něhož je signál).
- ENTRY_004 (open D+1) je první SKUTEČNĚ realizovatelná cena po signálu.
- Dávají totéž → close-based validace (STR-0001, EntryTimingEdge) je produkčně
  přenositelná na next-open bez degradace.

## Determinismus (přidáno 3. během)

Tři nezávislé běhy → tři různé run_id, ale **identický result_hash `8f3a1ebd…`**.
Prokázán determinismus experimentálního enginu (ne jen reprodukovatelnost výsledku):
run_id = otisk běhu, result_hash = otisk výsledku. Seed 42 fixní.

## Promotion

**ENTRY_004 approved as production-compatible entry proxy for close-entry research
baseline. Eligible for MSL / future production simulations.**
`entry_mode="next_open"` + `STR_0004` přidány do MSL (execution_model, portfolio_engine,
strategy_runner, strategy_definition). Regrese: STR-0001 close bit-identický (hash
0bea4b4045ec) → zpětně kompatibilní.

## Caveats / hranice platnosti

- **Rozsah:** MLE×IRC momentum leadeři, 2025-07 → 2026-06, hold 20D. Neextrapolovat.
- **Single ~1Y bull/momentum window; regime split deferred** — verdikt vázaný na období.
- CI[-0.30, +0.23]pp vylučuje jen rozdíly > ~0.3pp → „ekvivalentní" = „žádný prakticky
  významný rozdíl nenalezen", ne „identické".
- Dependence: nominal N=1049, tickerů=147 (poměr 0.14) → efektivní N << nominal;
  signifikance jen z ticker-clustered bootstrapu.
- **Portfolio-level ≠ tento test:** STR-0004 (next_open portfolio) má nižší CAGR
  (1.09 vs 1.37) — kapacitní/path artefakt nasyceného portfolia, NE degradace edge.
  Autoritativní čtení ekvivalence je tento matched forward-return test (~0 alpha).

## Rozsah tvrzení (co NENÍ prokázáno)

Uzavřeno: pullback, dva pullbacky, next-open (jednoduché entry-timing manipulace).
NEtestováno: follow-through, průraz báze, konsolidace (continuation vstupy) a celá
Exit osa. „Entry nemá edge" NEplyne z toho, že tři jednoduché varianty edge nepřidaly.
Entry Validation v1 je uzavřená; entry osa se ZUŽUJE, neuzavírá.
