# MRL State Reconstruction — 2026-07-05

Handoff pro nový architektův kontext. Zdroj pravdy: soubory v repu
(docs/, results/, registry/), ne paměť. Vše mimo doložitelné artefakty
je označeno jako nejisté.

---

## 1. Fázový stav

| Fáze | Stav | Doklad |
|---|---|---|
| Adapter v1.0 (sharadar_mdsm_adapter) | CLOSED / ACCEPTED | repo, __version__ = 1.0.0 |
| MRL-FUND-00 (design) | CLOSED / ACCEPTED | 5 docs MRL_FUNDAMENTAL_* |
| MRL-FUND-01 (wrapper) | CLOSED / ACCEPTED | src/providers/sharadar_fundamental_source.py |
| MRL-FUND-02 (wiring) | CLOSED / ACCEPTED | context_builder + experiment_runner |
| MRL-FUND-03 (coverage audit) | CLOSED / ACCEPTED | MRL_FUND03_COVERAGE_AUDIT_REPORT.md, RESULT PASS |
| MRL-FUND-04 (edge protocol design) | CLOSED / ACCEPTED | MRL_FUND04_* + FUND05_EDGE_RUN_PLAN |
| MRL-FUND-05 (edge run) | CLOSED / ACCEPTED AS EVIDENCE | results/Fund05MleIrcFundamentalEdge run |
| Fundamentální entry-filter větev | PAUSED | rozhodnutí PM/architekta |
| MRL-CAP-00 (market-cap study design) | CLOSED / ACCEPTED | 5 docs MRL_CAP00..03 |
| MRL-CAP-01 (market-cap coverage audit) | IN PROGRESS | schemas rozšíření + runner + testy; NEDOKONČENO |
| CAP-02 / pharma / DR / MDSM-Lite | BLOCKED | závislé na CAP-01 |

## 2. Klíčová zamčená rozhodnutí

Adapter / PIT:
```text
PIT lookup: datekey <= candidate_date (výhradně adapter, zamčené)
snapshot pinned: sf1art_20260704_005521
    data_hash: 8438e5077ad91602215258664b257e5ece7d3c94e5fd02a329c92f46c7f436b0
    53 229 řádků; 'latest' odmítán
price-derived pole (marketcap/pe/ps/pb, EV) globálně zakázána jako features
```

Candidate-days (FUND-03, sdíleno FUND-05 i CAP):
```text
definice: MLE TOP10 × IRC TOP10 (lookback 20)
zdroj: MLE rank_matrix_archive × IRC industry_rank_calendar_archive,
    join přes sp500_rank_calendar_universe (deterministic, SHA-256 manifest)
vzorek: 1 144 candidate-days, 151 conidů, 2025-07-09 → 2026-06-27
coverage: 100 % (FUND-03 PASS)
```

FUND-04 edge protokol (pre-registrováno):
```text
fixní prahy (NE percentily — ~4,7 candidate-days/den):
    roe > 0.15, de > 2.0, composite >= 4/5
primární metrika: median 20D raw forward return
SPY-relative return = pouze sekundární diagnostika (ne acceptance)
povinná non-overlap sensitivity + dependence reporting
```

CAP-00 bucket policy (schváleno):
```text
Mega >=200B | Large-high 50–200B | Large-low 10–50B | Mid 2–10B
Small <2B | UNBUCKETED (missing/suspect)
fixní prahy, po výsledku neměnit; Small/Mid řídkost = validní výsledek
market_cap_asof = MDSM close × sharesbas(PIT)
Sharadar marketcap = pouze sanity anchor (validation-only, ne feature)
tolerance 25 %, boundary ±10 %
```

## 3. FUND-05 výsledek (akceptovaný negativní)

```text
RESULT: COMPLETED; všechny varianty B–F FAIL vs baseline
B (netinc>0 & fcf>0): horší napříč metrikami
C (revenue_yoy>0): nejblíže PASS, padl na 5/10D consistency
D (roe>0.15): median20 pod baseline
E, F: full-sample zlepšení mizí v non-overlap subsample
    (konzistentní s artefaktem opakovaných conidů, 7.58/conid)
```

KR (schváleno zapsat):
```text
"Simple absolute fundamental filters did not robustly improve
MLE TOP10 × IRC TOP10 at 5–20D horizon in this in-sample protocol."
Evidence level: B (in-sample, protocol-valid, dependence-adjusted,
not OOS-confirmed)
Jediný kandidát pro budoucí OOS watch: varianta C (bez přeladění prahů)
```

Metodická výhrada (platí i pro budoucí směr): FUND-05 měřil varianty
PROTI baseline, ne baseline proti nule. Edge samotného MLE×IRC baseline
NENÍ tímto runem OOS-potvrzen.

## 4. CAP-01 — přesný stav rozpracování

Hotovo (sandbox, netestováno reálným snapshotem):
```text
schemas.py: append-only rozšíření (+sharesbas, +sharefactor) — SCHVÁLENO
    adapter suite 141 passed / MRL suite 71 passed
run_cap01_field_gate.py (Úkol 0, read-only)
run_cap01_market_cap_audit.py (Úkoly 1–5)
tests/test_cap01_audit.py — 27 passed (14 požadovaných scénářů + rozšíření)
```

Zbývá:
```text
docs/MRL_CAP01_COVERAGE_AUDIT_REPORT.md (skeleton s tolerancí)
delivery ZIP + completion report
reálný běh u PM: field gate → audit; screenshoty
```

Otevřený technický risk (nutno ověřit reálným snapshotem):
```text
sharesbas v snapshotu = předpoklad (grep build_snapshot.py naznačuje ano,
    ale NEOVĚŘENO na reálných datech) → field gate to rozhodne
pokud sharesbas chybí → CAP-01 STOP (žádný fallback, žádný rebuild)
pokud sharefactor chybí → schemas rozšíření rozbije fields=None cesty
    nad reálným snapshotem → eskalace k PM
```

## 5. Otevřený rozhodovací bod (vyžaduje architekta)

```text
A) dokončit CAP-01 → CAP-02 (market-cap diferenciace) dle plánu
B) přesměrovat na OOS/robustness validaci samotného MLE×IRC baseline
   (chybějící krok před jakýmkoli produkčním systémem nad výstupem)
C) systém nad MLE×IRC výstupem — předčasné bez B
```

Doporučení implementera: pořadí A → B → C. CAP-01 je těsně před
dokončením; přerušení uprostřed zanechá schemas.py změněné bez uzavřené
fáze. Rozhodnutí je na PM + architektovi.

## 6. Reprodukovatelnost / cesty

```text
adapter repo: C:\Users\stava\Projects\sharadar_mdsm_adapter
adapter data: C:\Users\stava\Projects\sharadar_mdsm_adapter_data (mimo git)
MRL:          C:\Users\stava\Projects\MarketResearchLab
candidate-days: results\diagnostics\fund03_candidate_days_20260704_225140\
FUND-05 run:  results\Fund05MleIrcFundamentalEdge\1.0.0\20260704_233827_c9831d5a\
env: market_research_lab (MRL) / sharadar_mdsm_adapter (adapter)
```

## 7. Nejisté / nedoložitelné

```text
- ústní/nezaznamenaná architektova schválení mimo docs/ = ztracená,
  nelze rekonstruovat
- FUND-05 known bug "feature whitelist: None" v reportu (kosmetické,
  schváleno opravit později bez re-run) — oprava dosud neprovedena
- archive_manager.py UTF-8 fix: schváleno jako post-FUND-05 infra fix
```
