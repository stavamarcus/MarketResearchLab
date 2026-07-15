# SHARADAR-DATA-06-PRE2 — Split-Event Field Validation

## VERDIKT: MIXED

## ACTIONS

- columns: ['date', 'action', 'ticker', 'name', 'value', 'contraticker', 'contraname']
- split label: substring 'split'
- split eventu v obdobi: 855

### action labely (top)

- dividend: 547397
- listed: 23128
- delisted: 19138
- tickerchangeto: 13360
- tickerchangefrom: 13360
- split: 12813
- relation: 8568
- initiated: 8401
- acquisitionby: 8230
- acquisitionof: 8230
- bankruptcyliquidation: 3342
- regulatorydelisting: 867
- spinoff: 564
- spunofffrom: 564
- spinoffdividend: 520
- adrratiosplit: 380
- voluntarydelisting: 375
- mergerto: 134
- mergerfrom: 134

## Kandidati (split-event porovnani)

### CRWD (conid 370757467, split 2026-07-02)
- split_value: 4.0
- overlap_rows: 14
- best_field: closeunadj
  - close: mad=446.689143 max=572.355 match_rate=0.1429
  - closeunadj: mad=41.396429 max=579.55 match_rate=0.9286
  - closeadj: mad=446.689143 max=572.355 match_rate=0.1429

### HON (conid 4350, split 2026-06-29)
- split_value: 0.5
- overlap_rows: 14
- best_field: closeunadj
  - close: mad=208.348571 max=232.21 match_rate=0.0714
  - closeunadj: mad=0.0 max=0.0 match_rate=1.0
  - closeadj: mad=3.152071 max=3.513 match_rate=0.0714

### DD (conid 887235923, split 2026-06-24)
- split_value: 0.33333
- overlap_rows: 20
- best_field: close
  - close: mad=0.0 max=0.0 match_rate=1.0
  - closeunadj: mad=61.581 max=97.08 match_rate=0.35
  - closeadj: mad=0.0 max=0.0 match_rate=1.0

### KLAC (conid 270957, split 2026-06-12)
- split_value: 10.0
- overlap_rows: 27
- best_field: closeunadj
  - close: mad=892.776 max=2170.476 match_rate=0.5185
  - closeunadj: mad=0.0 max=0.0 match_rate=1.0
  - closeadj: mad=892.776 max=2170.476 match_rate=0.5185

### CVNA (conid 274144952, split 2026-05-08)
- split_value: 5.0
- overlap_rows: 28
- best_field: close
  - close: mad=0.001286 max=0.004 match_rate=1.0
  - closeunadj: mad=158.999286 max=333.43 match_rate=0.5
  - closeadj: mad=0.001286 max=0.004 match_rate=1.0

## best_field distribuce

{'closeunadj': 3, 'close': 2}

## Rozhodnuti pro DATA-06

- CLOSE -> DATA-06 close = Sharadar close (split-adjusted)
- CLOSEUNADJ -> DATA-06 close = Sharadar closeunadj (raw)
- NO_VALID_SPLIT_SAMPLE / MIXED / UNRESOLVED -> DATA-06 field decision je ASSUMPTION, ne fact; dokumentovat.

## Vyhrady
- split label detekce: substring 'split' nebo --split-label.
- okno kolem splitu: +-2*window kalendarnich dni (ne trading).
- match_rate: relativni diff < 0.1%.
