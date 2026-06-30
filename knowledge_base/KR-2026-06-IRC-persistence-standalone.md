# Knowledge Record: IRC Persistence — Samostatny test (bez MLE)

```yaml
kr_id:          KR-2026-06-IRC-persistence-standalone
status:         ACTIVE
confidence:     LOW
evidence_level: B
created:        2026-06-30
last_reviewed:  2026-06-30
supersedes:     null
superseded_by:  null
source_project: RP-0006-IRC-PERSISTENCE
```

---

## Research Lineage

```yaml
lineage:
  inspired_by:
    - ref: KR-2026-06-MLE-IRC-rolling
      type: knowledge_record
      note: "Snaha najit druhy nezavisly edge vedle MLE x IRC"
  inspired:
    - ref: KR-2026-06-MLE-rank-value-decay
      type: knowledge_record
      note: "Nezdar samostatneho IRC posilnil zameneni pozornosti
             na MLE-centricke smery vyzkumu"
  produced_rules: []
```

---

## Evidence

```yaml
supported_by:
  - ref: "IRCPersistenceEdge v1.0.0"
    type: experiment
    note: "Industry-level test, bez MLE filtru, 195 obchodnich dni"
```

---

## Co bylo zjisteno

### Vysledky (industry-level, alpha vs SPY, 30D)

```
NEW_TOP10          -1.09%   N=209
EMERGING_TOP10      -0.66%   N=302
PERSISTENT_TOP10     -0.00%   N=887
EXTENDED_TOP10        -0.07%   N=552

Diff (PERSISTENT vs NEW): +1.08pp
H: formalne SUPPORTED
```

### KRITICKE — vsechny buckety jsou negativni nebo nulove

Hypoteza H-001 byla formalne potvrzena (persistentni industries jsou
relativne lepsi nez nove vstoupive), ale **zadny bucket nepřekonava
SPY v absolutnim vyjadreni**. Nejlepsi bucket (PERSISTENT_TOP10) je
prakticky na urovni trhu (-0.00%), ne nad nim.

To je kvalitativne jiny typ vysledku nez MLE x IRC, kde MLE+IRC_TOP
byla vyrazne v kladnem pasmu (+1.25% az +2.15% v gridu).

### Interpretace

Samotna IRC industry sila BEZ MLE asset-level filtru NENI samostatny
edge generator. IRC relativni poradi (persistence pomaha v ramci
sebe sama) je validni, ale absolutne slaby signal.

Toto podporuje puvodni architektonicky zaver z KR-2026-06-MLE-IRC-interaction:
IRC funguje jako **kontextovy modifikator** MLE selekce, ne jako
nezavisly zdroj alfa.

**Tento experiment NEPOTVRDIL IRC jako druhy nezavisly robustni edge.**

---

## Architektonicky dopad

Hledani druheho nezavisleho edge pokracuje jinym smerem
(viz KR-2026-06-MLE-rank-value-decay — MLE rank profil je nyni
sam o sobe kandidat na samostatnou linii poznani, i kdyz stale
v ramci MLE rodiny).

---

## Kdy plati

- S&P 500, IRC TOP10 (lookback 20D), persistence okno 20D
- Backtest 2025-07-09 -> 2026-06-29

## Kdy neplati / nevalidovano

- Jako samostatny produkcni signal — vsechny buckety NEPREKONAVAJI trh
- RISK_OFF podminky
- Robustness grid a rolling validation NEBYLY provedeny (zastaveno
  po single-point vysledku kvuli slabe absolutni vykonnosti)

---

## Confidence: LOW — odůvodnění

- Evidence Level B, jeden backtest
- Relativni hypoteza formalne SUPPORTED, ale absolutni vykon negativni
  ve vsech bucketech — slaba prakticka hodnota
- Dalsi validace (grid, rolling) zastavena jako neefektivni use of
  research effort vzhledem k slabemu signalu

---

## Doporuceni pro budouci vyzkum

- Negenerovat dalsi IRC-standalone experimenty bez MLE kontextu,
  pokud nevznikne nova hypoteza s odlisnou metodikou
- Energie vyzkumu prioritne na MLE rank profil a jeho rolling validaci
  (viz KR-2026-06-MLE-rank-value-decay doporuceni)
