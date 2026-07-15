# CAP-03 Future Selection Policy — Cap Experiment Design

**Status:** návrh budoucí selection policy. NENÍ implementace.

Kontext: produkční selection / decision layer zatím NENÍ postavena
(FUTURE SCOPE / NOT BUILT). Tento dokument navrhuje, jak by cap efekt
mohl VSTUPOVAT do budoucí selection vrstvy, až vznikne — nikoli změnu
existující logiky (žádná neexistuje).

## Předpoklad použití

Cap-aware selection má smysl POUZE pokud MLE × IRC vyprodukuje VÍCE
kandidátů, než je kapacita (slots constrained). Bez omezení kapacity
nemá cap preference co řešit.

## Kandidátní pravidla (návrh, neimplementovat)

```text
A. no cap preference (baseline)
   — všichni kandidáti rovnocenní; referenční varianta

B. prefer Mega when slots constrained
   — při převisu kandidátů upřednostnit Mega bucket
   — opora: CAP-02 Mega median20 6.89 vs baseline 2.40 (in-sample)

C. de-prioritize Large-low when slots constrained
   — při převisu snížit prioritu Large-low
   — opora: CAP-02 Large-low median20 0.065 << baseline (in-sample)

D. cap-aware tie-breaker only (ne hard filter)
   — cap ovlivní pouze pořadí při shodě jiných kritérií
   — nejkonzervativnější; nevyřazuje kandidáty, jen řadí
```

## Trade-offy pravidel

```text
B (prefer Mega):
    + nejsilnější in-sample signál
    − koncentrace do málo conidů (Mega 32 conidů, AMD/MU/INTC dominují)
    − režimové riziko: mega-caps vedly tento konkrétní trh
    − hard preference = ztráta diverzifikace

C (de-prioritize Large-low):
    + Large-low je nejslabší bucket robustně
    − Large-low má nejvíc conidů (77) → velká ztráta breadth
    − caution ≠ vyřazení; hard de-prioritizace může být příliš agresivní

D (tie-breaker):
    + minimální intervence, zachovává breadth
    + nevyřazuje kandidáty
    − nejslabší efekt; může být příliš měkký na to, aby něco změnil

A (baseline):
    + žádné režimové riziko z cap preference
    − ignoruje jediný non-overlap-robustní signál nalezený dosud
```

## Podmínka nasazení KTERÉHOKOLI pravidla

```text
1. OOS potvrzení cap efektu (MRL_CAP03_MARKET_CAP_OOS_WATCH_PLAN.md)
2. existující selection layer (dosud NOT BUILT)
3. portfolio-level validace (náklady, slippage, kapacita)
4. samostatný schválený protokol
Bez všech čtyř: pravidla zůstávají výzkumným konceptem.
```

## Zakázáno (aktuální fáze)

implementovat selection layer, měnit živou selection logiku (neexistuje),
portfolio backtest, threshold optimalizace, pharma exclusion.
