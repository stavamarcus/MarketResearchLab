# Research Project: Feature Validation — Volume

```yaml
project_id:        RP-0010-FEATURE-VOLUME
portfolio_area:    Feature Quality (technical)
research_status:   TESTING
production_status: NOT_EVALUATED
created:           2026-06-30
priority:          MEDIUM
class:             feature-validation
```

## Otázka

Přidávají technické volume features inkrementální prediktivní hodnotu nad
validovaný MLE×IRC selection edge?

## Experimenty

1. **VolumeRatioEdge_v1** (F001) — Volume(D)/SMA20(Volume), spojitý target.
   Výsledek: H1 not supported (Spearman ~0). Q1 underperformance jen exploratorní.
   Viz KR-2026-06-VOLUME-RATIO-v1.

## Backlog (dceřinné hypotézy)

- **F001b Low Volume Penalty** — nízký volume ratio predikuje podprůměrný forward
  return. Samostatný předregistrovaný test, a-priori práh, NE na stejných datech.
- F002 Relative Volume, F003 Gap Size — až pokud vznikne silnější volume hypotéza.
