# FUND-05 Edge Run Plan (pouze plán — implementace až po schválení FUND-04)

## 1. Vstupy

```text
candidate_days.csv — čerstvý deterministic extraction run
    (run_fund03_extract_candidate_days.py) k datu spuštění FUND-05;
    hash v manifestu
pinned snapshot: sf1art_20260704_005521 (nebo novější PM-schválený pin)
MDSM ceny: MRL price provider (forward returns, SPY pokud bude
    schválena sekundární alpha metrika)
schválené dokumenty FUND-04 (whitelist, leakage protokol, edge protokol)
```

## 2. Source files

```text
MLE rank_matrix_archive.csv, IRC industry_rank_calendar_archive.csv,
sp500_rank_calendar_universe.csv (extraction vstupy; SHA-256 v manifestu)
adapter_config.yaml + identity_map_resolved_v2.csv (přes adapter API)
config/data_paths.yaml (sharadar_fundamentals sekce, enabled pro run)
```

## 3. Expected runner

```text
run_fundamental_edge_protocol.py    (NEIMPLEMENTOVÁN ve FUND-04)
Preferovaná forma: BaseExperiment `FundamentalEdgeProtocol` v1.0.0
spouštěný přes ExperimentRunner (registry + immutable archiv +
report.md standard) s context.fundamental_source (FUND-02 wiring).
Alternativa standalone runneru jen pokud framework integrace narazí
na technický blocker — rozhodne se na začátku FUND-05.
```

## 4. Expected output folder

```text
results/FundamentalEdgeProtocol/1.0.0/<ts>_<shortid>/
    metadata.json, config.yaml, metrics.json,
    tables/ (per-variant metriky, per-záznam tabulka bez cen,
             dependence report, non-overlap subsample),
    artifacts/coverage_<run_id>.md,
    report.md
```

## 5. Expected reports

```text
report.md — všechny varianty A–F, plné metriky §3, dependence §4,
            PASS/FAIL/INCONCLUSIVE per varianta, RESULT celého runu
coverage report — adapter formát, povinný (bez něj výsledek NEVALIDNÍ)
source manifest — hashe všech vstupů
```

## 6. Testy před spuštěním

```text
stávající suita (50) PASS
nové testy FUND-05: variant filter rules (fixní prahy, synthetic),
    field_null_excluded accounting, non-overlap subsample determinismus,
    STOP detekce (forbidden columns, coverage<95, UNKNOWN_ERROR),
    žádné HTTP/MDSM-Lite/Resolver importy v novém kódu
```

## 7. Co je výsledek

Per varianta B–F: PASS / FAIL / INCONCLUSIVE dle FUND-04 §5; run-level
STOP podmínky mají přednost. Výstupem je KR návrh (pozitivní i negativní
výsledek je plnohodnotný — precedens RP-0011/0012); žádné tvrzení
„edge potvrzen", maximum „candidate for OOS validation".

## 8. Mimo scope

```text
out-of-sample validace, robustness grid, portfolio simulace, sizing,
náklady/slippage, Decision Resolver, MDSM-Lite integrace, produkční
nasazení, optimalizace prahů, API fetch
```
