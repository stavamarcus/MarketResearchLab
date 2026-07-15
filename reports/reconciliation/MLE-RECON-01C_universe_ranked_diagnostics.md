# MLE-RECON-01C — Universe / Ranked Diagnostics

## 1. Input window

- MLE original: run_date - 45 kalendarnich dni (extended_start .. run_date)
- MLE-RECON-01: cela DATA-06 serie per ticker (bez oriznuti okna)
- rozdil: recon posila FULL series, MLE original 45d slice
- **METHODOLOGICAL_DIFFERENCE_RECON**
- poznamka: recon full-series muze dat rank tickerum, ktere MLE original v 45d okne vyloucil (nedostatek historie) -> ranking universe mismatch

## 2. recon_only tickery

### BF.B
- conid: 4931
- in_universe: True, active: True, order: 76
- data06: exists=True range=1997-12-31..2026-07-02 rows=7169
- mdsm_cache: exists=True range=2024-07-01..2026-07-02 rows=503
- in_archive: True
- alt_formats_in_archive: {'BF-B': False, 'BFB': False, 'BF.B': True}

### BRK.B
- conid: 72063691
- in_universe: True, active: True, order: 61
- data06: exists=True range=1997-12-31..2026-07-02 rows=7169
- mdsm_cache: exists=True range=2024-07-01..2026-07-02 rows=503
- in_archive: True
- alt_formats_in_archive: {'BRK-B': False, 'BRKB': False, 'BRK.B': True}

### EXE
- conid: 470458975
- in_universe: True, active: True, order: 187
- data06: exists=True range=2021-02-10..2026-07-02 rows=1354
- mdsm_cache: exists=True range=2025-12-15..2026-05-12 rows=102
- in_archive: False
- alt_formats_in_archive: {}

### PSKY
- conid: 804144296
- in_universe: True, active: True, order: 358
- data06: exists=True range=1997-12-31..2026-07-02 rows=7169
- mdsm_cache: exists=True range=2025-12-15..2026-05-12 rows=102
- in_archive: False
- alt_formats_in_archive: {}

### Q
- conid: 824788107
- in_universe: True, active: True, order: 385
- data06: exists=True range=2025-11-03..2026-07-02 rows=166
- mdsm_cache: exists=True range=2025-10-27..2026-05-12 rows=136
- in_archive: False
- alt_formats_in_archive: {}

### SNDK
- conid: 760250490
- in_universe: True, active: True, order: 404
- data06: exists=True range=2025-02-24..2026-07-02 rows=341
- mdsm_cache: exists=True range=2025-12-15..2026-05-12 rows=102
- in_archive: False
- alt_formats_in_archive: {}

## 3. Per-date check (full vs sliced)

- clean_day: 503 full ranked, 503 sliced ranked
- full_only_ranked (rank ve full, ne ve sliced): []

### recon_only detail (full vs sliced rank)

- BF.B: full_rank=445 sliced_rank=445 days_full=7098 days_sliced=33
- BRK.B: full_rank=199 sliced_rank=199 days_full=7098 days_sliced=33
- EXE: full_rank=66 sliced_rank=66 days_full=1283 days_sliced=33
- PSKY: full_rank=502 sliced_rank=502 days_full=7098 days_sliced=33
- Q: full_rank=148 sliced_rank=148 days_full=95 days_sliced=33
- SNDK: full_rank=1 sliced_rank=1 days_full=270 days_sliced=33

## Zaver

- pokud full_only_ranked obsahuje recon_only tickery -> potvrzeno: full-series rezim dava rank tickerum, ktere sliced (MLE original) vyloucil.
- oprava: MLE-RECON musi orezavat na 45d okno jako MLE original,
  NEBO rangovat jen pres archive-ranked tickery per den.

## Vyhrady

- alt ticker formaty: kontrolovany BRK.B/BRK-B/BRKB, BF.B/BF-B/BFB.
- sliced rezim: 45 KALENDARNICH dni (jako MLE start_buffer).
