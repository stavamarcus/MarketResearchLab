# KR-2026-07-EXIT-EMA-v1

**Class:** exit-validation (technical / price-based)
**Research Project:** RP-0011-EXIT-TIMING
**Experiment:** ExitTimingEdge_v1
**Status:** VALIDATED (negative result — signifikantní OPAČNÝ směr)

```yaml
kr_id:          KR-2026-07-EXIT-EMA-v1
confidence:     HIGH (v rámci běhového období)
evidence_level: B+
run_id:         68327233-5340-4f3c-847b-78e3f9dbbc37
result_hash:    863cdaf03cef893913a5
archive:        results/ExitTimingEdge/1.0.0/20260702_064905_68327233/
period:         2025-07-09 → 2026-06-29 (efektivní entries od ~11/2025, viz limitace)
universe:       MLE TOP10 × IRC TOP10 (lookback 20D)
created:        2026-07-02
supersedes:     null
```

> KR = current best knowledge, not truth.

---

## Hypotéza (pre-registrováno, zamčeno 2026-07-02, PM approval)

- **H0:** EMA20 exit nemění mean return uvnitř fixního 20D okna proti fixed 20D hold.
- **H1a:** EMA20 exit zvyšuje mean return uvnitř fixního 20D okna.

```
entry close(D) | okno fixní D→D+20 | signal close(k)<EMA20(k) | fill open(k+1)
po exitu cash 0 % | matched comparison | ticker-clustered bootstrap B=10000 seed=42
PASS ⇔ 95% CI celé > 0 | EMA10/30 sensitivity (NE hypotézy)
EMA: alpha=2/(n+1), SMA seed, warmup 90 barů (3×EMA30, společný matched set)
H1b (uncapped, time-stop 60D) exploratorní, bez kritéria
```

## Výsledek (autoritativní běh 2026-07-02)

```
N = 620 candidate-days | 116 unikátních tickerů | excluded warmup 424
H1a: paired diff -2.719pp  CI[-4.548, -1.112]  → NOT SUPPORTED
     CI celé POD nulou → validovaný negativní výsledek:
     EMA20 exit signifikantně ZHORŠUJE fixní 20D okno.
baseline TIME_20 mean: 8.572 %

Sensitivity (monotónní):
  EMA_10: -4.471pp | early exit 89.68 % | hold 10.62d
  EMA_20: -2.719pp | early exit 63.23 % | hold 14.61d
  EMA_30: -1.868pp | early exit 42.90 % | hold 16.59d
  → čím těsnější EMA, tím horší výsledek.

H1b (exploratorní): N=395, ret/den -49.4bps (metrika dominována krátkými
ztrátovými trades — neinterpretovat), time-stop jen 1.52 %.
```

## Mechanismus

Strukturálně identický s pullback entry (RP-0009): momentum leaders běžně
krátce podklesnou EMA a pokračují; exit odřezává nejsilnější pokračování
(missed winners > avoided losers). Baseline 8.57 %/20D ukazuje objem
obětovaného edge. Detailní per-variant tabulky viz archiv report.md.

## Limitace

1. **Warmup clipping (framework nález):** price provider ořezává historii
   na DATE_FROM → 90barový warmup se spotřeboval zevnitř analytického okna
   (excluded 424, efektivní entries až od ~11/2025). Čísla validní, období
   kratší. Pro budoucí experimenty s warmupem: prodloužit price window
   o buffer před DATE_FROM (backlog framework item).
2. Jedno běhové období; exit pravidla režimově citlivější než selection
   (EMA exit systematicky vyhrává v choppy/klesajícím trhu). Re-run po
   Regime Engine.
3. Entry close(D) look-ahead sdílený párem — paired diff nezkresluje.

## Důsledky

- EMA-break exit rodina pro MLE×IRC pool UZAVŘENA (analogie pullback entry).
- Nepromovat do MSL; STR-0002 nevzniká.
- ATR/Chandelier zůstávají formálně otevřené, prior snížen.
- Viz Edge Lifetime Hypothesis (KR-2026-07-EXIT-RANKLOSS-v1 §) — širší
  interpretace, proč exity uvnitř 20D selhávají.

## Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-SYNTHESIS
      note: "validovaný selection edge = vstupní pool"
    - ref: KR-2026-06-ENTRY-TIMING-v1
      note: "protokol matched comparison + mechanismus (leaders přežívají slabost)"
  inspired:
    - ref: RP-0012-LEADERSHIP-LOSS-EXIT
      note: "signálově nativní exit jako alternativa k price-based"
```
