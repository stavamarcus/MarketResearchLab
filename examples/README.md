# Examples

Ukázka výstupů MRL experimentu.

Slouží jako reference pro nového vývojáře nebo při kontrole formátu.

## Soubory

| Soubor | Popis |
|---|---|
| `example_report.md` | Ukázka report.md generovaného ReportBuilderem |
| `example_metrics.json` | Ukázka metrics.json uloženého ArchiveManagerem |

## Kde vznikají skutečné výstupy

```
results/
└── {experiment_name}/
    └── {version}/
        └── {run_id}/
            ├── metadata.json
            ├── config.yaml
            ├── metrics.json
            ├── tables/
            └── report.md

registry/
└── experiment_runs.jsonl
```

Tyto adresáře jsou prázdné po instalaci a vznikají při prvním spuštění experimentu.
Nejsou verzovány (viz `.gitignore`).
