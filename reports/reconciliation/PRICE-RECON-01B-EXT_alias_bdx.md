# PRICE-RECON-01B-EXT — Alias + BDX Diagnostics

## 1. Alias cases (NWS/GOOG/FOX)

### 129348130 (NWS -> NWSA)
- classification: **identity_alias_class_mismatch**
- alias_flag: COMPANY_LEVEL_ALIAS
- identity_tier: WHITELIST_COMPANY_LEVEL
- evidence: share-class alias NWS->NWSA
- source: WHITELIST

### 208813720 (GOOG -> GOOGL)
- classification: **identity_alias_class_mismatch**
- alias_flag: COMPANY_LEVEL_ALIAS
- identity_tier: WHITELIST_COMPANY_LEVEL
- evidence: share-class alias GOOG->GOOGL
- source: WHITELIST

### 356858007 (FOX -> FOXA)
- classification: **identity_alias_class_mismatch**
- alias_flag: COMPANY_LEVEL_ALIAS
- identity_tier: WHITELIST_COMPANY_LEVEL
- evidence: share-class alias FOX->FOXA
- source: WHITELIST

## 2. BDX (4886) extended ACTIONS lookup

- classification: **corporate_action_found_extended_lookup**
- bdx_ticker_rows: 124
- all labels: {'dividend': 114, 'acquisitionof': 4, 'relation': 2, 'spinoffdividend': 1, 'spinoff': 1, 'split': 1, 'initiated': 1}
- boundary: 2026-02-10

### Events v okne 2025-01..2026-07

- 2026-06-09 dividend value=1.05 contra=N/A
- 2026-03-10 dividend value=1.05 contra=N/A
- 2025-12-08 dividend value=1.05 contra=N/A
- 2025-09-08 dividend value=1.04 contra=N/A
- 2025-06-09 dividend value=1.04 contra=N/A
- 2025-03-10 dividend value=1.04 contra=N/A

### Near boundary (+-60d)

- 2026-03-10 dividend value=1.05

### Name-based hits (Becton/Dickinson/...)

- 2026-06-09 dividend BDX (BECTON DICKINSON & CO) value=1.05
- 2026-05-18 acquisitionof NBIX (NEUROCRINE BIOSCIENCES INC) value=2762.9
- 2026-04-17 listed ALMR (ALAMAR BIOSCIENCES INC) value=nan
- 2026-04-08 dividend WSBF (WATERSTONE FINANCIAL INC) value=0.17
- 2026-03-10 dividend BDX (BECTON DICKINSON & CO) value=1.05
- 2026-03-10 split ARTL (ARTELO BIOSCIENCES INC) value=0.33333
- 2026-03-04 delisted VTYX (VENTYX BIOSCIENCES INC) value=999.0
- 2026-03-04 acquisitionby VTYX (VENTYX BIOSCIENCES INC) value=999.0
- 2026-02-26 tickerchangeto RNAM (AVIDITY BIOSCIENCES INC) value=nan
- 2026-02-26 tickerchangefrom RNAM (AVIDITY BIOSCIENCES INC) value=nan
- 2026-02-26 spinoff RNAM (AVIDITY BIOSCIENCES INC) value=0.1
- 2026-02-26 delisted RNAM (AVIDITY BIOSCIENCES INC) value=11298.0
- 2026-02-26 acquisitionby RNAM (AVIDITY BIOSCIENCES INC) value=11298.0
- 2026-01-28 split REVB (REVELATION BIOSCIENCES INC) value=0.25
- 2026-01-08 dividend WSBF (WATERSTONE FINANCIAL INC) value=0.15
- 2025-12-31 dividend BOUT (INNOVATOR IBD BREAKOUT OPPORTUNITIES ETF) value=0.125
- 2025-12-08 dividend BDX (BECTON DICKINSON & CO) value=1.05
- 2025-10-30 tickerchangeto NBP (NOVABRIDGE BIOSCIENCES) value=nan
- 2025-10-30 tickerchangefrom NBP (NOVABRIDGE BIOSCIENCES) value=nan
- 2025-10-28 split ENVB (ENVERIC BIOSCIENCES INC) value=0.08333
- 2025-10-08 dividend WSBF (WATERSTONE FINANCIAL INC) value=0.15
- 2025-09-08 dividend BDX (BECTON DICKINSON & CO) value=1.04
- 2025-08-29 acquisitionof N/A (CONCENTRA BIOSCIENCES LLC) value=448.7
- 2025-08-19 acquisitionof N/A (CONCENTRA BIOSCIENCES LLC) value=216.2
- 2025-08-13 acquisitionof N/A (CONCENTRA BIOSCIENCES LLC) value=76.6
- 2025-08-13 delisted IGMS (IGM BIOSCIENCES INC) value=76.6
- 2025-08-13 acquisitionby IGMS (IGM BIOSCIENCES INC) value=76.6
- 2025-08-07 split SPRB (SPRUCE BIOSCIENCES INC) value=0.01333
- 2025-07-22 acquisitionof N/A (CONCENTRA BIOSCIENCES LLC) value=21.6
- 2025-07-08 dividend WSBF (WATERSTONE FINANCIAL INC) value=0.15

### Contraticker hits (BDX jako contra)

- ZADNE

## Vyhrady
- alias klasifikace: alias_flag=True NEBO ticker!=sharadar_ticker.
- BDX: pokud extended lookup nenajde CA, zustava needs_manual_review (cache boundary bez ACTIONS evidence).
