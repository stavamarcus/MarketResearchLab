# MLE-PAPER-01 — Strategy Specification (zmražená pravidla pro paper execution)

Verze: 1.0
Datum: 2026-07-09
Status: **ZMRAŽENO** — zdroj pravdy pro Decision Resolver. Žádná změna bez explicitního rozhodnutí + verzování.
Cílová cesta: `C:\Users\stava\Projects\MarketResearchLab\reports\MLE-PAPER-01_STRATEGY_SPEC.md`

---

## 0. Účel dokumentu

Přesná, jednoznačná pravidla zmražené strategie MLE-PAPER-01 pro automatizované paper provedení. Decision Resolver a všechny navazující komponenty MUSÍ implementovat POUZE tato pravidla. Žádná nová strategie, žádné nové filtry.

Pokud kód a tento dokument nesouhlasí, platí dokument. Změna pravidla = nová verze specu + záznam důvodu.

---

## 1. Definice a datové zdroje

```text
DATA-06:      C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\
              sharadar_full_equity_v20260705_01\derived\mdsm_price_view
              {conid}_D1.parquet, DatetimeIndex, OHLCV (open,high,low,close,volume)
universe:     C:\Users\stava\Projects\MDSM-Lite\data\universe\
              sp500_rank_calendar_universe.csv (conid,ticker,active_flag,sector,industry)
              → jen active_flag = true (503 tickerů)
MLE engine:   compute_rank_matrix(close_prices, instruments, target_date, lookbacks)
LOOKBACKS:    [1,2,3,4,5,6,7,8,9,10,20]
```

Poznámka pro paper: v backtestu byla data z DATA-06 (Sharadar). Pro live paper bude zdroj cen pravděpodobně IBKR/MDSM-Lite cache. **Rozhodovací bod:** zdroj cen pro paper musí být zafixován a musí odpovídat tomu, na čem běžel backtest (split-adjusted daily OHLCV). Rozdíl ve zdroji dat = potenciální rozdíl v signálech.

---

## 2. Definice obchodního dne a časování

```text
D    = signální den (obchodní den, kdy se počítá MLE rank + regime)
D+1  = následující obchodní den (kdy se VSTUPUJE na open)

Časová osa jednoho cyklu:
  po zavření trhu v den D (nebo před otevřením D+1):
    1. spočítej MLE rank matrix z dat do D včetně
    2. spočítej regime200 stav pro D
    3. Decision Resolver vytvoří order plan pro D+1
  na open D+1:
    4. provedou se BUY (nové vstupy) a EXIT (planned exits) na open
```

**Rozhodovací bod:** přesný okamžik výpočtu (po close D vs před open D+1) musí být zafixován. Doporučení: počítat po close D z finálních denních dat, aby open D+1 byl skutečně "next open po signálu" jako v backtestu.

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

Poznámka: 4 tickery s nedostatečnou historií (EXE, PSKY, Q, SNDK v době backtestu) mohou mít NaN — to není chyba, ignorují se.

---

## 4. Výpočet regime200

```text
krok 1: denní výnos každého tickeru = close[t] / close[t-1] - 1
krok 2: market_daily_return[t] = průměr denních výnosů všech 503 tickerů
krok 3: index_level[t] = kumulativní součin (1 + market_daily_return), start 1.0
krok 4: MA200[t] = průměr index_level za posledních 200 obchodních dní
krok 5: regime_ON[D] = index_level[D] > MA200[D]

edge case: pokud MA200 není k dispozici (< 200 dní historie) → regime_ON = True
           (neblokovat). V paper nenastane — historie je dlouhá.
lookahead: MA200 používá jen data do D včetně. Žádná budoucí data.
```

**Rozhodovací bod (zásadní):** index se počítá z celého 503 universe. Pro paper musí být index počítán ze STEJNÉHO universe jako v backtestu, se stejnou historií pro MA200. Pokud se universe v čase mění (rebalance S&P), musí být zdokumentováno, jak se index počítá (fixní vs aktuální universe).

---

## 5. Rozhodovací logika (Decision Resolver)

Pro každý obchodní den D Decision Resolver produkuje akce pro D+1. Pořadí zpracování je závazné:

### 5.1 Krok 1 — EXITY (planned exits)

```text
pro každou otevřenou pozici:
  pokud planned_exit_date == D+1:
    → akce EXIT na open D+1
```

`planned_exit_date` = obchodní den, kdy uplyne 10 obchodních dní držení. Viz sekce 6.

### 5.2 Krok 2 — REGIME GATE

```text
regime_ON[D] = výpočet dle sekce 4
pokud regime_ON == False:
  → ŽÁDNÉ nové vstupy pro D+1 (jen exity z kroku 1 se provedou)
  → přeskoč krok 3
pokud regime_ON == True:
  → pokračuj na krok 3
```

### 5.3 Krok 3 — VSTUPY (new entries)

```text
free_slots = MAX_POSITIONS (10) - počet otevřených pozic (po exitech z kroku 1)
pokud free_slots <= 0:
  → žádné nové vstupy (portfolio plné)
jinak:
  kandidáti = MLE_TOP10 seřazení dle rank_10d
  vyluč tickery, které už držím (žádné duplicity)
  vezmi prvních free_slots kandidátů
  pro každého:
    target_value = 10 % aktuální equity
    pokud cash < target_value: použij dostupný cash (spend = min(target, cash))
    pokud spend <= 0: přeskoč (nedostatek cash)
    → akce BUY na open D+1, quantity = spend / open_price
```

### 5.4 Výstup Decision Resolveru

```text
pro každou akci: {BUY | EXIT}, ticker, quantity, reason, date=D+1
pokud žádná akce: DO_NOTHING
```

---

## 6. Výpočet planned_exit_date

```text
při vstupu (entry na open D+1):
  entry_trading_day = D+1
  planned_exit_date = 10. obchodní den PO entry_trading_day
                    = entry_trading_day + 10 obchodních dní
                    (počítáno přes obchodní kalendář, ne kalendářní dny)

příklad: entry v pondělí → exit za 10 obchodních dní (obvykle za 2 týdny,
         přeskakuje víkendy a svátky)
```

**Rozhodovací bod:** zdroj obchodního kalendáře pro paper (víkendy + burzovní svátky NYSE). Backtest používal dostupné dny v DATA-06. Paper musí použít stejný kalendář (NYSE trading days).

---

## 7. Ošetření hraničních stavů

```text
regime OFF + otevřené pozice:
  → DRŽ pozice do jejich planned_exit_date (konzistentní s backtestem)
  → regime blokuje jen NOVÉ vstupy, ne exity existujících
  ROZHODOVACÍ BOD: potvrdit, že paper drží stejně jako backtest.
  Alternativa (nezavedeno): zavírat pozice hned při regime OFF — TO BY BYLA
  ZMĚNA STRATEGIE, ne baseline.

ticker už otevřený + znovu v TOP10:
  → NEotevírat druhou pozici. Držet stávající do jejího planned_exit_date.

nedostatek cash na plnou pozici:
  → koupit za dostupný cash (spend = min(target_value, cash))
  → pokud spend <= 0, přeskočit tento ticker

open cena chybí (D+1):
  → pozice se neotevře (skip). Zalogovat jako warning.

exit — close cena chybí:
  → fallback dle definice zdroje. Zalogovat warning.
  ROZHODOVACÍ BOD: paper fill logika (viz sekce 9).

MLE_TOP10 má méně než 10 tickerů:
  → vstoupit jen do dostupných. Zbytek zůstává cash.

signál generuje víc kandidátů než free_slots:
  → vzít nejlepší MLE rank (kandidáti jsou seřazení). Zbytek zahodit.
```

---

## 8. Stavový model (paper portfolio state)

Perzistentní stav, který systém udržuje mezi dny:

```text
positions[]:
  ticker
  conid
  shares (quantity)
  entry_date
  entry_price
  planned_exit_date
  signal_rank        (MLE rank_10d při vstupu)
  regime_at_entry    (True — vždy True, protože vstup jen při regime ON)
  status             (OPEN | CLOSED)

account:
  cash
  equity             (cash + mark-to-market pozic)
  last_updated_date

historie:
  closed_trades[]    (pro audit: entry/exit date, price, pnl, reason)
```

Invarianty (musí platit vždy):
```text
- počet OPEN pozic <= 10
- cash >= 0
- žádné dvě OPEN pozice se stejným tickerem
- equity = cash + suma(shares × aktuální close)
```

---

## 9. Fill logika pro paper (rozhodovací body)

```text
backtest fill: entry = open[D+1], exit = close[planned_exit_date]

paper fill — MUSÍ SE ROZHODNOUT:
  a) simulovaný fill (jako backtest): entry na open, exit na close, bez slippage
     nad rámec 15 bps → nejblíž backtestu, ale nezohledňuje reálné plnění
  b) IBKR paper broker fill: skutečné paper ordery, reálné (paper) fill ceny
     → realističtější, ale fill cena se může lišit od backtest předpokladu

DOPORUČENÍ: v první fázi (order planner bez TWS) použít (a) — simulovaný fill
konzistentní s backtestem. Po napojení IBKR paper přejít na (b) a POROVNAT,
jak moc se reálné paper filly liší od simulace.
```

Náklady: 15 bps round-trip (half na každé straně) — konzistentní s backtestem.

---

## 10. Logging (co se loguje)

```text
každý den:
  regime_ON stav + index_level + MA200 (pro audit výpočtu)
  MLE_TOP10 (ticker, rank)
  Decision Resolver akce (BUY/EXIT/HOLD/DO_NOTHING) + reason
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
BEZ dynamického hold periodu
BEZ live tradingu (jen paper)
BEZ ML / optimalizace
```

Jakékoli z výše uvedeného = ZMĚNA STRATEGIE, vyžaduje novou verzi specu a rozhodnutí, ne tichou úpravu kódu.

---

## 12. Otevřené rozhodovací body (k potvrzení před implementací)

Shrnutí bodů označených výše, které vyžadují explicitní rozhodnutí:

```text
RB-1: zdroj cen pro paper (DATA-06 vs IBKR/MDSM) — musí odpovídat backtestu
RB-2: okamžik výpočtu signálu (po close D vs před open D+1)
RB-3: jak se počítá regime index při měnícím se universe (S&P rebalance)
RB-4: zdroj obchodního kalendáře (NYSE trading days) pro planned_exit_date
RB-5: regime OFF + otevřené pozice → držet do exitu (potvrdit backtest chování)
RB-6: fill logika paper (simulovaný vs IBKR paper broker)
```

Tyto body neurčují strategii (ta je zmražená), ale způsob jejího provedení. Musí být zafixovány ve v1.1 specu před napojením paper účtu.
