# Research Projects

Každý projekt řeší jednu výzkumnou otázku a prochází plným governance lifecycle.

## Konvence adresářů

```
research_projects/
├── _template/               ← kopírovat pro nový projekt
│   └── PROJECT.md
│
├── RP-2026-06-MRC/          ← Market Regime Classifier (aktivní)
│   └── PROJECT.md
│
└── RP-2026-06-IRC-edge/     ← IRC Persistence Edge (uzavřen → KR)
    └── PROJECT.md
```

## Konvence pojmenování

```
RP-{YYYY-MM}-{název}
```

## Lifecycle statusy

| Status | Meaning |
|---|---|
| IDEA | Nápad, zatím bez formální otázky |
| RESEARCH_QUESTION | Otázka formulována |
| HYPOTHESIS | Hypotéza definována |
| EXPERIMENTS | Experimenty probíhají |
| EVIDENCE | Agregace výsledků |
| CONCLUSION | Závěr strukturován |
| RESOLUTION | Architekt rozhodl |
| KNOWLEDGE_RECORD | Znalost uložena do Knowledge Base |

## Aktivní projekty

| Projekt | Oblast | Status | Priorita |
|---|---|---|---|
| MRC (Market Regime Classifier) | Risk Regimes | HYPOTHESIS | BLOCKER |

## Uzavřené projekty

| Projekt | Oblast | Resolution | KR |
|---|---|---|---|
| IRC Persistence Edge | Industry Rotation | APPROVED_WITH_RESTRICTIONS (čeká na MRC) | KR-2026-06-IRC-persistence-edge |
