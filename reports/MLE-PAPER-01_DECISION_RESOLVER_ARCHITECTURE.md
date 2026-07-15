# MLE-PAPER-01 — Decision Resolver: architektura

Verze: 1.0
Datum: 2026-07-09
Návaznost: implementuje pravidla z `MLE-PAPER-01_STRATEGY_SPEC.md` v1.0
Cílová cesta: `C:\Users\stava\Projects\MarketResearchLab\reports\MLE-PAPER-01_DECISION_RESOLVER_ARCHITECTURE.md`

---

## 0. Princip

Decision Resolver je "produkční mozek", ale **hloupý ve smyslu strategie** — neobsahuje žádnou strategii ani filtry. Je to čistý VYKONAVATEL zmražených pravidel. Dostane stav světa (signály, regime, portfolio) a vyprodukuje deterministické akce.

```text
Decision Resolver = f(MLE_TOP10, regime_stav, portfolio_state) → akce[]
```

Deterministický: stejný vstup → vždy stejný výstup. Žádná náhoda, žádné skryté stavy.

---

## 1. Komponenty (moduly)

Architektura je záměrně rozdělena na malé, testovatelné moduly. Každý má jeden úkol.

```text
┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ 1. SignalSource │   │ 2. RegimeSource  │   │ 3. PortfolioState   │
│  MLE TOP10      │   │  regime200 ON/OFF│   │  positions, cash    │
└────────┬────────┘   └────────┬─────────┘   └──────────┬──────────┘
         │                     │                        │
         └─────────────────────┼────────────────────────┘
                               ▼
                  ┌────────────────────────────┐
                  │  4. DecisionResolver       │
                  │  (čistá rozhodovací logika)│
                  │  → BUY / EXIT / DO_NOTHING │
                  └─────────────┬──────────────┘
                                ▼
                  ┌────────────────────────────┐
                  │  5. OrderPlanner           │
                  │  → orders_plan_YYYY-MM-DD  │
                  └─────────────┬──────────────┘
                                ▼
                  ┌────────────────────────────┐
                  │  6. (později) Executor     │
                  │  IBKR paper broker         │
                  └────────────────────────────┘
                                
                  ┌────────────────────────────┐
                  │  7. Logger / Audit         │  ← čte ze všech
                  └────────────────────────────┘
```

---

## 2. Kontrakty mezi komponentami

Přesné datové kontrakty (co komponenta vrací). Kontrakty se zamknou, aby moduly šly testovat izolovaně.

### 2.1 SignalSource → DecisionResolver

```text
MLE_TOP10: List[{
  ticker: str,
  conid: int,
  rank_10d: int,        # 1..10
}]
seřazeno vzestupně dle rank_10d
```

### 2.2 RegimeSource → DecisionResolver

```text
Regime: {
  date: date,
  regime_on: bool,
  index_level: float,   # pro audit
  ma200: float,         # pro audit
}
```

### 2.3 PortfolioState → DecisionResolver

```text
Portfolio: {
  cash: float,
  equity: float,
  positions: List[{
    ticker: str,
    conid: int,
    shares: float,
    entry_date: date,
    entry_price: float,
    planned_exit_date: date,
    signal_rank: int,
  }]
}
```

### 2.4 DecisionResolver → OrderPlanner

```text
Decisions: List[{
  action: "BUY" | "EXIT",
  ticker: str,
  conid: int,
  quantity: float,          # BUY: spočítané shares; EXIT: držené shares
  reason: str,              # "MLE_rank_3_regime_ON" | "hold10_expired"
  price_source: str,        # "next_open"
  target_date: date,        # D+1
}]
prázdný seznam = DO_NOTHING
```

### 2.5 OrderPlanner → soubor

```text
orders_plan_YYYY-MM-DD.csv
sloupce: date,ticker,conid,action,quantity,reason,price_source
```

---

## 3. DecisionResolver — vnitřní logika (pseudokód)

Implementuje sekci 5 specu. Pořadí je závazné.

```text
function resolve(mle_top10, regime, portfolio, D_plus_1):
    decisions = []

    # KROK 1: EXITY (planned exits)
    for pos in portfolio.positions:
        if pos.planned_exit_date == D_plus_1:
            decisions.append(EXIT, pos.ticker, pos.shares,
                             reason="hold10_expired")

    # KROK 2: REGIME GATE
    if not regime.regime_on:
        return decisions   # jen exity, žádné vstupy

    # KROK 3: VSTUPY
    open_after_exits = [p for p in portfolio.positions
                        if p.planned_exit_date != D_plus_1]
    held_tickers = {p.ticker for p in open_after_exits}
    free_slots = MAX_POSITIONS - len(open_after_exits)
    if free_slots <= 0:
        return decisions

    candidates = [c for c in mle_top10 if c.ticker not in held_tickers]
    equity_now = portfolio.equity   # dle sekce 8 specu

    for cand in candidates[:free_slots]:
        target_value = 0.10 * equity_now
        spend = min(target_value, portfolio.cash_available)
        if spend <= 0:
            continue
        # quantity dopočítá OrderPlanner z open ceny D+1 (tu resolver nezná)
        decisions.append(BUY, cand.ticker, quantity=PENDING_OPEN_PRICE,
                         reason=f"MLE_rank_{cand.rank_10d}_regime_ON")
        # snížit dostupný cash pro další kandidáty (rezervace)
        portfolio.cash_available -= spend

    return decisions
```

**Poznámka ke quantity:** Decision Resolver v pořadí věcí nezná open cenu D+1 (ta je až ráno D+1). Dvě možnosti:
```text
a) resolver rezervuje HODNOTU (spend), quantity dopočítá OrderPlanner/Executor
   z reálné open ceny D+1 (quantity = spend / open_price)
b) resolver použije poslední close jako odhad, quantity se upraví při fillu

DOPORUČENÍ: (a). Resolver rozhoduje CO a ZA KOLIK HODNOTY, quantity v shares
až podle skutečné open ceny. Čistší oddělení rozhodnutí od provedení.
```

---

## 4. Determinismus a testovatelnost

```text
DecisionResolver je ČISTÁ FUNKCE:
  - žádné I/O uvnitř (nečte soubory, nevolá API)
  - dostane vstupy jako argumenty, vrátí rozhodnutí
  - stejný vstup → stejný výstup

→ jde testovat unit testy bez dat/brokera:
  test: portfolio plné (10 pozic) → žádný BUY
  test: regime OFF → jen EXITy, žádný BUY
  test: ticker už držen → nekupovat duplikát
  test: nedostatek cash → spend = cash, ne target
  test: planned_exit == D+1 → EXIT
  test: méně než 10 kandidátů → jen dostupné vstupy
```

Toto je klíčová výhoda architektury: strategie se testuje izolovaně od brokera a dat.

---

## 5. Tok jednoho dne (end-to-end)

```text
po close dne D:
  1. SignalSource.compute(D) → MLE_TOP10
  2. RegimeSource.compute(D) → regime_on
  3. PortfolioState.load()   → aktuální positions, cash, equity
  4. DecisionResolver.resolve(top10, regime, portfolio, D+1) → decisions
  5. OrderPlanner.write(decisions) → orders_plan_D+1.csv
  6. Logger.daily_report(D) → MLE-PAPER-01_DAILY_REPORT_D.md

na open D+1:
  7. (fáze 1) simulovaný fill z open D+1 → aktualizuj PortfolioState
     (fáze 2) Executor pošle paper ordery do IBKR → fill → aktualizuj state
  8. Logger.log_fills(D+1)
```

---

## 6. Fázování implementace

```text
FÁZE 1 (bez TWS) — nejdřív:
  SignalSource + RegimeSource + PortfolioState + DecisionResolver + OrderPlanner
  fill = simulovaný (open D+1 z dat, jako backtest)
  výstup: order plan + daily report + portfolio state
  cíl: ověřit, že automat přesně reprodukuje zmražená pravidla LOKÁLNĚ

  KONTROLA FÁZE 1: pusť ho na historickém období a porovnej výstup s
  MLE-BT-04 regime200 hold10. Musí sedět. Pokud sedí → logika je správná.

FÁZE 2 (IBKR paper) — až po fázi 1:
  přidat Executor (IBKR paper broker)
  read account, read positions, submit paper orders, confirm fills
  nejdřív 1 symbol test order, pak plná simulace
  POROVNAT: reálné paper filly vs simulované (jak moc se liší)

FÁZE 3 — audit:
  po 3-6 měsících: MLE-PAPER-01 audit paper výsledků vs backtest očekávání
```

**Zásadní kontrola fáze 1:** automat na historických datech MUSÍ dát stejný výsledek jako MLE-BT-04 regime200 hold10. To je test správnosti — pokud se liší, je chyba v provedení, ne ve strategii.

---

## 7. Co Decision Resolver NEDĚLÁ

```text
NErozhoduje o strategii (jen provádí zmražená pravidla)
NEpřidává filtry
NEupravuje signály
NEvolá broker přímo (to dělá Executor)
NEčte/nepíše soubory (to dělají Source/Planner/Logger)
NEobsahuje stav mezi voláními (stav drží PortfolioState)
```

Čistá funkce. Vše ostatní jsou oddělené moduly. To drží systém testovatelný a bránitelný proti "rozjetí do chaosu".

---

## 8. Návaznost — další úkol

```text
Tento dokument = architektura (design).
Další úkol (dle tvého pořadí): implementovat
  - PortfolioState (stavový soubor/model)
  - OrderPlanner (order plan bez TWS)
  - DecisionResolver (čistá logika)
BEZ napojení na TWS. Fill simulovaný.

Až fáze 1 poběží lokálně a bude sedět s MLE-BT-04 → napojit IBKR paper.
```
