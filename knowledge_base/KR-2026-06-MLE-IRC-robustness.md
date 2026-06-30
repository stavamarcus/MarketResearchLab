# Knowledge Record: MLE x IRC — Robustness Grid

```yaml
kr_id:          KR-2026-06-MLE-IRC-robustness
status:         ACTIVE
confidence:     MEDIUM-HIGH
evidence_level: B+
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0004-MLE-IRC-ROBUSTNESS
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-interaction
      type: knowledge_record
      note: "Single-point vysledek (MLE TOP20 x IRC TOP10, diff +1.28pp)
             — tento test overuje stabilitu kolem tohoto bodu"
  inspired:
    - ref: "MLE x IRC Rolling Validation (navrh, dalsi krok)"
      type: research_project
      note: "Robustnost vuci prahum potvrzena — dalsim krokem je
             robustnost vuci casovym oknum"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLEIRCRobustnessGrid v1.0.0"
    type: experiment
    note: "16 kombinaci prahu, 216 obchodnich dni, 2025-07-09 -> 2026-06-29"
  - ref: KR-2026-06-MLE-IRC-interaction
    type: knowledge_record
    note: "Puvodni single-point nalez, ktery tento grid potvrzuje a rozsiruje"
```

---

## Co bylo zjisteno

### Grid vysledky (diff = alpha(MLE+IRC_TOP) - alpha(MLE_HEADWIND), 30D)

```
            IRC TOP5   IRC TOP10   IRC TOP15   IRC TOP20
MLE TOP10    +1.58%     +2.13%      +2.15%      +1.91%
MLE TOP20    +1.55%     +1.25%      +1.33%      +1.36%
MLE TOP30    +0.86%     +0.79%      +0.80%      +1.09%
MLE TOP50    +0.43%     +0.47%      +0.50%      +0.82%
```

### Finding 1 — Edge neni single-point artefakt

**16 ze 16 kombinaci ma kladny diff.** Zadna kombinace v gridu nevykazuje
negativni nebo nulovy efekt. To je silny argument proti overfitu —
puvodni KR-2026-06-MLE-IRC-interaction testoval pouze jeden bod
(MLE TOP20 x IRC TOP10), tento grid potvrzuje ze efekt drzi v cele
okolni oblasti.

```
Diff rozsah: +0.43% az +2.15%
Diff median: +1.17%
```

### Finding 2 — Logicka struktura, ne nahodny sum

Efekt monotonne slabne s rostoucim MLE prahem:
```
MLE TOP10 (median pres IRC prahy): ~+1.94%
MLE TOP20: ~+1.37%
MLE TOP30: ~+0.89%
MLE TOP50: ~+0.56%
```

Uzsi MLE selekce (silnejsi price leadership) v kombinaci s IRC context
prinasi silnejsi efekt. To odpovida intuici a teorii — neni to nahodny
pattern, je to smysluplna struktura.

### Finding 3 — Referencni bod potvrzen

MLE TOP20 x IRC TOP10 (puvodni KR-2026-06-MLE-IRC-interaction bod):
diff +1.25% v tomto gridu, konzistentni s +1.28pp v plnem datasetu
puvodniho KR (drobna odchylka z mirne odlisneho datoveho rozsahu/zpracovani).

---

## Architektonicky zaver

```
Primary validated signal candidate:
MLE rank_10d leadership + IRC industry tailwind
```

Toto je nejlepe podlozeny vyzkumny edge v MRL k 2026-06-30.
NENI to hotova strategie — je to nejsilnejsi kandidat pro budouci
Decision Resolver, podlozeny opakovanou validaci napric 16 kombinacemi
prahu, ne jen jednim bodem.

---

## Kdy plati

- S&P 500 universe
- MLE rank_10d jako zakladni metrika leadershipu
- IRC rank (lookback 20D) jako industry context
- Grid: MLE TOP10-50, IRC TOP5-20
- Backtest 2025-07-09 -> 2026-06-29

## Kdy neplati / nevalidovano

- RISK_OFF podminky — nevalidovano, ceka na MRC
- Stabilita pres CASOVA OKNA (rolling validation) — NEVALIDOVANO,
  toto je explicitne dalsi krok (viz Doporuceni)
- Mimo S&P 500
- Statisticka vyznamnost jednotlivych bunek gridu — nevalidovano
  (chybi bootstrap CI nebo permutacni test)
- Out-of-sample test na datech mimo 2025-07-09 -> 2026-06-29

---

## Confidence: MEDIUM-HIGH — odůvodnění

Zvyseno oproti puvodnimu KR-2026-06-MLE-IRC-interaction (MEDIUM) kvuli:
- 16/16 kombinaci kladnych — silna evidence proti overfitu
- logicka, ne nahodna struktura gridu

NE HIGH, protoze chybi:
- delsi historie nez 219-220 obchodnich dni
- rolling validation pres casova okna
- statisticke intervaly spolehlivosti
- out-of-sample validace

---

## Doporuceni pro budouci vyzkum

**Prioritni dalsi krok: MLE x IRC Rolling Validation**

Otazka: Drzi edge napric casovymi okny, nebo je tazen jednim obdobim?

Az po rolling validaci ma smysl uvazovat o:
- statisticke vyznamnosti (bootstrap, permutacni testy)
- segmentaci podle trzniho rezimu (MRC) — predcasne bez rolling validace
- formalnim navrhu pro Decision Resolver
