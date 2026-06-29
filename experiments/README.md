# Experimenty

## Adresářová struktura

```
experiments/
├── templates/
│   └── experiment_template.py   ← výchozí šablona
├── edge_validation/             ← vznikne při první migraci
├── backtesting/
├── hypothesis_testing/
├── module_comparison/
└── strategy_audit/
```

Podadresáře kategorií vznikají postupně — při první potřebě.

## Vytvoření nového experimentu

1. Zkopíruj `templates/experiment_template.py` do příslušné kategorie.
2. Přejmenuj soubor: `{název}_{kategorie}_v{verze}.py`
3. Přejmenuj třídu: `{Název}_v{verze}`
4. Implementuj `define()`, `validate_inputs()`, `run()`.
5. Spusť přes `ExperimentRunner` v `main.py`.

## Pravidla

- Experiment nesmí volat produkční moduly (MLE, IMS, IRC) přímo.
- Experiment nesmí zapisovat soubory — to zajišťuje framework.
- `run()` musí být čistá funkce — žádné side effects.
- Verze v `ExperimentDefinition.version` musí odpovídat verzi v názvu třídy.
