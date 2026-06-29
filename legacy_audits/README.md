# Legacy Audits — Karanténa

Audit skripty z produkčních modulů. Čekají na review a rozhodnutí o migraci do MRL.

## Pravidlo migrace

```
legacy skript → review → rozhodnutí → adaptace na BaseExperiment → validace → experiment
```

Automatická migrace je zakázána.

## Obsah

| Složka | Modul | Souborů | Kandidát pro MRL |
|---|---|---|---|
| `IMS_audit/` | InstitutionalMomentumScanner | 15 | ✅ overlap_analysis (Reference #2) |
| `IRC_audit/` | industry_rank_calendar | 16 | ✅ test_b_persistence, test_f_edge_leaderboard |
| `market_breadth_audit/` | market_breadth | 3 | ✅ decision_simulation_audit |
| `sector_rank_calendar_audit/` | sector_rank_calendar | 10 | 🔍 k review |

## Doporučení pro Reference Experiment #2

**Kandidát:** `IMS_audit/tests/overlap_analysis.py`  
Měří: IMS × MLE overlap — který signál přidává hodnotu?  
Typ: edge_validation / module_comparison  
Data: IMS archiv + MLE archiv + prices
