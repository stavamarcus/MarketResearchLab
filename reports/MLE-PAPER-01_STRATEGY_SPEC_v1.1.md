# MLE-PAPER-01 — Strategy Specification v1.1 (kauzálně opravený executable spec)

Verze: 1.1
Datum: 2026-07-14
Status: **APPROVED / FROZEN** — zdroj pravdy pro Decision Resolver (nahrazuje v1.0). Schváleno architektem 2026-07-14 po review. Žádná změna bez explicitního rozhodnutí + verzování.
Cílová cesta: `C:\Users\stava\Projects\MarketResearchLab\reports\MLE-PAPER-01_STRATEGY_SPEC_v1.1.md`
Vztah k v1.0: v1.0 (`MLE-PAPER-01_STRATEGY_SPEC.md`) zůstává beze změny jako historický frozen spec podle původní evidence (MLE-BT-04). Tato v1.1 je kauzálně opravený executable spec podle MLE-BT-04R a MLE-BT-05.

---

## 0. Účel dokumentu

Přesná, jednoznačná pravidla zmražené strategie MLE-PAPER-01 pro automatizované paper provedení. Decision Resolver a všechny navazující komponenty MUSÍ implementovat POUZE tato pravidla. Žádná nová strategie, žádné nové filtry.

Pokud kód a tento dokument nesouhlasí, platí dokument. Změna pravidla = nová verze specu + záznam důvodu.

**Kauzální acceptance criterion (závazné pro veškerý kód):** každé rozhodnutí prováděné na open dne X smí používat pouze informace známé nejpozději po close dne X-1.

---

## 0a. Changelog v1.0 → v1.1

```text
C-1  Odstraněn vnitřní rozpor v1.0 (§2/§5.1 „EXIT na open D+1" vs §9
     „exit na close"): závazně EXIT = close planned_exit_date, shodně
     s backtest kódem. BUY = open D+1. [zdroj: BT-04R verifikace]
C-2  Doplněna kauzální pravidla exekuce: regime z close D (ne D+1);
     cash a slot z exitu dostupné až následující obchodní den;
     pending-exit pozice drží slot; ticker s pending exitem není
     tentýž den znovu koupitelný. [zdroj: MLE-BT-04R, nálezy D1+D2]
C-3  RB-1 až RB-6 uzavřeny (viz §12). [rozhodnutí architekta 2026-07-14]
C-4  Kontrakty upřesněny: BUY nese target_value (ne quantity);
     EXIT nese quantity; cash_available je pouze lokální proměnná
     resolveru; resolver nesmí mutovat vstupní PortfolioState.
C-5  Baseline nahrazena: MLE-BT-04R NEW (kauzální) místo MLE-BT-04.
     Původní 375.283 % bylo částečně artefakt lookaheadu a nemožné
     cash/slot chronologie. Nová auditní baseline viz §13.
C-6  Zdůvodnění regime200 přepsáno poctivě (viz §13.2): regime200
     NENÍ alpha enhancer; je to drawdown-control overlay za cenu
     nižšího CAGR/Sharpe.
C-7  hold10 potvrzen testem MLE-BT-05; hold12 zamítnut (viz §13.3).
C-8  Výpočet regime indexu explicitně zafixován (fill_method=None,
     skipna, log valid constituents) — viz §4.
C-9  Doplněny výhrady k evidenci (§13.4) včetně zákazu používat
     Calmar jako rozhodovací metriku do ověření výpočtu/škálování.

Referenční reporty:
  reports/backtests/MLE-BT-04R_causal_execution_correction.{md,json}
  reports/backtests/MLE-BT-05_hold_sensitivity.{md,json}
```

---

## 1. Definice a datové zdroje

```text
DATA-06:      C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\
              sharadar_full_equity_v20260705_01\derived\mdsm_price_view
              {conid}_D1.parquet, DatetimeIndex, OHLCV (open,high,low,close,volume)
universe:     C:\Users\stava\Projects\MDSM-Lite\data\universe\
              sp500_rank_calendar_universe.csv (conid,ticker,active_flag,sector,industry)
              → jen active_flag = true (503 tickerů, FROZEN — viz RB-3)
MLE engine:   compute_rank_matrix(close_prices, instruments, target_date, lookbacks)
LOOKBACKS:    [1,2,3,4,5,6,7,8,9,10,20]
```

**Zdroj cen (RB-1, UZAVŘENO):**

```text
Fáze 1 (replay, bez TWS):  DATA-06 mdsm_price_view — POVINNĚ.
    Důvod: kontrola správnosti Fáze 1 = reprodukce MLE-BT-04R;
    jiný zdroj cen by reprodukci znemožnil.
Fáze 2 (IBKR paper):       MDSM-Lite / IBKR daily cache, ale POUZE
    po úspěšném Signal Parity Testu (viz §14).
```

---

## 2. Definice obchodního dne a časování

```text
D    = signální den (obchodní den, po jehož close se počítá MLE rank + regime)
D+1  = následující obchodní den (kdy se VSTUPUJE na open)

Časová osa jednoho cyklu (kauzální, závazná):
  po close dne D (z finálních denních dat — RB-2, UZAVŘENO):
    1. spočítej MLE rank matrix z dat do D včetně
    2. spočítej regime200 stav pro D (regime_ON[D])
    3. aktualizuj portfolio stav podle close D (exity provedené na close D)
    4. Decision Resolver vytvoří order plan pro D+1
  na open D+1:
    5. provedou se BUY (nové vstupy) na open, price_source = next_open
  na close planned_exit_date (každé pozice):
    6. provede se EXIT na close, price_source = close

Cash a slot z EXITu na close dne X jsou dostupné až pro vstupy
na open dne X+1 (následující obchodní den). Nikdy tentýž den.
```

Poznámka: v1.0 zde uváděla „EXIT na open D+1" — to bylo v rozporu s §9 v1.0 i s backtest kódem a je tímto opraveno (C-1).

---

## 3. Výpočet MLE signálu (výběr TOP10)

```text
vstup:   close ceny všech 503 active tickerů, okno [D-45 kalendářních dní, D]
         (start_buffer 45 dní zajistí dost dat pro lookback 20)
compute: rm = compute_rank_matrix(close_prices, instruments, D, LOOKBACKS)
signál:  MLE_TOP10 = {ticker : rank_10d <= 10}
         seřazeno vzestupně dle rank_10d (rank 1 = nejsilnější)
NaN:     ticker s rank_10d = NaN se ignoruje (nedostatek historie)
```

Výstup: seřazený seznam `[(ticker, rank_10d), ...]` délky <= 10.

Poznámka: tickery s nedostatečnou historií (EXE, PSKY, Q, SNDK v době backtestu) mohou mít NaN — to není chyba, ignorují se.

---

## 4. Výpočet regime200 (explicitně zafixováno — C-8)

```text
krok 1: denní výnos každého tickeru:
          rets = close.pct_change(fill_method=None)
          — ŽÁDNÝ implicitní forward fill cen; chybějící cena = NaN výnos
krok 2: market_daily_return[t] = průměr denních výnosů přes dostupné
          tickery: rets.mean(axis=1, skipna=True)
          — NaN se PŘESKAKUJÍ (explicitní pravidlo, shodné s BT-04R)
krok 3: index_level[t] = kumulativní součin (1 + market_daily_return),
          start 1.0; den bez jediného validního výnosu → výnos 0
krok 4: MA200[t] = průměr index_level za posledních 200 obchodních dní
          (min_periods = 200)
krok 5: regime_ON[D] = index_level[D] > MA200[D]

logging: počet validních constituentů se loguje každý den
         (referenční rozsah z BT-04R: min 492, max 503, medián 498)

edge case: pokud MA200 není k dispozici (< 200 dní historie) → regime_ON = True
           (neblokovat). V paper nenastane — historie je dlouhá.
kauzalita: regime_ON[D] používá jen data do close D včetně. Pro vstupy
           na open D+1 se používá regime_ON[D], NIKDY regime_ON[D+1].
```

**Universe pro index (RB-3, UZAVŘENO):** fixed frozen universe = stejných 503 active tickerů jako v backtestu, se stejnou historií pro MA200. Žádná dynamická S&P rebalance ve verzi MLE-PAPER-01. Dynamické universe = budoucí verze strategie, ne baseline. Delisting uvnitř frozen universe → NaN → přeskakuje se dle kroku 2 (zafixované pravidlo, ne náhodná vlastnost knihovny).

---

## 5. Rozhodovací logika (Decision Resolver)

Decision Resolver je čistá deterministická funkce. Běží po close dne D a produkuje akce pro D+1. Nesmí číst soubory, volat broker/API ani mutovat vstupy. Pořadí zpracování je závazné:

### 5.1 Krok 1 — EXITY (planned exits)

```text
pro každou otevřenou pozici:
  pokud planned_exit_date == D+1:
    → akce EXIT na CLOSE dne D+1, price_source = close,
      quantity = skutečně držené shares pozice
```

Pozice s exitem na close D+1 se pro účely kroku 3 STÁLE počítá jako otevřená (drží slot, její cash není dostupný, její ticker není koupitelný).

### 5.2 Krok 2 — REGIME GATE

```text
regime_ON[D] = výpočet dle sekce 4 (z close D — kauzálně)
pokud regime_ON == False:
  → ŽÁDNÉ nové vstupy pro D+1 (exity z kroku 1 se provedou vždy)
  → přeskoč krok 3
pokud regime_ON == True:
  → pokračuj na krok 3
```

### 5.3 Krok 3 — VSTUPY (new entries)

```text
free_slots = MAX_POSITIONS (10) - počet VŠECH otevřených pozic
             (VČETNĚ pozic s exitem plánovaným na close D+1 — jejich
             slot se uvolní až pro D+2)
pokud free_slots <= 0:
  → žádné nové vstupy (portfolio plné)
jinak:
  equity = cash + mark-to-market otevřených pozic za close D
  cash_available = cash          (LOKÁLNÍ proměnná resolveru;
                                  neobsahuje proceeds z exitů D+1)
  kandidáti = MLE_TOP10 seřazení dle rank_10d
  vyluč tickery, které už držím (včetně pending-exit) — žádné duplicity
  vezmi prvních free_slots kandidátů
  pro každého (v pořadí rank):
    target_value = 10 % equity
    spend = min(target_value, cash_available)
    pokud spend <= 0: přeskoč (nedostatek cash)
    → akce BUY na open D+1, price_source = next_open,
      target_value = spend        (quantity se určí až z open ceny D+1)
    cash_available -= spend       (kaskádová rezervace přes více BUY)
```

### 5.4 Výstup Decision Resolveru

```text
pro každou akci: {BUY | EXIT}, ticker, conid, reason, price_source,
  BUY:  target_value, target_date = D+1 (fill na open)
  EXIT: quantity,     target_date = planned_exit_date (fill na close)
pokud žádná akce: DO_NOTHING
```

Resolver NIKDY nemutuje vstupní PortfolioState. Aktualizaci stavu provádí navazující vrstva až podle skutečných fillů.

---

## 6. Výpočet planned_exit_date

```text
při vstupu (entry na open D+1):
  entry_trading_day = D+1
  planned_exit_date = 10. obchodní den PO entry_trading_day
                    = entry_trading_day + 10 obchodních dní
                    (počítáno přes obchodní kalendář, ne kalendářní dny)
  exit se PROVÁDÍ na CLOSE planned_exit_date (viz §2, §5.1)

příklad: entry v pondělí → exit na close 10. obchodního dne poté
         (obvykle za 2 týdny, přeskakuje víkendy a svátky)
```

**Obchodní kalendář (RB-4, UZAVŘENO):**

```text
Fáze 1 (replay):  obchodní dny dle DATA-06 price indexu
                  (shodně s BT-04R sim_dates — nutné pro reprodukci)
Fáze 2 (paper):   NYSE trading calendar (víkendy + burzovní svátky)
```

---

## 7. Ošetření hraničních stavů

```text
regime OFF + otevřené pozice (RB-5, UZAVŘENO):
  → DRŽ pozice do jejich planned_exit_date (konzistentní s backtestem)
  → regime blokuje jen NOVÉ vstupy, ne exity existujících
  Alternativa (nezavedeno): zavírat pozice hned při regime OFF — TO BY
  BYLA ZMĚNA STRATEGIE, ne baseline.

ticker už otevřený + znovu v TOP10:
  → NEotevírat druhou pozici. Držet stávající do planned_exit_date.

ticker s exitem na close D+1 + znovu v TOP10 pro open D+1:
  → NEkupovat na open D+1 (pozice je na open stále držena).
    Koupitelný nejdřív na open D+2, pokud je znovu v signálu z D+1.

nedostatek cash na plnou pozici:
  → koupit za dostupný cash_available (spend = min(target_value, cash_available))
  → pokud spend <= 0, přeskočit tento ticker
  → proceeds z exitů na close D+1 NEJSOU pro open D+1 dostupné

open cena chybí (D+1):
  → pozice se neotevře (skip). Zalogovat jako warning.

exit — close cena chybí:
  → Fáze 1 (replay): fallback = entry cena POUZE jako BT-04R-compatible
    reproduction mechanism, NE obecné obchodní pravidlo; každý případ
    musí být zalogován jako data warning.
  → Fáze 2: missing close/fill = incident, ŽÁDNÝ fallback.

MLE_TOP10 má méně než 10 tickerů:
  → vstoupit jen do dostupných. Zbytek zůstává cash.

signál generuje víc kandidátů než free_slots:
  → vzít nejlepší MLE rank (kandidáti jsou seřazení). Zbytek zahodit.
```

---

## 8. Stavový model (paper portfolio state)

Perzistentní stav, který systém udržuje mezi dny (Fáze 1: JSON nebo Parquet/CSV, ne databáze):

```text
positions[]:
  ticker
  conid
  shares (quantity)       — skutečné, určené až z fill ceny
  entry_date
  entry_price
  planned_exit_date
  signal_rank             (MLE rank_10d při vstupu)
  regime_at_entry         (True — vždy True, vstup jen při regime ON)
  status                  (OPEN | CLOSED)

account:
  cash
  equity                  (cash + mark-to-market pozic)
  last_updated_date

historie:
  closed_trades[]         (pro audit: entry/exit date, price, pnl, reason)
```

Invarianty (musí platit vždy):
```text
- počet OPEN pozic <= 10
- cash >= 0
- žádné dvě OPEN pozice se stejným tickerem
- equity = cash + suma(shares × aktuální close)
- PortfolioState mutuje POUZE stavová vrstva podle fillů;
  Decision Resolver stav pouze čte (C-4)
```

---

## 9. Fill logika pro paper (RB-6, UZAVŘENO)

```text
Fáze 1 (replay / order planner bez TWS):
  simulovaný fill konzistentní s backtestem:
    entry = open[D+1], exit = close[planned_exit_date]
    náklady 15 bps round-trip (7.5 bps na každé straně), žádná další slippage
  BUY quantity = spend / (open_price × (1 + 7.5bps))

Fáze 2 (IBKR paper):
  skutečné paper ordery, reálné (paper) fill ceny
  POVINNÉ MĚŘENÍ: porovnat actual fill vs simulated fill
  (rozdíl v bps je klíčový vstup — BT-05 ukázal citlivost
  ~4.5–5 pb CAGR na každých +15 bps nákladů)
```

Náklady: 15 bps round-trip (half na každé straně) — konzistentní s backtestem.

---

## 10. Logging (co se loguje)

```text
každý den:
  regime_ON stav + index_level + MA200 + počet validních constituentů
  MLE_TOP10 (ticker, rank)
  Decision Resolver akce (BUY/EXIT/DO_NOTHING) + reason + price_source
  order plan (pokud nějaký)
  portfolio state (positions, cash, equity, exposure)
  rule violations / warnings (nedostatek cash, chybějící cena, atd.)

každý fill:
  ticker, action, quantity, fill_price, timestamp, planned vs actual
```

---

## 11. Co tento spec NEOBSAHUJE (vědomě)

```text
BEZ stop-loss
BEZ dual-MA (backlog R&D-IDEA-01)
BEZ IRC (hard filtr ani váha)
BEZ výběrových filtrů (cena/volatilita/historie/rank sizing)
BEZ dynamického hold periodu (hold12/hold14 zamítnuty — viz §13.3)
BEZ dynamického universe (S&P rebalance = budoucí verze)
BEZ tranšování vstupů / rozkládání exitů (výzkumný backlog, ne baseline)
BEZ live tradingu (jen paper)
BEZ ML / optimalizace
```

Jakékoli z výše uvedeného = ZMĚNA STRATEGIE, vyžaduje novou verzi specu a rozhodnutí, ne tichou úpravu kódu.

---

## 12. Rozhodovací body RB-1 až RB-6 — UZAVŘENO (C-3)

Rozhodnuto architektem 2026-07-14 po MLE-BT-04R:

```text
RB-1  Zdroj cen: Fáze 1 = DATA-06 (povinně, kvůli reprodukci BT-04R);
      Fáze 2 = MDSM/IBKR až po Signal Parity Testu (§14).
RB-2  Okamžik výpočtu: po close D z finálních denních dat.
      Ne intraday, ne před finálním EOD close, ne přepočet ráno.
RB-3  Regime universe: fixed frozen 503 (jako backtest). NaN-skip
      dle §4. Dynamická rebalance = budoucí verze, ne baseline.
RB-4  Kalendář: Fáze 1 = DATA-06 price index; Fáze 2 = NYSE calendar.
RB-5  Regime OFF + otevřené pozice: držet do planned_exit_date;
      regime blokuje pouze nové vstupy.
RB-6  Fill: Fáze 1 = simulovaný (entry open, exit close, 15 bps);
      Fáze 2 = IBKR paper fill + povinné porovnání actual vs simulated.
```

---

## 13. Baseline, evidence a zdůvodnění (C-5, C-6, C-7, C-9)

### 13.1 Kauzální auditní baseline (nahrazuje MLE-BT-04)

MLE-BT-04 obsahoval dva exekuční defekty (regime lookahead; cash/slot chronologie) — původní výsledek 375.283 % NENÍ validní baseline a smí být citován jen jako historický artefakt. MLE-BT-04 soubor a report zůstávají zachovány jako auditní důkaz.

Nová baseline = **MLE-BT-04R NEW, regime200_hold10, 2021-07-01..2026-07-02, 15 bps:**

```text
total return:   337.652 %
CAGR:           34.504 %
maxDD:          -32.700 %
Sharpe:         1.182
trades:         990
avg_exposure:   0.787
```

Referenční kontext (mle_only_hold10 NEW): 464.351 % / CAGR 41.550 % / maxDD −44.485 % / Sharpe 1.267 / 1150 trades.

Kontrola správnosti Fáze 1: replay MLE-PAPER-01 na historii MUSÍ reprodukovat MLE-BT-04R regime200_hold10. Pokud nesedí, chyba je v implementaci paper systému, ne ve strategii. Cíl není lepší výsledek; cíl je STEJNÝ výsledek.

### 13.2 Zdůvodnění regime200 (přepsáno — nahrazuje zdůvodnění v1.0)

```text
regime200 NENÍ alpha enhancer.
regime200 JE drawdown-control overlay.

Kauzální evidence (BT-04R): regime200 vs MLE-only
  CAGR    34.5 % vs 41.6 %   (platíme ~7 pb CAGR)
  Sharpe  1.182  vs 1.267    (horší i risk-adjusted)
  maxDD   -32.7 % vs -44.5 % (jediný doručený přínos)

Známá slabá místa (zaznamenáno, akceptováno rozhodnutím):
  - 2022: regime selhal (−25.4 % vs baseline −8.8 %); selhání je
    strukturální napříč holdy (BT-05), mechanismus = OFF okna +
    vstupy v bear-market rallies + propásnutá sektorová rotace
  - DD výhoda je doložená u hold10; napříč jinými holdy není
    systematická (BT-05)
  - evidence = jedno 5leté in-sample okno se survivorship bias

Rozhodnutí: regime200 se ponechává jako vědomý trade-off
(nižší CAGR/Sharpe výměnou za nižší maxDD u zvolené konfigurace).
Původní tvrzení v1.0 („regime zlepšuje výnos i DD") je vyvrácené
a nesmí být dále citováno.
```

### 13.3 Potvrzení hold10 (MLE-BT-05)

```text
Hold-period sensitivity test did not provide robust evidence to
replace hold10. Therefore hold10 remains frozen baseline.

Detail: hold12 ROBUST=False pro obě varianty (kritéria C1/C2/C3
definovaná předem); povrch hold→výkon je zubatý (path dependence
překryvných portfolií), bodové spiky (hold5, hold14) nejsou signál.
```

### 13.4 Výhrady k evidenci (závazné pro interpretaci čísel)

```text
- current 503 universe → survivorship bias (nekvantifikovaný)
- jedno 5leté in-sample okno; žádný OOS test
- path dependence: bodová čísla číst jako střed široké distribuce,
  ne jako slib (BT-05: sousední holdy se liší až 2×)
- 15 bps = modelované náklady; citlivost ~4.5–5 pb CAGR na +15 bps
  (reálné filly změří Fáze 2)
- Calmar NEPOUŽÍVAT jako rozhodovací metriku, dokud není ověřen
  výpočet/škálování (interní hodnoty nekonzistentní napříč reporty)
- realistické očekávání pro paper: CAGR 15–25 %, spíše spodní okraj
```

---

## 14. Signal Parity Test (gate pro Fázi 2)

Před přechodem na MDSM/IBKR zdroj cen (RB-1 Fáze 2) se MUSÍ změřit na překryvných dnech DATA-06 vs MDSM/IBKR:

```text
- TOP10 overlap po dnech
- rozdíl ranků
- rozdíl adjusted close returns
- dny ovlivněné corporate actions
```

Kvantitativní gate (přesné prahy) se stanoví až z naměřené distribuce rozdílů — vědomě NENÍ definován předem, aby nebyl vycucaný z prstu. Bez splnění gate se Fáze 2 nespouští: nelze tvrdit, že paper obchoduje stejnou strategii.

---

## 15. Fázování implementace

```text
Fáze 1 (bez TWS): models.py → decision_resolver.py → unit testy →
  portfolio_state.py → order_planner.py → signal_source/regime_source →
  replay engine → REPRODUKCE MLE-BT-04R (kontrola správnosti §13.1)
Fáze 2 (IBKR paper): Signal Parity Test (§14) → napojení IBKR paper →
  měření actual vs simulated fill (§9)
Umístění Fáze 1: MarketResearchLab/paper_trading/mle_paper_01/
  (vědomé rozhodnutí; core execution logika se později migruje mimo
  research vrstvu — zapsáno, aby nešlo o tiché trvalé umístění)
```
