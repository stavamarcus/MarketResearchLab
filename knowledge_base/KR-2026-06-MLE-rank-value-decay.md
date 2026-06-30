# Knowledge Record: MLE Rank — Informacni hodnota a decay

```yaml
kr_id:          KR-2026-06-MLE-rank-value-decay
status:         ACTIVE
confidence:     MEDIUM-HIGH
evidence_level: B+
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0007-MLE-RANK-BUCKETS
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-robustness
      type: knowledge_record
      note: "Grid testoval pouze MLE TOP10-50. Tento KR rozsiruje profil
             a kvantifikuje informacni hodnotu MLE ranku jako takoveho."
  inspired:
    - ref: "budouci: Decision Resolver priority tiers"
      type: observation
      note: "Monotonni decay motivuje hypotezu o vrstvene logice:
             TOP10 samostatne, TOP11-30 s potvrzenim, TOP30+ pouze
             se silnou dalsi evidenci"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLERankBuckets v1.0.0"
    type: experiment
    note: "Discrete buckety (Elite 1-10, Strong 11-20, ... Tail 101-150)"
  - ref: "MLERankCumulative v1.0.0"
    type: experiment
    note: "Kumulativni thresholdy (TOP10, TOP20, TOP30, TOP50, TOP70, TOP100)
           — doplnek objasnujici vztah mezi discrete a kumulativnim pohledem"
```

---

## Co bylo zjisteno

### Kumulativni profil (TOP-N, primarni interpretace pro DR)

```
TOP10    +1.11%
TOP20    +0.62%
TOP30    +0.23%   <- posledni kladny bod
TOP50    -0.09%
TOP70    -0.43%
TOP100   -0.70%
```

**5/5 monotonnich prechodu (100%).** Cisty, bez vyjimky klesajici profil.

### Discrete profil (izolovane buckety, vysvetluje strukturu)

```
Elite      1-10    +1.06%
Strong    11-20    +0.02%   <- prakticky nulove
Good      21-35    -0.58%
Moderate  36-50    -0.35%
Watch     51-70    -1.18%
Weak      71-100   -1.23%
Tail     101-150   -1.26%
```

### Finding 1 — MLE rank neni jen poradi, je to sila signalu

Informacni hodnota MLE ranku klesa monotonne a hladce. Neni to skokova
hranice (napr. "TOP20 dobre, TOP21 spatne") — je to plynuly decay.

### Finding 2 — Vysvetleni rozporu discrete vs kumulativni

Discrete bucket Strong (11-20) je prakticky nulovy (+0.02%), ale
kumulativni TOP20 je kladna (+0.62%), protoze TOP20 mixuje silny
Elite (+1.06%) se slabym Strong (+0.02%). Aritmeticky konzistentni —
zadny rozpor v datech, pouze ruzne otazky.

### Finding 3 — Hranice edge je mezi TOP30 a TOP50

Predchozi prace (MLERobustnessGrid) testovala pouze TOP10-50 a
predpokladala TOP20/TOP50 jako relevantni hranice. Tento profil
ukazuje presnejsi hranici: TOP30 je posledni bucket s kladnou alfou.

---

## Konzistence s MLE x IRC

```
Samotne MLE:           TOP10 nejlepsi -> TOP20 dobre -> TOP30 hranicni -> TOP50+ mizi
MLE + IRC (KR-MLE-IRC-robustness): TOP10 x IRC nejsilnejsi v celem gridu
```

Oba nezavisle vznikle vysledky (ruzne research projekty, ruzne experimenty)
ukazuji stejny smer: uzsi MLE selekce = silnejsi signal. To je dalsi
forma vzajemne potvrzujici se evidence napric Knowledge Base.

---

## Architektonicka hypoteza pro budouci Decision Resolver (NEVALIDOVANO jako pravidlo)

```
Priority A:  TOP10           -> muze projit samostatne
Priority B:  TOP11-30        -> potrebuje dalsi potvrzeni (napr. IRC tailwind)
Priority C:  TOP30+          -> potrebuje velmi silnou dalsi evidenci
```

Toto je hypoteza primo motivovana daty, NE schvalene produkcni pravidlo.
Vyzaduje formalni Research Project a Resolution pred jakymkoliv pouzitim
v Decision Resolveru.

---

## Kdy plati

- S&P 500 universe, MLE rank_10d jako zakladni metrika
- Backtest 2025-07-09 -> 2026-06-29 (216 obchodnich dni, ~1 rok)
- Alpha vs SPY jako metrika

## Kdy neplatí / nevalidováno

- **Pouze ~1 rok dat.** Stabilita pres ruzne trzni cykly nevalidovana.
- RISK_OFF podminky — nevalidovano
- Mimo S&P 500
- Statisticka vyznamnost jednotlivych bucketu/thresholdu

---

## Confidence: MEDIUM-HIGH — odůvodnění

Zvyseno nad zakladni MEDIUM kvuli:
- 100% monotonni kumulativni profil (5/5 prechodu)
- 83% monotonni discrete profil (5/6 prechodu)
- Dva nezavisle experimenty (discrete + kumulativni) vzajemne konzistentni
  a vysvetlujici
- Konzistence s nezavisle vzniklym MLE x IRC vysledkem

NE HIGH (na rozdil od KR-2026-06-MLE-IRC-rolling):
- Chybi rolling validation pres cas pro tento konkretni finding
- Pouze jeden rok historie — explicitni vyhrada architekta o
  dlouhodobe stabilite pres ruzne trzni cykly
- Chybi out-of-sample test

---

## Doporuceni pro budouci vyzkum

- Rolling validation tohoto profilu (analogicky k RP-0005 pro MLE x IRC)
- Az bude dostupna delsi historie: overit zda monotonni decay prezije
  napric ruznymi trznimi cykly (bull/bear/sideways)
- Formalni Research Project pro Priority Tiers hypotezu pred jakymkoliv
  vyuzitim v Decision Resolveru
