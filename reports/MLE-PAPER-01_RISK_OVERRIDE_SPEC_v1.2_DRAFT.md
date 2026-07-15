# MLE-PAPER-01 — Risk & Override Layer Specification v1.2

Verze: 1.2 — DRAFT k review
Datum: 2026-07-14
Status: **DRAFT** — specifikace bez implementace. Implementace POVOLENA až po úspěšné reprodukci MLE-BT-04R replayem (rozhodnutí architekta, viz §8).
Cílová cesta: `C:\Users\stava\Projects\MarketResearchLab\reports\MLE-PAPER-01_RISK_OVERRIDE_SPEC_v1.2_DRAFT.md`
Vztah k v1.1: NEMĚNÍ mechanickou strategii v1.1 (ta zůstává frozen). Přidává auditovanou risk & override vrstvu NAD ni pro živý paper běh. Fáze 1 replay běží čistě dle v1.1 bez této vrstvy.

---

## 0. Účel a motivace

1. BT-04R změřil, že mechanický návrat regime200 po propadu je pomalý (2023: ~59 pb propásnuto čekáním na MA200 cross). PM požaduje právo diskrečního dřívějšího návratu — POUZE směrem do trhu, nikdy proti ochrannému vypnutí.
2. Automatický systém potřebuje systémovou pojistku proti chování mimo změřenou historii: kill switch na drawdown účtu od high-water mark.
3. Vše musí být auditovatelné a měřitelné — diskrece bez měření by zničila vyhodnotitelnost celého paper běhu.

---

## 1. Hierarchie priorit (závazná)

```text
1. kill switch (strategy drawdown)
2. data / broker / integrity locks (emergency operations halt — §7)
3. effective regime gate
4. MLE signál
5. portfolio constraints (cash, max positions, no-duplicate,
   pending-exit rule)
```

```text
effective_regime_ON = mechanical_regime_ON  OR  active_force_ON_override
```

Override přebíjí POUZE vstupní regime gate. Override NIKDY nepřebíjí:

```text
kill switch
cash limit
max positions (10)
duplicate ticker rule
pending-exit rule (slot/cash/ticker do dalšího open)
missing price / data incident
order safety / emergency halt
```

Override nesmí zabránit ani oddálit mechanické ochranné VYPNUTÍ — ochranná strana zůstává 100% mechanická.

---

## 2. Force-ON override

### 2.1 Sémantika

```text
Override mění výhradně effective_regime_ON.
Override NENÍ trade selector:
  - nevybírá tickery
  - nemění sizing (10 % equity)
  - nemění hold period (10)
  - neruší ani neposouvá pending exity
  - neobchází MLE TOP10
```

### 2.2 Expirace (rozhodnuto architektem)

Override expiruje při NEJBLIŽŠÍ z těchto událostí:

```text
E1  mechanical_regime_ON == True   (mechanika dohnala PM → override
                                    se rozpouští, vše opět automatické)
E2  regime index close klesne o 8 % pod index close dne aktivace
    (pojistka proti špatnému bottom-callu; viz OQ-1 k anchoru)
E3  uplyne 30 obchodních dní od aktivace
E4  PM override ručně zruší (CANCELLED)
E5  aktivuje se kill switch
```

`X = 8 %` pro první paper verzi; změna vyžaduje novou verzi specu.

### 2.3 Časový cutoff zadání

```text
Override musí být zadán: po close D, před vytvořením order planu pro D+1.
Žádné intraday přepínání po vytvoření plánovaných orderů.
Jediná výjimka: emergency operations halt (§7) — ten ale nikdy
nezapíná vstupy, pouze zastavuje.
```

### 2.4 Override ledger (append-only)

Override = záznam v ledgeru, NIKDY úprava kódu ani ruční manipulace portfolio state. Žádné zpětné editace; oprava pouze novým záznamem.

```text
override_id
created_at
created_by
activation_signal_date      (den D, po jehož close byl zadán)
effective_trade_date        (první D+1, pro který platí)
force_on = true
activation_index_level      (regime index close dne aktivace — kotva E2)
activation_spy_close        (informativní; viz OQ-1)
reason                      (PM zdůvodnění bottom-callu)
expiry_rule                 (E1–E5 parametry platné při aktivaci)
status = ACTIVE | EXPIRED | CANCELLED
expired_at
expiry_reason               (E1|E2|E3|E4|E5)
```

---

## 3. Kill switch (strategy drawdown)

### 3.1 Definice a prahy (rozhodnuto architektem)

```text
drawdown = equity / max(equity od startu paper běhu) - 1
           (high-water mark, denní close, z existujícího logu v1.1 §10)

DD <= -25 %:  SOFT WARNING — povinná revize PM+architekt, systém běží dál
DD <= -35 %:  HARD KILL   — aktivace kill switch
```

Zdůvodnění prahu: kauzální baseline maxDD = −32.7 %; hard kill −35 % = „systém je mírně mimo změřené historické chování". Těsnější práh by zastavil i systém chovající se přesně jako backtest; volnější (−40 %) je pro první paper příliš. Pro live peníze může být práh nižší dle osobní tolerance; pro paper validaci se drží −35 %, jinak strategie neprojde srovnatelnou zátěží.

### 3.2 Akce při HARD KILL

```text
- žádné nové BUY (bez ohledu na regime i override)
- otevřené pozice DOBĚHNOU do svých planned_exit_date, exity se provedou
- ŽÁDNÁ automatická okamžitá likvidace (prodej všeho na dně = nová
  strategie a systematická chyba)
- restart POUZE ručním rozhodnutím PM+architekt po revizi
- aktivace expiruje všechny ACTIVE overridy (E5)
```

---

## 4. Shadow portfolio (rozhodnuto architektem — plnohodnotný běh)

Živý paper běh vede DVĚ paralelní portfolia:

```text
actual portfolio:      s overridy (a kill switchem)
mechanical shadow:     čistý MLE-PAPER-01 v1.1 bez overridů
```

Pouhý log čistého regime signálu NESTAČÍ — override mění vstupy, cash, sloty, planned exity, dostupnost tickerů, equity křivku i sekvenci obchodů. Jen plný paralelní běh odpoví přesně, zda PM diskrece přidává hodnotu.

Minimální reportovací výstup (průběžně):

```text
actual equity | mechanical shadow equity
difference $ | difference %
trades only due to override
missed mechanical trades
override PnL attribution (per override_id)
DD actual vs DD mechanical
```

Implementační poznámka: resolver v1.1 je čistá funkce → shadow běh = druhé volání resolveru s mechanickým regime a vlastním PortfolioState. Architektura to umožňuje bez zásahu do resolveru.

---

## 5. Co v1.2 NEMĚNÍ

```text
- mechanickou strategii v1.1 (signál, regime výpočet, hold10, sizing,
  kauzální pravidla, fill logiku, kontrakty)
- Fázi 1 replay (běží čistě dle v1.1, bez risk vrstvy)
- resolver (čistá funkce zůstává; override je transformace regime
  VSTUPU, kill switch je gate NAD výstupním plánem)
```

---

## 6. Auditní požadavky

```text
- override ledger: append-only, žádné zpětné editace (§2.4)
- každý den se loguje: mechanical_regime_ON, active_override_id,
  effective_regime_ON, kill_switch_state, HWM, aktuální DD
- shadow portfolio state se persistuje stejně jako actual (§4)
- každá expirace overridu: expired_at + expiry_reason do ledgeru
```

---

## 7. Emergency operations halt (vymezení — mimo scope v1.2)

Operační incidenty (špatná data, chybné ordery, broker mismatch, extrémní technická chyba) NEJSOU strategy kill switch. Emergency halt:

```text
- smí zastavit systém kdykoli, i intraday
- nikdy nezapíná vstupy
- má mít separátní pravidla — samostatný dokument OPS_HALT spec
  (zatím nespecifikováno; zapsáno jako známý dluh před Fází 2)
```

---

## 8. Fázování a podmínka implementace

```text
1. dokončit Fázi 1 dle v1.1: signal_source / regime_source →
   replay engine → REPRODUKCE MLE-BT-04R
2. teprve po úspěšné reprodukci: implementace v1.2
   (důvod: nejdřív musí fungovat čistá mechanická baseline; jinak
   nelze lokalizovat chybu mezi resolver/portfolio/replay/risk vrstvou)
3. spec v1.2 se před implementací povyšuje z DRAFT na APPROVED/FROZEN
```

---

## 9. Otevřené otázky k rozhodnutí (před freeze v1.2)

```text
OQ-1  Kotva expirace E2: architekt uvádí "regime index / SPY close".
      NÁMITKA (Claude): SPY není v DATA-06 (regime index je záměrně
      equal-weight universe, ne SPY — rozhodnutí z výzkumné fáze) a
      zavedl by novou datovou závislost + možnou divergenci obou kotev
      (equal-weight vs cap-weighted se v sektorových rotacích rozcházejí
      o procenta). DRAFT proto kotví E2 na INTERNÍ regime index close;
      SPY close se do ledgeru zapisuje jen informativně.
      → Architekt: potvrdit index-anchor, nebo explicitně zvolit SPY
      (pak nutno definovat zdroj SPY dat pro paper).
OQ-2  SOFT WARNING (-25 %): jaká je formální akce? Návrh: povinný
      review zápis (datum, závěr, podpis PM) do risk logu; bez zápisu
      systém po 5 obchodních dnech eskaluje (opakované warningy).
      Potvrdit/upravit.
OQ-3  Restart po HARD KILL: vyžaduje se nová verze specu, nebo stačí
      zapsané rozhodnutí PM+architekt v risk logu? Návrh: zapsané
      rozhodnutí + povinná analýza příčiny DD (co se lišilo od
      backtestu).
```
