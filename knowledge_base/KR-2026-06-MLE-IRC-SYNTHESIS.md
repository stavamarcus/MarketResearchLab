# Knowledge Record: MLE x IRC — Syntetizovana Knowledge Line

```yaml
kr_id:          KR-2026-06-MLE-IRC-SYNTHESIS
status:         ACTIVE
confidence:     HIGH
evidence_level: A-
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0001-SIGNAL-INTERACTION, RP-0004 az RP-0008
```

---

## Ucel tohoto dokumentu

Toto NENI novy experiment. Je to syntetizovany pohled na pet
samostatnych Knowledge Records, ktere spolu tvori jednu ucelenou
"knowledge line" o MLE x IRC interakci. Cilem je poskytnout jediny
referencni bod pro budouci Decision Resolver design, misto nutnosti
cist pet samostatnych dokumentu.

---

## Research Lineage — kompletni retez

```yaml
lineage:
  synthesizes:
    - ref: KR-2026-06-MLE-IRC-interaction
      contribution: "Single-point edge: MLE TOP20(10D) x IRC TOP10, +1.28pp alpha"
    - ref: KR-2026-06-MLE-IRC-robustness
      contribution: "16/16 kombinaci prahu kladnych — neni overfit na jeden bod"
    - ref: KR-2026-06-MLE-IRC-rolling
      contribution: "6/8 rolling oken kladnych — neni tazeno jednim obdobim"
    - ref: KR-2026-06-MLE-rank-value-decay
      contribution: "MLE rank profil: edge koncentrovan v TOP10-30, hranice TOP30/TOP50"
    - ref: KR-2026-06-MLE-buckets-IRC-multiplier
      contribution: "IRC je multiplikator sily (nejvic u TOP10), ne zachranny filtr"
  inspired:
    - ref: "budouci: formalni Priority Tiers Research Project"
      type: observation
  produced_rules: []
```

---

## Syntetizovany obraz

### 1. Existence edge

```
MLE TOP20 (10D) x IRC TOP10: +1.28pp alpha (single-point, plny dataset)
```

### 2. Robustnost vuci prahum

```
16/16 kombinaci (MLE TOP10-50 x IRC TOP5-20) ma kladny diff
Rozsah: +0.43% az +2.15%, median +1.17%
Struktura: uzsi MLE prah = silnejsi efekt (logicke, ne nahodne)
```

### 3. Robustnost vuci casu

```
6/8 rolling oken (60d/20d step) kladnych (75%)
Median window diff: +1.41%
Dve negativni okna (rijen 2025, leden-duben 2026) — otevrena otazka pro MRC
```

### 4. MLE rank value decay (samostatny, ale konzistentni nález)

```
TOP10    +1.11% (kumulativni alpha)
TOP20    +0.62%
TOP30    +0.23%   <- posledni kladny bod
TOP50    -0.09%
TOP70    -0.43%
TOP100   -0.70%

100% monotonni kumulativni profil
```

### 5. IRC jako multiplikator (presne mechanika interakce)

```
MLE bucket    HEADWIND    IRC_TOP    Diff
1-10           +0.23%      +2.49%   +2.26%   <- IRC nejvic pomaha tady
11-20          -0.06%      +0.12%   +0.18%   <- mensi, ale kladny efekt
21-30          -0.42%      -0.58%   -0.15%   <- NEPOTVRZENO ze IRC pomaha
51-70          -1.11%      -1.47%   -0.35%   <- zadny zachranny efekt
```

---

## Sjednocujici architektonicky zaver

```
MLE rank neni jen poradi — je to spojita mira sily signalu,
ktera monotonne klesa od TOP10 k TOP100.

IRC neni nezavisly zdroj alfa (viz KR-2026-06-IRC-persistence-standalone
— IRC samostatne NEPREKONAVA trh).

Dosavadni experimenty podporuji hypotezu, ze IRC pusobi jako
multiplikator existujiciho MLE signalu spise nez jako samostatny
zdroj alpha. Nejvyraznejsi efekt byl pozorovan u MLE TOP10.
U bucketu 21-30 a dal se tento posilujici efekt v dosavadnich
experimentech NEPOTVRDIL.
```

**Poznamka k formulaci (architekt, 2026-06-30):** Vyse uvedeny zaver
je formulovan jako hypoteza podporena daty, ne jako prokazany mechanismus.
Chybi statisticka vyznamnost, out-of-sample validace a vice trznich
cyklu — viz sekce "Co tato knowledge line jeste neumi" nize.

### Hypoteza priority tiers (revidovana, NEVALIDOVANA jako pravidlo)

```
Tier A: MLE TOP10                    -> silny edge samostatne,
                                         VYRAZNE posileny IRC TOP10 (+2.26pp)
Tier B: MLE 11-20                    -> slaby edge samostatne,
                                         mirne posileny IRC (+0.18pp)
Tier C: MLE 21-30                    -> slaby/zaporny edge,
                                         IRC efekt NEPOTVRZEN (-0.15pp, N nizsi)
Tier D: MLE 30+                      -> zaporny edge,
                                         IRC nezachranuje
```

**Toto je hypoteza primo motivovana konvergujicimi daty z peti
nezavislych experimentu. NENI to schvalene produkcni pravidlo.**

---

## Co tato knowledge line JESTE neumi

```
✗ Statisticka vyznamnost (bootstrap CI, permutace) — zadny z peti
  experimentu ji nepocitam
✗ Out-of-sample validace — vse na jednom datasetu (2025-07-09 -> 2026-06-29)
✗ Vysvetleni dvou negativnich rolling oken (rijen 2025, leden-duben 2026)
  — ceka na MRC
✗ Delsi historie (>1 rok) pro overeni stability pres trzni cykly
✗ Rolling validation specificky pro MLE-bucket x IRC grid (RP-0008)
```

---

## Confidence: HIGH — odůvodnění (stejne jako KR-2026-06-MLE-IRC-rolling)

**Dulezita poznamka:** Confidence HIGH a Evidence Level A- jsou interni
klasifikace MRL governance procesu (viz RESEARCH_GOVERNANCE.md),
NE tvrzeni o formalni statisticke vyznamnosti. Oznacuji relativni
silu evidence v ramci MRL Knowledge Base, ne p-hodnotu nebo
confidence interval v statistickem smyslu.

Tri nezavisle typy validace (existence, threshold robustness, time
robustness) plus dve dalsi nezavisle vznikle, vzajemne konzistentni
linie dukazu (rank decay profil, bucket x IRC multiplier mechanika).

Pet samostatnych experimentu, ruzne metodiky, stejny smer zaveru.
To je nejsilnejsi dostupna evidence v celem MRL k 2026-06-30 —
v ramci MRL klasifikace, ne v absolutnim statistickem smyslu.

NE Evidence Level A (pouze A-): chybi vse uvedene v sekci vyse,
vcetne formalni statisticke vyznamnosti.

---

## Doporuceni

**Pro vyzkum:** MLE x IRC prostor je dostatecne prozkoumany. Dalsi drobne
varianty (jine IRC prahy, jine MLE lookbacky) maji pravdepodobne klesajici
prinos. Energie by mela jit na:
1. Druhy nezavisly edge (IRC samostatne selhalo — viz
   KR-2026-06-IRC-persistence-standalone, zkusit jiny smer)
2. Statisticka vyznamnost existujicich MLE x IRC nalezu
3. Az bude dostupne: MRC pro vysvetleni rolling negativnich oken

**Pro architekturu:** Priority Tiers hypoteza je pripravena pro formalni
Research Project s cilem Resolution — ale teprve po doplneni statisticke
vyznamnosti.
