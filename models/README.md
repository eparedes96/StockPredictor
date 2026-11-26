# Registro de modelos
Un subdirectorio por universo, horizonte y versión: `models/{universe_id}/h{N}/v{AAAAMMDD-n}/` (ADR 0015). Un modelo por horizonte y universo (Europa, small caps, S&P 500...).

```
models/
└── {universe_id}/
    ├── h90/
    │   ├── CHAMPION                 # texto: versión vigente; cambia solo con `stockpredictor promote`
    │   └── v20261125-1/
    │       ├── metadata.json        # ver abajo
    │       ├── preprocessor/        # estado de winsorizing, normalización e imputación (JSON)
    │       └── model.*              # binario (fuera de git; formato sin código ejecutable)
    ├── h365/
    └── h1500/
```

## `metadata.json` (campos mínimos)
- `horizon_days`, `universe_id`, `model_type`, `version`, `created_at`, `status` (challenger | champion | retired)
- `features`: lista ordenada de columnas y versión de `configs/features.yaml`
- `train_start`, `train_end`, `embargo_sessions`, `purge`
- `dataset_version` y `data_hash`; `data_as_of` (fecha de corte y composición vigente)
- `config_hash` y `git_commit`
- `metrics`: estadísticas y financieras (RankIC, Sharpe, drawdown con costes supuestos) por fold y agregadas, con ventanas independientes efectivas y la etiqueta de viabilidad (`viable` | `exploratory` | `not_evaluable`)
- `survivorship_label`: "con sesgo de supervivencia" mientras aplique
- `parent_version`: champion al que desafía o sustituye
- Dominio: universo, divisa y calendario (para la versión ligera)

Cada predicción guarda `model_version` y `data_as_of`. Los baselines también se registran.
