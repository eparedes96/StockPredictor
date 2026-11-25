# Registro de modelos

Un subdirectorio por horizonte y versión: `models/h{N}/v{AAAAMMDD-n}/`.

```
models/
├── h90/
│   ├── CHAMPION                 # texto: versión vigente (v...), cambia solo vía monitoring/promote.py
│   └── v20261125-1/
│       ├── metadata.json        # ver abajo
│       └── model.*              # binario (fuera de git)
├── h365/
└── h1500/
```

## `metadata.json` (campos mínimos)
- `horizon_days`, `model_type`, `version`, `created_at`, `status` (challenger | champion | retired)
- `features`: lista ordenada de columnas y versión de `configs/features.yaml`
- `train_start`, `train_end`, `embargo_days`, `purge`
- `dataset_version` y `data_hash`
- `config_hash` y `git_commit`
- `metrics`: estadísticas y financieras (RankIC, Sharpe, drawdown con costes) por fold y agregadas, con observaciones independientes efectivas
- `survivorship_label`: "con sesgo de supervivencia" mientras aplique
- `parent_version`: champion al que desafía o sustituye

Cada predicción guarda `model_version` y `data_as_of`.
