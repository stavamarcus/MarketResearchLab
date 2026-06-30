# Knowledge Record: Diagnostika IMS_MISSING uvnitr MLE TOP20

```yaml
kr_id:          KR-2026-06-IMS-missing-diagnosis
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
    - ref: "MLEIMSInteraction v1.1.0"
      type: experiment
      note: "IMS_MISSING vysla jako druha nejsilnejsi skupina (+1.91% alpha,
             N=1605) — vyzadovalo vysvetleni pred jakoukoli interpretaci"
  inspired:
    - ref: "RP-0003 hlavni hypoteza (IMS<70 vs IMS_90-94)"
      type: research_project
      note: "Diagnoza umoznila pokracovat s cistou interpretaci hlavnich bucketu"
  produced_rules: []
```

---

## Co bylo zjisteno

### Otazka

V experimentu MLEIMSInteraction v1.1.0 (IMS jako prioritizace uvnitr MLE
TOP20) vysla skupina `IMS_MISSING` (MLE TOP20 kandidat bez IMS zaznamu
tento den) jako druha nejsilnejsi: +1.91% alpha, N=1605 (38.1% vsech MLE
TOP20 signalu). To vyzadovalo vysvetleni pred interpretaci ostatnich bucketu.

### Finding — IMS_MISSING ma dve odlisne priciny

```
IMS_MISSING celkem: 1,888 zaznamu (38.1% MLE TOP20 signalu)

  95.8% (1,808) — ticker JE v IMS univerzu, ale tento konkretni den
                  nedosahl IMS score >= 60 (IMS modul publikuje pouze
                  HIGH/RADAR kandidaty se score >= 60 — neni to chyba
                  ani chybejici data, je to navrh IMS modulu)

  4.2%  (80)    — ticker NIKDY nema IMS zaznam za cele sledovane obdobi
                  (napr. CHTR, CPB, FDS, GDDY, GPN, IT, LULU, POOL, TTD,
                  VRSK, ZTS — 11 unikatnich tickeru z teto kategorie)
```

### Interpretace

`IMS_MISSING` **neni** chybejici nebo spatna data. Je to validni signal:
"tato akcie nebyla dostatecne silna na to, aby IMS modul ji ten den
zaradil mezi sledovane kandidaty (score < 60)".

To znamena ze `IMS_MISSING` skupina v MLEIMSInteraction v1.1.0 je
smysluplna kategorie — NE artefakt chyby nebo coverage gap.

### Proc jsou nektere tickery uplne mimo IMS univerzum

11 tickeru (CHTR, CPB, FDS, GDDY, GPN, IT, LULU, POOL, TTD, VRSK, ZTS)
nikdy nedosahly IMS sledovani za cele obdobi. Mozne vysvetleni
(nevalidovano v tomto KR): IMS modul ma vlastni universe definici
odlisnou od MLE/MDSM-Lite universe, nebo tyto akcie soustavne nesplnuji
vstupni kriteria IMS modulu (napr. avg_volume_20d, price_vs_52w_high).
Vyzaduje dalsi vyzkum pokud bude relevantni.

---

## Dopad na interpretaci MLEIMSInteraction v1.1.0

`IMS_MISSING` (+1.91% alpha) by nemela byt interpretovana jako
"chybejici IMS data jsou lepsi nez IMS data" — spravna interpretace je:
"MLE kandidati, kteri NEdosahli IMS score 60+, maji v prumeru vyssi
alpha nez ti, kteri IMS score 60+ dosahli, ale jsou pod 90".

To je v souladu s hlavnim zjistenim KR-2026-06-MLE-IMS-no-synergy:
MLE samotne (bez ohledu na IMS) je silnejsi signal nez MLE filtrovany
pres stredni IMS pasma (70-89).

---

## Kdy plati

- IMS_candidates_archive obsahuje pouze score >= 60 (HIGH/RADAR) — design IMS modulu
- MLE univerzum (503 tickeru) je sirsi nez IMS univerzum (473 tickeru + 24 nikdy nezaznamenanych)

## Doporuceni pro budouci vyzkum

- Pokud bude relevantni: zjistit presnou definici IMS vstupnich kriterii
  pro vysvetleni 11 tickeru zcela mimo IMS univerzum
- Pri jakekoliv interpretaci IMS_MISSING v budoucich experimentech
  odkazovat na tento KR
