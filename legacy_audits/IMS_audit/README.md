# IMS Audit — Legacy Scripts

**Projekt:** InstitutionalMomentumScanner  
**Status:** KARANTÉNA — čeká na review a rozhodnutí o migraci  
**Přesunuto do MRL:** 2026-06-29

---

## Přehled verzí

| Soubor | Verze | Co přidává |
|---|---|---|
| `entry_points/run_audit_v1.py` | v1 | Základ: return analysis + relative performance |
| `entry_points/run_audit_v2.py` | v2 | + fine score buckets, component profile |
| `entry_points/run_audit_v3.py` | v3 | + IMS × MLE overlap analysis |
| `entry_points/run_audit_v4.py` | v4 | + MLE diagnostic (proč MLE TOP50 > IMS×MLE) |
| `entry_points/run_audit_v5_mle_top80.py` | v5 | + PRE-LEADER band optimization (Test E) |

---

## Testovací moduly

| Soubor | Sekce | Měří |
|---|---|---|
| `tests/return_analysis.py` | B | Forward returns per score bucket (RADAR/H70/H80/H90/H95+) |
| `tests/relative_performance.py` | C | Alpha vs SPY per bucket a window |
| `tests/fine_score_buckets.py` | E | Returns per 5-bodový bucket (60–64, 65–69, ...) |
| `tests/component_profile.py` | F | Průměr scoring komponent per bucket |
| `tests/component_quintiles.py` | G | Prediktivní síla každé komponenty (kvintilová analýza) |
| `tests/overlap_analysis.py` | — | IMS only / MLE only / IMS∩MLE porovnání |
| `tests/mle_diagnostic.py` | A–D | Proč MLE TOP50 > IMS×MLE overlap |

## Infrastruktura

| Soubor | Zodpovědnost |
|---|---|
| `infrastructure/data_loader.py` | IMS archiv + MDSM close prices → AuditData |
| `infrastructure/forward_returns.py` | 5D/10D/20D/30D forward returns + alpha vs SPY |
| `infrastructure/report_writer.py` | Zápis textového reportu |

---

## Rozhodnutí o migraci (zatím neprovedeno)

| Test | Typ | Doporučení |
|---|---|---|
| return_analysis | edge_validation | **MIGROVAT** — měří obchodní hodnotu IMS signálu |
| relative_performance | edge_validation | **MIGROVAT** — alpha vs SPY = edge test |
| fine_score_buckets | edge_validation | **MIGROVAT** — granulární edge analýza |
| component_quintiles | hypothesis_testing | **MIGROVAT** — prediktivní síla komponent |
| overlap_analysis | module_comparison | **MIGROVAT** — IMS vs MLE porovnání |
| mle_diagnostic | hypothesis_testing | **MIGROVAT** — vysvětlení MLE dominance |
| component_profile | hypothesis_testing | ZVÁŽIT — popisná statistika, ne přímý edge test |

**Kandidát pro Reference Experiment #2:** `overlap_analysis` (IMS × MLE) —  
jasná hypotéza, existující logika, měří edge kombinace signálů.
