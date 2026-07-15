"""
exit_validation — rodina MRL experimentů pro validaci EXIT komponenty.

První třída: RP-0011-EXIT-TIMING. MRL zde validuje, zda ZPŮSOB VÝSTUPU
(dynamické exit pravidlo) realizuje větší část validovaného selection
edge než fixed hold — trade-level, matched comparison uvnitř fixního
okna, nezávisle na portfolio simulaci (bez capu, cash kolizí, sizingu).

Architektura: ExitRule (signalizace) + exit_engine (fill exekuce).
Rozšíření o novou exit logiku = nová třída v exit_rules.py.

Výstup je exit-edge Knowledge Record, ne selection KR.
"""
