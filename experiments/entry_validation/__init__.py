"""
entry_validation — rodina MRL experimentů pro validaci ENTRY komponenty.

Oddělená od edge_validation (selekce). MRL zde validuje, zda ZPŮSOB VSTUPU
(timing / cesta ceny) přidává inkrementální forward-return edge nad baseline
close-entry — nezávisle na portfolio simulaci (bez capu, cash, kolizí).

Výstup těchto experimentů je entry-edge Knowledge Record, ne selection KR.
"""
