# Knowledge Record: MLE x IMS — Hypotéza o synergii nepotvrzena

```yaml
kr_id:          KR-2026-06-MLE-IMS-no-synergy
status:         ACTIVE
confidence:     LOW
evidence_level: B
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0002-MLE-IMS-INTERACTION
```

---

## Presna formulace zaveru

**NE:** "IMS nema prinos k MLE."

**ANO:** "Hypoteza o synergii MLE x IMS, formulovana jako prekryv dvou
nezavislych skupin (MLE TOP20 a IMS score buckety), nebyla na tomto
datasetu potvrzena."

Toto rozliseni je dulezite. Negativni vysledek se vztahuje ke konkretni
formulaci hypotezy (H-001 az H-003), ne k modulu IMS jako takovemu.

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-interaction
      type: knowledge_record
      note: "Uspesna metodika MLE x context testu inspirovala tento test"
    - ref: KR-2026-06-IMS-score-buckets
      type: knowledge_record
      note: "IMS edge potvrzen samostatne (s vyhradou absolutniho returnu)"
  inspired:
    - ref: "RP-0003 (navrh): MLE-conditioned IMS prioritization"
      type: research_project
      note: "Jemnejsi formulace otazky — viz Doporuceni nize"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "MLEIMSInteraction v1.0.0"
    type: experiment
    note: "Plny dataset, 2025-07-09 -> 2026-06-29, 219 dni"
```

---

## Co bylo zjisteno

### Vysledky (po oprave _assign_group bugu — IMS_ONLY N=6 -> N=3066)

| Skupina | Alpha 30D | Win Rate | N |
|---|---|---|---|
| MLE_ONLY | **+1.43%** | 54.5% | 2,061 |
| IMS_ONLY | +0.73%* | 46.1% | 3,066 |
| MLE+IMS_70-79 | +0.19% | 51.0% | 907 |
| MLE+IMS_80-89 | +0.04% | 50.4% | 1,201 |
| MLE+IMS_90-94 | +0.46% | 52.6% | 211 |

*Poznamka: IMS_ONLY alpha v poslednim behu zobrazena jako +0.73%,
v predchozim testovacim behu jako -0.69% az -0.73% (zavisi na presnem
datovem rozsahu run-to-run). Smer zaveru se nemeni — IMS_ONLY winrate
pod 50% je konzistentni signal slabosti samostatneho IMS filtru bez MLE.

**H-001 NOT SUPPORTED** — MLE+IMS_90-94 (+0.46%) nepřekonává MLE_ONLY (+1.43%) o pozadovany prah.
**H-002 NOT SUPPORTED** — zadna kombinace neprekonava MLE_ONLY.
**H-003 NOT SUPPORTED** — zadny monotonni vztah mezi IMS buckety.

### Klicove pozorovani — kontraintuitivni smer

```
MLE_ONLY (+1.43%) > MLE+IMS_90-94 (+0.46%)
```

Filtrovani MLE TOP20 podle vysokeho IMS skore **snizuje** prumernou alpha
oproti nefiltrovane MLE TOP20 mnozine. To je opacny smer nez puvodni
hypoteza predpokladala.

### Bug nalezen a opraven behem tohoto vyzkumu

Puvodni implementace `_assign_group()` obsahovala logickou chybu —
for-cyklus tise zahazoval skoro vsechny kandidaty pro IMS_ONLY skupinu
(N=6 namisto spravneho N≈3000). Oprava nezmenila smer zaveru, pouze
zvysila spolehlivost IMS_ONLY srovnani.

---

## Proc nebyl tento vysledek interpretovan jako "IMS nefunguje"

Testovana hypoteza byla specificka:
> Prekryv dvou NEZAVISLE definovanych skupin (MLE TOP20 a IMS score bucket)
> vytvari lepsi signal nez kazda skupina samostatne.

Tato formulace nerozlisuje mezi:
- IMS jako samostatny screening modul (jina otazka, jiz castecne
  zodpovezena v KR-2026-06-IMS-score-buckets)
- IMS jako prioritizacni filtr UVNITR MLE TOP20 mnoziny (jina statisticka
  otazka — neresena timto experimentem)

Zaver se vztahuje pouze k prvni formulaci.

---

## Kdy platí

- S&P 500 universe, MLE TOP20 (rank_10d), IMS legacy buckety
- Backtest 2025-07-09 -> 2026-06-29
- Pouze pro formulaci "prekryv dvou nezavislych mnozinr"

## Kdy neplatí / nevalidováno

- Jemnejsi formulace (IMS jako prioritizace uvnitr MLE) — NEVALIDOVANO,
  vyzaduje RP-0003 (viz Doporuceni)
- RISK_OFF podminky
- Mimo S&P 500

---

## Confidence: LOW — odůvodnění

- Evidence Level B, jeden backtest, bez rolling validace
- Negativni vysledek pro specifickou formulaci — neuzavira otazku obecne
- Bug v implementaci nalezen a opraven behem tohoto cyklu (transparentne
  zaznamenano), zvysuje duveryhodnost finalniho vysledku ale upozornuje
  na nutnost peclive kontroly definic skupin v budoucich experimentech

---

## Doporučení pro budoucí výzkum

**RP-0003 (navrh) — MLE-conditioned IMS prioritization**

Jemnejsi formulace otazky:
> Pomaha IMS prioritizovat kandidaty UVNITR jiz vybraneho MLE univerza?

Konkretni rezy dat k otestovani:
1. Vezmi pouze MLE TOP20. Uvnitr teto mnoziny porovnej:
   IMS<70 vs IMS 70-79 vs IMS 80-89 vs IMS 90+
   (na rozdil od tohoto experimentu — VSECHNY tyto skupiny jsou podmnozinou MLE TOP20)
2. Vezmi pouze IMS 90+. Uvnitr teto mnoziny porovnej:
   MLE TOP5 vs MLE TOP10 vs MLE TOP20 vs MLE none
3. Statisticka vyznamnost (bootstrap CI, Mann-Whitney) pro oba rezy
