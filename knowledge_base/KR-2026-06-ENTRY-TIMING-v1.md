# KR-2026-06-ENTRY-TIMING-v1

**Class:** entry-edge (NE selection-edge)
**Research Project:** RP-0009-ENTRY-TIMING
**Experiment:** EntryTimingEdge_v1
**Status:** VALIDATED (autoritativní framework běh)

```yaml
run_id:       df22ba65-4b2d-47c8-b77b-907f91e5eb7a
result_hash:  5bf2b910868f0e7bf6c8
archive:      results/EntryTimingEdge/1.0.0/20260701_021010_df22ba65/
period:       2025-07-09 → 2026-06-27
universe:     MLE TOP10 × IRC TOP10 (lookback 20D)
created:      2026-06-30
```

> KR = current best knowledge, not truth. Nikdy nemazat; superseded, ne rewritten.

---

## Otázka

Přidává ZPŮSOB VSTUPU (čekání na cenový pullback) inkrementální forward-return
edge nad baseline close-entry, nad množinou MLE×IRC kandidátů — nezávisle na
portfolio simulaci (bez capu, cash, kolizí)?

## Pre-registrované parametry (zamčeno a priori 2026-06-30)

```
MLE_TOP=10  IRC_TOP=10  IRC_LOOKBACK=20  HOLD=20D
ENTRY_001 baseline   : buy close v den signálu
ENTRY_002 1 pullback : první close < prev, wait=5, entry=close pullback dne
ENTRY_003 2 pullbacks: dva PO SOBĚ jdoucí poklesy, wait=7, flat(==) přerušuje
MIN_FUTURE_DAYS=27 (common completable subset)
signifikance: ticker-clustered bootstrap (B=2000, seed=42)
regime split: DEFERRED
forward return = close[entry+20]/close[entry]-1; baseline pro alpha = ENTRY_001
```

## Výsledky (autoritativní běh, N=1015 candidate-days, 142 unikátních tickerů)

| varianta | matched entry alpha | 95% CI (ticker-clustered) | strategy-level net | fill |
|---|---|---|---|---|
| ENTRY_001 (baseline) | — | — | +7.15 % (ref) | 100 % |
| ENTRY_002 (1 pullback) | +0.13 pp | [-0.49, +0.82] — **nesignif.** | -0.42 pp | 97.5 % |
| ENTRY_003 (2 pullbacks) | +3.19 pp | [+1.98, +4.43] — **signif.** | **-2.38 pp** | 68.9 % |

Skipped baseline return: K3 (přeskočené ENTRY_003) **+14.7 %** vs S3 (vstoupené) **+3.73 %**.

---

## Závěry

**1. Close-entry NENÍ „vítěz" — je to zatím neporažený baseline.**
Data neukázala, že close-entry je optimální nebo lepší. Ukázala, že dvě konkrétní
pullback alternativy jsou vůči němu horší. Close-entry nesoutěžil; byl referenční
bod, který dva vyzyvatelé nepřekonali. Navíc nese caveat baseline look-ahead (vstup
na close, z něhož je signál počítán → mírně nadhodnocen). Pozice close-entry je tedy
„neporažený dvěma slabými vyzyvateli", ne „prokázaně nejlepší".

**2. Ani First Pullback ani Two Consecutive Pullbacks se NEPROMUJÍ do MSL.**
Obě mají negativní strategy-level net vůči baseline. Žádná není doporučena jako
entry komponenta pro MSL strategie na základě tohoto datasetu.

**3. Two Pullbacks mají signifikantní conditional entry alpha, ale strategy-level je
negativní kvůli zmeškaným nejsilnějším moverům.**
ENTRY_003: matched alpha +3.19 pp (CI vylučuje nulu) — na jménech, kde vstoupí, je
vstupní cena reálně lepší. Ale strategy-level -2.38 pp, protože 31 % kandidátů
přeskočí, a přeskočené (K3 +14.7 %) jsou násobně silnější než vstoupené (S3 +3.73 %).
Conditional alpha je survivorship — platí jen na slabších, couvajících jménech; nikdy
nedožene přeskočené silné movery. (Vyšší win rate ENTRY_003 potvrzuje: vyhrává častěji,
míjí velké výhry.)

**4. Mechanismus „momentum impulse pokračuje bez pullbacku" zůstává HYPOTÉZA.**
Změřený fakt: přeskočení kandidáti měli vyšší baseline forward return (K3 +14.7 % vs
S3 +3.73 %). Interpretace, že MLE×IRC nachází akcie uprostřed silného impulsu, který
pokračuje bez oddechu, je konzistentní a pravděpodobná, ale experiment ji přímo
neměřil. Označeno jako pracovní hypotéza, ne prokázaný mechanismus.

**5. Další entry kandidáti mají být CONTINUATION, ne reverzní pullback.**
Otevřené alternativy se dělí na dvě třídy:
- Reverzní / oddechové (pullback, mírněji inside-day-jako-oslabení) — čekají na
  slabost → tato třída je tímto experimentem varována (deselektuje nejsilnější jména).
- Kontinuační (next-open, průraz krátké báze / ORB) — jdou po síle → experimentem
  NEzasaženy, mechanicky konzistentní s pozorováním.

Priorita dalších experimentů: **next-open první** (D1-testovatelný hned, žádná intraday
data, kontinuační), pak průraz báze (potřebuje definici báze), inside-day/konsolidace
níž (reverzní příchuť → opatrnost). Pořadí plyne z tohoto nálezu.

**6. Regime split je DEFERRED.**
Chybí schválené režimové štítky. Verdikt je vázaný na jedno běhové období (2025-07 →
2026-06, pravděpodobně bull/momentum režim), kde je míjení trendu nejdražší. Entry-edge
je režimově citlivý — v choppy/mean-reverting režimu se verdikt může obrátit (pullback
by tam mohl pomáhat). Nutný re-run se stratifikací, až vznikne schválený Regime Engine.

---

## Disproved / Not supported

- **Not supported:** čekání na první ani druhý pullback nepřineslo lepší výsledky než
  okamžitý close-entry u MLE×IRC momentum leaderů v období 2025-07 → 2026-06 (strategy-level).
- **ENTRY_002 entry alpha:** no evidence (CI přes nulu).
- **ENTRY_003 jako promovatelná strategie:** disproved na strategy-level (conditional
  alpha ANO, ale net negativní).

## Caveats / hranice platnosti

- **Rozsah:** platí pro MLE×IRC momentum leadery, období 2025-07 → 2026-06, hold 20D,
  pullback definice výše. Neextrapolovat mimo tento rozsah.
- **Dependence:** nominal N=1015, unikátních tickerů=142 (poměr 0.14) → efektivní N <<
  nominal. Signifikance výhradně z ticker-clustered bootstrapu. Naivní t-test/win-rate
  NEPOUŽÍVAT.
- **Baseline look-ahead:** ENTRY_001 vstup na close signálu (konzistentní s předchozími
  MRL audity, mírně nadhodnocuje baseline).
- **Skipped/entered magnitudy** jsou nejcitlivější na tail dat (K3 ~314 pozorování);
  poměr (~4×) a směr jsou robustní, absolutní hodnoty méně.

---

## Navazující (samostatné, předregistrované experimenty)

- **Next-open entry** (D1, kontinuační) — nejvyšší priorita, nejlevnější.
- Průraz krátké báze / ORB (kontinuační; ORB potřebuje intraday data — vázáno na
  dormant intraday osu).
- Re-run se stratifikací režimů, až budou schválené štítky.
- **Fundamentální větev** (Sharadar features) — otevřít až potom, a to jako
  **MRL fundamental-feature validation** (nová feature class + Sharadar provider),
  NE jako samostatný „Leader DNA" projekt. Pozor na hloubku: MLE×IRC candidate pool
  je ~1 rok, Sharadar 25 let to neobejde.
