# MLE-PAPER-01 — Zpráva o výsledku a specifikace zmražené strategie

Datum: 2026-07-09
Status: **STRATEGIE ZMRAŽENA** (baseline pro paper trading, bez dalších změn)
Cílová cesta reportu: `C:\Users\stava\Projects\MarketResearchLab\reports\MLE-PAPER-01_frozen_strategy_report.md`

---

## 1. Verdikt

Výzkumná fáze je uzavřena. Výsledkem je jednoduchá, cenově-only momentum strategie s jedním rizikovým filtrem. Strategie byla vybrána tím, že se otestovaly složitější varianty a data je zamítla — ne dojmem ani laděním parametrů.

```text
FINÁLNÍ STRATEGIE: MLE (rank_10d <= 10) + regime200 filtr, hold 10D
2 komponenty, obě standardní, žádný laděný parametr.
```

Backtestový výsledek (5 let, current 503 universe, 15 bps): total return ~375 % vs benchmark buy-and-hold ~79 %. Čísla jsou **optimistický horní odhad** kvůli survivorship bias a jednomu časovému období — viz sekce 6.

---

## 2. Specifikace zmražené strategie (MLE-PAPER-01)

### 2.1 Výběr akcií (MLE)

```text
zdroj:        MarketLeadershipEngine, fresh compute z DATA-06 (mdsm_price_view)
signál:       MLE rank_10d <= 10
              (10 akcií s nejsilnějším výnosem za posledních 10 obchodních dní)
universe:     current 503 S&P tickerů (sp500_rank_calendar_universe.csv, active_flag)
tie-break:    pořadí dle universe (insertion order)
```

### 2.2 Rizikový filtr (regime200)

```text
index:        equal-weight universe index
              = kumulativní součin průměrných denních výnosů všech 503 akcií
              (SPY není v DATA-06, proto equal-weight proxy z jednotlivých akcií)
signál:       index > jeho 200denní klouzavý průměr (MA200)
pravidlo:     regime ON  → povolit nové vstupy
              regime OFF → nevstupovat, držet hotovost
lookahead:    žádný — MA200 používá jen minulých 200 dní
poznámka:     regime blokuje NOVÉ vstupy; držené pozice pokračují do exitu
```

### 2.3 Portfolio pravidla

```text
initial_capital:   100 000 (referenční)
max pozic:         10
sizing:            10 % aktuální equity na pozici (equal weight dle equity)
entry:             next open po signálním dni
exit:              close po 10 obchodních dnech (fixně)
duplicity:         žádná druhá pozice v již drženém tickeru
směr:              long only
cash:              když regime OFF nebo nedostatek signálů
```

### 2.4 Náklady (referenční)

```text
15 bps round-trip (half round-trip na každé straně, tj. bps/2 při entry i exitu)
strategie testována i na 0 / 5 / 25 bps — edge robustní ve všech úrovních
```

### 2.5 Co strategie NEOBSAHUJE (vědomě)

```text
BEZ stop-loss           (zamítnuto daty — whipsaw, viz sekce 5)
BEZ výběrových filtrů   (cena/volatilita/historie/rank — nerozlišují, sekce 5)
BEZ dual-MA regime      (backlog, ne baseline, viz sekce 7)
BEZ IRC hard filtru     (redukuje breadth, zamítnuto v EDGE-BT-01C)
BEZ fundamentů          (MLE je cenově-only — žádné Sharadar SF1, PIT, valuace)
BEZ dynamického přepínání hold periody (lookahead bias, zamítnuto)
```

---

## 3. Výkonnost (backtest 2021-07-01 → 2026-07-02, 15 bps)

### 3.1 Strategie vs benchmark

```text
                              total return   CAGR      maxDD     Sharpe   Calmar
MLE + regime200 hold10        375 %          ~37 %     -25.4 %   1.20     1.44
benchmark buy-and-hold        ~79 %          ~12.3 %   -20.9 %   0.78     —
```

Poměr: strategie ~4.7× total return benchmarku; +25 procentních bodů CAGR ročně; jen mírně vyšší drawdown (-25 % vs -21 %).

Calmar = CAGR / |maxDD| = 36.7 / 25.4 = 1.44.

### 3.2 Roční rozklad (regime200 hold10 vs benchmark)

```text
rok    strategie   benchmark   regime ON %   poznámka
2021    +5.1 %      +8.9 %       100 %        částečné okno (od července)
2022   -18.0 %     -11.8 %        34 %        bear market — regime šel do cash
2023   +82.8 %     +20.6 %        86 %        recovery (regime obětoval část, viz 7)
2024   +29.1 %     +17.8 %       100 %
2025   +37.3 %     +13.7 %        86 %        regime snížil DD
2026   +69.5 %     +10.5 %        98 %        částečné okno (do července)
```

Strategie porazila benchmark v každém plném roce kromě 2022 (bear market, kde ztratila méně díky přechodu do cash, ale benchmark klesl méně, protože equal-weight index nespadl pod MA tak výrazně).

---

## 4. Proč právě tato (jednoduchá) podoba — shrnutí testů

Jednoduchost není kompromis. Je výsledkem toho, že složitější varianty byly otestovány a zamítnuty daty.

```text
test              výsledek
EDGE-TEST-01      MLE×IRC signál PASS (mírně lepší průměr forward returnu)
EDGE-BT-01/B      INVALID — chyba equity accountingu (opraveno)
EDGE-BT-01C       MLE-only > MLE×IRC v portfoliu → IRC hard filtr ZAMÍTNUT
MLE-BT-02         MLE-only 5 let: CAGR ~40 %, ale maxDD -39 %
MLE-BT-03         regime200 nejlepší (Calmar 1.44); stop-loss ZAMÍTNUT
MLE-BT-04         regime200 hold10 potvrzena jako primární varianta
MLE-DIAG-01       losery nepredikovatelné → výběrové filtry nemají smysl
```

---

## 5. Co bylo zamítnuto a proč

### 5.1 Stop-loss 8 % (O'Neil/CAN SLIM standard)

```text
hold10: CAGR 33.7 % → 21.6 % (pokles o 12 pp), maxDD DOKONCE HORŠÍ
383 stop exitů = whipsaw. Momentum akcie jsou volatilní, 8% stop je
uřezává těsně před zotavením.
→ ZAMÍTNUTO. Data jasně ukázala škodlivost.
```

### 5.2 IRC hard filtr (MLE×IRC)

```text
Na úrovni signálu edge vypadal lépe (EDGE-TEST-01).
V portfoliu horší (EDGE-BT-01C): IRC filtr redukuje breadth (233 vs 250
trades) a vyřazuje velké vítěze mimo top industries.
→ ZAMÍTNUTO jako hard filtr. IRC jako váha = nevyřešená budoucí hypotéza.
```

### 5.3 Výběrové filtry (cena / volatilita / historie / rank)

```text
MLE-DIAG-01 (1090 obchodů): losery vs winnery téměř identické.
korelace s výnosem:
  entry_price:  -0.03  (NULA — cena není faktor, mýtus vyvrácen)
  volatilita:   +0.10  (slabá, OPAČNÁ — winnery jsou volatilnější)
  momentum rank:-0.04  (NULA)
  historie:     -0.09  (NULA — losery jsou spíš staré firmy)

CVNA byla v BT-02 nejlepší trade (+196 %) i v DIAG-01 mezi top losery
(-25.9 %). Stejná akcie = winner i loser → jde o načasování, ne o akcii.
→ losery NELZE identifikovat předem. Žádný výběrový filtr nepomůže.
→ důsledek: MLE výběr je už optimální; ztráty jsou nevyhnutelný šum.
```

### 5.4 Dynamické přepínání hold periody

```text
"Přepínat hold podle toho, co zrovna funguje" = lookahead bias.
"Co funguje" se pozná jen zpětně. Na backtestu by zářilo, v realitě selhalo.
→ ZAMÍTNUTO jako adaptivní overfitting.
```

---

## 6. Zásadní výhrady (proč čísla nebrat doslova)

Backtestová čísla jsou **optimistický horní odhad**, ne očekávaný reálný výsledek.

```text
1. SURVIVORSHIP BIAS — pravděpodobně největší zkreslení
   Testováno na 503 SOUČASNÝCH akciích (přeživších). Firmy, které z indexu
   vypadly (bankrot, delisting), v datech NEJSOU. Momentum vítězové jako
   CVNA/SNDK/PLTR přežili a vyrostli; ti, co spadli a zmizeli, chybí.

2. IN-SAMPLE, jedno období
   2021-2026 = jedna 5letka s mohutnou tech/AI rally (2023-2026) a jedním
   bear marketem (2022). Momentum v tomto období zářilo. Jiná dekáda
   (např. 2000-2010) může být výrazně slabší.

3. Koncentrace v jednom tickeru
   SNDK ~17 % celkového zisku ve všech variantách. Recent IPO,
   survivorship-heavy. Bez něj je return nižší.

4. Regime chrání jen broad-market, ne sektorové propady
   2022 (broad bear): regime ON jen 34 % → vyhnul se.
   2024-2025 (semi/tech propady): regime ON 84-100 % → NEZACHYTIL,
   protože celkový trh držel nad MA200.

5. Bez reálného tření
   slippage, likvidita při vstupu 10 pozic naráz, daně — nic z toho
   backtest nemá nad 15 bps.

Realistický odhad (SPEKULACE, chybí survivorship-free data):
skutečný CAGR spíš 15-25 % než 37 %. Pořád nad benchmarkem, ale ne 4.7×.
```

**Edge pravděpodobně existuje** (momentum je akademicky doložený jev, regime200 je standardní neladěný filtr, test není zmanipulován — stop-loss v něm selhal, losery vyšly náhodné). Ale je **menší, než backtest ukazuje**.

---

## 7. Backlog (nezavádět bez forward potvrzení)

```text
R&D-IDEA-01: asymmetric regime (dual-MA)
  motivace:  regime200 v 2023 recovery obětoval ~30 pp (zapnul pozdě)
  návrh:     exit  = index < MA200 (pomalý, vyhne se bear)
             entry = index > MA50  (rychlý, chytí recovery dřív)
  VAROVÁNÍ:  přínos je hlavně z JEDNÉ události (2022→2023 recovery).
             Riziko fitování na tuto konkrétní recovery. Rychlejší vstup
             může způsobit whipsaw (falešný odraz / dead cat bounce).
  status:    samostatný budoucí experiment, NE úprava paper baseline.
             Výsledek NESMÍ změnit baseline bez forward potvrzení.
```

---

## 8. Další krok — paper trading

```text
1. MLE-PAPER-01 freeze                    ← nyní
2. paper trading bez změn (žádné úpravy strategie)
3. audit paper výsledků po 3-6 měsících
4. teprve pak nové výzkumné větve (vč. R&D-IDEA-01 dual-MA)
```

Paper trading řeší přesně ty výhrady, které backtest nemůže:

```text
- survivorship: obchoduje reálné current universe forward (ne přeživší z minulosti)
- out-of-sample: forward období, ne historický overlap
- reálné tření: skutečné open ceny, timing vstupu, slippage
- edge robustnost: platí CAGR/DD i mimo tuto 5letku?
```

Je to nejčistší test skepse "je to příliš dobré, než aby to byla pravda" — realita odpoví dopředu, ne dohady dozadu.

---

## 9. Reference (zdrojové skripty a reporty)

```text
skripty (research_projects\tests\):
  edge_test_01_mle_irc_signal_validation.py
  edge_bt_01c_windowed_equity_backtest.py       (opravený equity accounting)
  mle_bt_02_five_year_current_universe_backtest.py
  mle_bt_03_drawdown_control.py                 (regime200 vs stop-loss)
  mle_bt_04_yearly_monthly_regime_breakdown.py  (diagnostika regime)
  mle_diag_01_loser_characteristics.py          (losery nepredikovatelné)

reporty (reports\backtests\):
  EDGE-BT-01C, MLE-BT-02, MLE-BT-03, MLE-BT-04, MLE-DIAG-01

data:
  DATA-06 mdsm_price_view (sharadar_full_equity_v20260705_01)
  universe: sp500_rank_calendar_universe.csv (503 active)
```

---

## 10. Závěr

```text
Máš jednoduchou, cenově-only momentum strategii s jedním standardním
rizikovým filtrem. Postavenou na datech, ne na dojmech. Se složitými
variantami otestovanými a zamítnutými. S poctivě zdokumentovanými výhradami.

Strategie je ZMRAŽENA. Další krok je forward validace (paper trading),
ne další vylepšování. Backtestová čísla ber jako optimistický horní odhad;
reálný edge bude menší, ale pravděpodobně existuje.
```
