# FUND-03 Candidate-Day Source Review

**Fáze:** MRL-FUND-03. Zdroj reálných MLE × IRC candidate-days pro coverage audit.
**Rozhodnutí architekta:** priorita A (experiment/registry artefakty) → B (signal archivy) → C (nový skript).

---

## 1. Nalezené možné zdroje

| Zdroj | Obsah | Umístění |
|---|---|---|
| A1. MRL results archivy (MLEBucketsIRCGrid aj.) | `grid_stats.csv` — agregované bucket statistiky (n, median_alpha, win_rate) | `results/MLEBucketsIRCGrid/1.0.0/.../tables/` |
| A2. MRL registry | metadata běhů (run_id, rozsahy), žádné per-day záznamy | `registry/experiment_runs.jsonl` |
| B1. MLE archiv | per-day per-ticker rank vektory (`date, ticker, rank_1d..rank_20d` + trailing `ret_*`) | `MarketLeadershipEngine\output\archive\rank_matrix_archive.csv` |
| B2. IRC archiv | per-day industry ranky (`date, lookback, rank, industry, ...`) | `industry_rank_calendar\output\archive\industry_rank_calendar_archive.csv` |
| B3. MDSM sp500 universe | `conid, ticker, sector, industry, active_flag` (503 řádků) | `MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv` |

## 2. Odmítnuté zdroje a důvody

- **A1 odmítnuto:** tabulky obsahují pouze agregáty per bucket (navíc s alpha
  sloupci) — per-candidate-day záznamy (conid, date) v archivech NEEXISTUJÍ;
  experimenty je drží jen in-memory.
- **A2 odmítnuto:** registry neobsahuje candidate-days, jen run metadata.
- MLE archiv sloupec `industry`: fill-rate 1,2 % → industry se bere z universe (B3).

## 3. Zvolený zdroj

**Varianta B** (B1 × B2, join přes B3) — deterministic extraction script
`run_fund03_extract_candidate_days.py`. Replikuje selekční logiku experimentu
MLEBucketsIRCGrid (feature `MLE_Rank_10d`, IRC lookback 20), ale BEZ price
warmupu a BEZ forward-window cutoffu — proto počty nesedí 1:1 s `n` v grid_stats
(1 144 zde vs. 1 017 v gridu; grid ořezává poslední ~40 dní kvůli 30D oknu).

## 4. Přesná definice candidate-day

```text
(conid, candidate_date) kde na candidate_date platí SOUČASNĚ:
    MLE rank_10d(ticker) <= 10                       (MLE TOP10)
    IRC rank(industry(ticker), lookback=20) <= 10    (IRC TOP10)
industry(ticker) a conid(ticker) z MDSM sp500 universe
pouze dny přítomné v OBOU archivech (průnik)
dedup exact duplicit; sort (candidate_date, conid)
```

Zvolená varianta: **MLE TOP10 × IRC TOP10** (konzervativní baseline; TOP20
lze později přes `--mle-top 20` — parametr je v manifestu).

## 5. Použité filtry

`--mle-top 10  --irc-top 10  --irc-lookback 20` (defaulty skriptu).

## 6. Datumový rozsah (stav archivů z PM ZIPu 2026-07-04)

```text
MLE archiv:      2025-07-09 → 2026-06-30 (249 dní)
IRC lookback=20: 2025-06-02 → 2026-06-27 (270 dní)
průnik:          245 dní, 2025-07-09 → 2026-06-27
candidate-days:  1 144 | unikátních conid: 151 | unmapped tickerů: 0
```

Pozn.: lokální archivy PM mohou být novější — směrodatný je lokální
extraction run a jeho manifest.

## 7. Source files

Viz tabulka §1 (B1, B2, B3). Plné cesty + SHA-256 v `extraction_manifest.json`
každého extraction runu.

## 8. Source hashes

Skript počítá SHA-256 všech tří vstupů + výstupního CSV do manifestu
(reprodukovatelnost; audit runner navíc hashuje svůj input).

## 9. Forward returns

**Nebyly použity.** MLE archiv obsahuje trailing `ret_*` sloupce (vstupy
rankingu, nikoli forward returns) — do výstupu se NEPŘENÁŠEJÍ. Výstupní
schema: `conid, candidate_date, ticker, mle_rank, irc_rank,
source_signal_label` — žádný zakázaný sloupec (vynuceno testem i fail-fast
guardem audit loaderu). Manifest: `"forward_returns_used": false`.
