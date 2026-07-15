"""
feature_validation — rodina experimentů validujících VLASTNOSTI kandidátů.

Feature = vlastnost kandidáta v den D, která NEMĚNÍ vstup ani výstup ani množinu
(matched triviálně na 100% množině). Podtřídy:
  - technical:   volume ratio, ATR, ...
  - fundamental: ROE, revenue growth, ... (blocked — depth prerequisite)

Otázka: přidává feature X inkrementální forward-return edge nad MLE×IRC?
První plánovaný: Volume Ratio = Volume(D) / SMA20(Volume).

POZOR: confirmation entries (follow-through, pullback) sem NEPATŘÍ — mění okamžik/
množinu vstupu → to je Entry Validation.
"""
