# Knowledge Record: IMS jako prioritizace uvnitr MLE TOP20

```yaml
kr_id:          KR-2026-06-IMS-within-MLE
status:         ACTIVE
confidence:     MEDIUM
evidence_level: B
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0003-MLE-CONDITIONED-IMS
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IMS-no-synergy
      type: knowledge_record
      note: "Negativni vysledek RP-0002 (prekryv nezavislych mnozin)
             motivoval jemnejsi formulaci otazky"
    - ref: KR-2026-06-IMS-missing-diagnosis
      type: knowledge_record
      note: "Vysvetleni IMS_MISSING bylo nutnou podminkou pred touto interpretaci"
  inspired: []
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLEIMSInteraction v1.1.0"
    type: experiment
    note: "Plny dataset 2025-07-09 -> 2026-06-29, 219 obchodnich dni"
```

---

## Hlavni hypoteza a vysledek

**Otazka:** Pomaha IMS radit kandidaty uvnitr jiz vybraneho MLE TOP20 univerza?

**Definice (po metodicke oprave — viz historie nize):**
```
IMS_<70 (N=447, alpha=-0.38%)  vs  IMS_90_94 (N=211, alpha=+0.46%)
```
Oba buckety jsou podmnoziny stejne zakladni mnoziny (MLE rank_10d <= 20)
a maji dostatecne N pro spolehlive srovnani.

**Vysledek:**
```
Diff: +0.84pp alpha
H: SUPPORTED (threshold 0.5pp)
```

**Hodnoceni sily efektu:** Pozitivni, ale slaby ve srovnani s
KR-2026-06-MLE-IRC-interaction (+1.28pp). Efekt je tesne nad prahem,
ne vyrazny.

---

## Historie metodicke opravy (transparentne zaznamenano)

Puvodni formulace hypotezy pouzivala `IMS_95plus` (N=9) jako horni hranici
srovnani — to davalo zavadejici vysledek (+8.29pp, tazeny statisticky
bezvyznamnym vzorkem). Architekt identifikoval problem pred archivaci.

Oprava: hlavni hypoteza prevedena na `IMS_<70 vs IMS_90_94` (oba N>200).
`IMS_95plus` zustava v experimentu a reportu, ale explicitne oznacen jako
**EXPLORATORY ONLY** — nikdy nevstupuje do rozhodovani o hypoteze.

Toto je dokumentovano jako priklad spravne praxe: maly vzorek se neskryva,
ale ani se nepouziva jako zaklad zaveru.

---

## Otevrena otazka — IMS_MISSING

```
IMS_MISSING: alpha=+1.91%, N=1605 (nejvetsi skupina, 38.1% MLE TOP20 signalu)
```

Vysvetleni puvodu teto skupiny je v KR-2026-06-IMS-missing-diagnosis
(95.8% = IMS score < 60 ten den, 4.2% = ticker nikdy v IMS univerzu).

**Interpretace teto skupiny vuci hlavni hypoteze zustava OTEVRENA.**
Tento KR se vztahuje pouze k porovnani IMS_<70 vs IMS_90_94 — nesnazi se
vysvetlit proc IMS_MISSING vychazi tak silne. To je samostatna otazka
pro budouci vyzkum (mozna souvisi se zjistenim KR-2026-06-MLE-IMS-no-synergy,
ze MLE samotne bez IMS filtru je silne).

---

## Porovnani sily dukazu — aktualni poradi

| Poradi | Knowledge Record | Diff alpha | Sila dukazu |
|---|---|---|---|
| 1 | KR-2026-06-MLE-IRC-interaction | +1.28pp | Vysoka |
| 2 | KR-2026-06-IMS-score-buckets | +2.14pp* | Stredni (*absolutni return, ne alpha) |
| 3 | KR-2026-06-IMS-within-MLE | +0.84pp | Stredni az nizsi |

MLE x IRC zustava nejprekonatelnejsim kandidatem na prakticky vyuzitelny
edge. Energie budouciho vyzkumu by mela zustat soustredena primarne tam.

---

## Kdy plati

- S&P 500, MLE rank_10d <= 20 jako zakladni mnozina
- Backtest 2025-07-09 -> 2026-06-29
- Srovnani pouze IMS_<70 vs IMS_90_94 (ne IMS_95plus)

## Kdy neplati / nevalidovano

- IMS_95plus jako samostatny bucket — N nedostatecne, vyzaduje delsi historii
- Interpretace IMS_MISSING vuci teto hypoteze — otevrene
- RISK_OFF podminky
- Bez statisticke vyznamnosti (bootstrap, Mann-Whitney)

---

## Confidence: MEDIUM — odůvodnění

- Evidence Level B, jeden backtest
- Efekt je pozitivni a smerove konzistentni (+0.54pp test, +0.84pp plny dataset)
- Ale slabsi nez MLE x IRC — nestaci na vyssi confidence
- Otevrena otazka IMS_MISSING snizuje uplnost interpretace

---

## Doporuceni pro budouci vyzkum

- Vysvetlit IMS_MISSING vztah k hlavni hypoteze (proc vychazi tak silne)
- Rolling validation pres delsi historii
- Statisticka vyznamnost (bootstrap CI) pro diff +0.84pp
- Energie prioritne na MLE x IRC prostor — silnejsi a jasnejsi signal
