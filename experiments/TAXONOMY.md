# MRL Experiment Classes — Taxonomy

Klasifikační pravidlo pro každou novou hypotézu:

```
Mění hypotéza:
  A) vlastnost kandidáta v D          → Feature Validation
  B) okamžik / množinu VSTUPU         → Entry Validation
  C) okamžik / podmínku VÝSTUPU       → Exit Validation
  (signál/filtr sám)                  → Selection Validation
```

## 1. Selection Validation  (`experiments/edge_validation/`)
Má signál / filtr edge? Forward returns nezávislých pozorování.
Příklady: MLE rank buckets, IRC persistence, MLE×IRC interaction/robustness, IMS score.

## 2. Entry Validation  (`experiments/entry_validation/`)
Mění vstupní timing nebo množinu realizovaných vstupů?
Příklady: close vs next-open (timing), pullback / follow-through (confirmation entry).
- Timing (množina se nemění) → matched na 100%.
- Confirmation entry (mění množinu) → matched + skipped return + strategy-level net.

## 3. Exit Validation  (`experiments/exit_validation/`)  — REZERVOVÁNO
Mění pravidlo výstupu? Trailing stop, profit target, exit na zlomení EMA.
Zatím prázdné: exit zamčen na 20D hold. Testuje se matched proti fixnímu baseline.

## 4. Feature Validation  (`experiments/feature_validation/`)
Mění vlastnosti / stratifikaci kandidátů, ale NEmění vstup ani výstup?
Podtřídy: technical (volume, ATR), fundamental (ROE, revenue — blocked: depth prereq).

---

## Vztah k MSL

MRL validuje jednotlivé komponenty (selection / entry / exit / feature).
MSL skládá VALIDOVANÉ komponenty do kompletní strategie:
    selection + entry + exit + risk + portfolio constraints.
Komponenta se do MSL promuje až po experimentálním osvědčení v MRL.

## Metodika (osvědčená praxe)

    Hypotéza → Předregistrace → Experiment → Knowledge Record → teprve pak architektura.

Negarantuje správné závěry; garantuje, že chybu odhalíme dřív, než se promítne do
architektury nebo produkční strategie.
