# Estructura de carpetas y archivos

Pensada para repositorio Python. Un módulo por etapa del pipeline, con la lógica de features compartida entre entrenamiento e inferencia. Actualizada el 2026-11-26 con la planificación P0 a P8 (ADR 0003 a 0018). Lo marcado *(vacío)* existe como carpeta y se rellena por fase.

```
stockpredictor/
├── README.md                    # Qué es, cómo ejecutar cada etapa
├── CLAUDE.md                    # Instrucciones permanentes (de instrucciones_proyecto.md)
├── pyproject.toml, uv.lock, .python-version   # Entorno fijado (ADR 0003)
├── .env.example                 # Plantilla de secretos; .env no se versiona
├── configs/
│   ├── universe.yaml            # Fase activa, mercados por fase, filtros, umbrales de cobertura
│   ├── markets/                 # Ficha por mercado: calendario, divisa, zona horaria, fuentes, estado, valuation_enabled
│   ├── indices/                 # Extractor de composición por índice (fuente, formato)
│   ├── horizons.yaml            # Horizontes activos (90, 365), h1500 descriptivo, muestreo de fechas
│   ├── preregistered.yaml       # Cantidades pre-registradas con nombre propio (ADR 0020); provisional hasta firmar
│   ├── data_sources.yaml        # Proveedores, límite de tasa, caché (sin robots.txt, ADR 0010)
│   ├── features.yaml            # Ventanas, winsorizing, política de nulos por variable
│   ├── target.yaml              # Target transversal y componente de mercado, price_for_returns, return_currency
│   ├── validation.yaml          # Walk-forward, purga y calendario de reserva global
│   ├── quality.yaml, transform.yaml, dataset.yaml, evaluation.yaml,
│   │   inference.yaml, monitoring.yaml, retention.yaml   # umbrales provisionales o por definir
│   └── models/                  # Un YAML por algoritmo (ridge, lgbm, xgb, catboost)
├── data/                        # Fuera de git (solo .gitkeep)
│   ├── raw/                     # Instantáneas inmutables, por proveedor y fecha, con manifiesto
│   ├── reference/               # index_membership/, universe_membership, exit_events, tasas legales (con proveedor y fecha)
│   ├── interim/                 # Limpio, tipado, bitemporal; _quarantine/ y _reports/
│   ├── features/                # Panel por (security_id, sesión) con features, regenerable
│   ├── datasets/                # {universe_id}/h{N}/v{hash}/ versionados
│   ├── predictions/             # Archivo inmutable de predicciones (paper trading)
│   ├── snapshots/, archive/, user/   # Entradas de inferencia, raw archivado y datos propios del usuario
├── src/stockpredictor/
│   ├── extraction/              # 1. Extracción
│   │   ├── prices.py            # OHLCV, adjusted close, splits, dividendos
│   │   ├── fundamentals.py      # PyL, balance, cash flow con filing/accepted date
│   │   ├── reference.py         # País, bolsa, sector, divisa
│   │   ├── macro.py             # Tipos, IPC, PIB (con fecha de publicación/vintage), FX, índice
│   │   ├── scrapers/            # Scrapers (CNMV, composición histórica de índices) con caché y límite de tasa; extractores por mercado en extraction/{mercado}/ con pruebas de humo
│   │   ├── sec_edgar.py         # Fundamentales EE. UU. (F2), con fecha de aceptación del filing
│   │   ├── cnmv.py              # Fundamentales IBEX (F1), ESEF/XBRL y PDF
│   │   └── cache.py             # Evita descargas repetidas, registra proveedor y fecha
│   ├── interim/                 # raw -> interim: todas las versiones con available_at (bitemporal) (vacío)
│   ├── quality/                 # Contratos y control de calidad de datos (no confundir con validación de modelos)
│   │   ├── schemas.py           # Esquemas por tabla (pandera sobre polars) con schema_version; incluye panel, features y predicciones
│   │   └── quality_checks.py    # Duplicados, huecos, outliers contables, identidades (Activos = Pasivo + Equity)
│   ├── universe/                # Universo point-in-time (datos en data/reference/)
│   │   ├── constituents.py      # Composición histórica de índices: altas, bajas y fechas
│   │   └── membership.py        # Miembros vigentes en cada fecha; sector y bolsa vigentes
│   ├── transform/               # 2a. Alineación point-in-time y tratamiento (compartido con inferencia)
│   │   ├── calendar.py          # Calendarios Parquet por mercado (sin asumir mercado único)
│   │   ├── base.py, versions.py, shares.py, market_series.py   # protocolo fit/transform/save/load, versión vigente, acciones, series de otro calendario
│   │   ├── align.py             # merge_asof por available_at, ffill por empresa, days_since_report; price_for_returns en el panel
│   │   ├── ttm.py               # TTM y crecimiento YoY
│   │   ├── macro_align.py       # Alineación de macro por fecha de disponibilidad
│   │   ├── missing.py           # Política de nulos, indicadores de ausencia
│   │   ├── winsorize.py         # Transformador con fit (solo train) y transform
│   │   └── normalize.py         # Z-score/percentil por sector y fecha, escalado (fit solo en train)
│   ├── features/                # 2b. Ratios e indicadores (compartido con inferencia; no une tablas por fecha)
│   │   ├── fundamentals.py      # Márgenes, ROE/ROA/ROIC, solvencia, eficiencia
│   │   ├── valuation.py         # Market cap, P/E, P/B, EV/EBITDA, P/S, PEG, yield (con Close sin ajustar)
│   │   ├── technical.py         # Retornos, volatilidad, MA, RSI, MACD, beta
│   │   ├── macro_features.py    # Features derivadas de macro ya alineada (cambios, diferenciales)
│   │   ├── registry.py          # Registro de features (YAML + test de completitud)
│   │   └── pipeline.py          # Orquestación única: panel de transform → features (la normalización con fit va por fold, ADR 0016)
│   ├── dataset/
│   │   ├── target.py            # Target por N (días naturales) y comprobación anti-fuga
│   │   ├── build.py             # Dataset por horizonte, elegibilidad, versionado
│   │   ├── splits.py            # Walk-forward con purga por label_end_date
│   │   ├── effective_n.py       # Ventanas independientes, regla de viabilidad y MDE
│   │   └── manifest.py          # Hash, instantánea y configuración
│   ├── training/                # 3. Diseño de entrenamiento
│   │   ├── models.py            # Baselines y GBM
│   │   ├── tuning.py            # Búsqueda de hiperparámetros (solo sobre train)
│   │   └── train.py             # Entrenamiento por fold (fit de transformadores con el train) y registro del modelo
│   ├── evaluation/
│   │   ├── metrics.py           # RMSE/MAE/AUC + RankIC, Sharpe, drawdown con costes (única definición; la reutiliza monitoring)
│   │   ├── backtest.py          # Quintiles solo largos, costes de transacción supuestos
│   │   └── reports.py           # Informes por periodo, sector y régimen, con N_eff y etiqueta de viabilidad
│   ├── registry/                # Lectura/escritura del registro en models/ y paquete exportable (vacío)
│   ├── inference/               # 4. Inferencia
│   │   ├── fetch_latest.py      # Extracción incremental de datos recientes
│   │   ├── predict.py           # Carga el modelo registrado, reutiliza transform/ y features/
│   │   └── store.py             # Guarda predicciones con versión del modelo y data_as_of
│   └── monitoring/              # 5. Reentrenamiento y mejora continua
│       ├── drift.py             # Drift de features y de RankIC rodante
│       ├── retrain.py           # Disparadores y reentrenamiento programado
│       └── promote.py           # Champion/challenger, promoción o rollback
├── models/                      # Registro: models/{universe_id}/h{N}/v{versión}/ + CHAMPION por universo y horizonte (ver models/README.md)
├── experiments/                 # Runs de entrenamiento y evaluación, accesos al test, promociones
├── runs/                        # Resúmenes de ejecución de las etapas; fuera de git, purgable
├── notebooks/                   # Exploración; nada que el pipeline necesite
├── tools/calendars/             # Generación de calendarios a Parquet (usa pandas; extra `calendars`; excepción de ruff acotada)
├── tests/
│   ├── fixtures/                # Datos sintéticos compartidos
│   ├── unit/                    # Fórmulas (ROIC, TTM, márgenes...)
│   ├── leakage/                 # Tests anti look-ahead y de purga, con dos calendarios
│   └── integration/             # Pipeline completo con datos sintéticos; la muestra real solo en local
├── scripts/                     # Solo envoltorios finos; la vía de ejecución es la CLI `stockpredictor <etapa>` (ADR 0015)
└── docs/
    ├── plan_modelo.md           # Plan de modelo original
    ├── plan_datos.md            # Plan de datos original (tablas 1-3)
    ├── convenciones.md          # available_at, timing, divisa, definición de N, glosario de columnas
    ├── limitaciones.md          # Limitaciones de datos conocidas (restatements, GICS histórico...)
    ├── mlops.md                 # Inferencia, disparadores, promoción y rollback
    ├── verificaciones.md        # (a crear) resultado de cada verificación técnica pendiente
    └── decisiones/              # ADRs, incluido pendientes.md
```

## Propósito por bloque
| Bloque | Propósito |
| --- | --- |
| `configs/` | Todo parámetro que cambie resultados vive aquí, no en el código. |
| `data/raw` | Fuente de verdad inmutable: permite reconstruir todo y auditar proveedores. |
| `extraction/` | Un conector por tipo de dato, con proveedor intercambiable. |
| `quality/` | Detecta datos rotos antes de entrar al pipeline. |
| `universe/` | Composición histórica de índices: evita el sesgo de supervivencia por usar solo los constituyentes actuales. |
| `transform/` | Alineación point-in-time, TTM, nulos, winsorizing y normalización. Aislado para testear el anti look-ahead. |
| `features/` | Ratios y técnicos; única implementación, usada por entrenamiento e inferencia. |
| `training/` y `evaluation/` | Validación walk-forward, tuning y backtest realista con costes. |
| `inference/` | Predicción diaria o semanal reutilizando `features/`. |
| `monitoring/` | Detecta degradación y gestiona la promoción de modelos. |
| `models/` | Registro por universo, horizonte y versión con metadata; base del reentrenamiento y del champion/challenger. |
| `tests/leakage/` | Protege la regla más importante del proyecto. |
| `docs/decisiones/` | Memoria de por qué se eligió cada cosa. |

## Fases
| Fase | Universo | Objetivo |
| --- | --- | --- |
| F1 | IBEX 35 | Pipeline completo de punta a punta, con tests de fuga y limitaciones documentadas |
| F2 | + Nasdaq-100 | Segundo mercado: valida el diseño multi-mercado (FX, calendarios, SEC EDGAR) |
| F3 | Mercados con ficha lista, de uno en uno | Escala; cada mercado exige ficha, informe de cobertura y de sesgo y tres extracciones reales reproducibles (ADR 0011) |

## Orden de construcción sugerido (F1)
1. Tests con datos sintéticos y esqueleto de contratos → 2. Guardar ya las instantáneas de macro europea (cada semana sin guardar es historia irrecuperable) → 3. `extraction/` + `data/raw` (composición, precios, macro y referencia, fundamentales CNMV) → 4. `interim/` con contratos → 5. `transform/` (incluido `price_for_returns`) y tests de fuga → 6. `features/` y target con N parametrizable → 7. dataset, splits y N_eff → 8. baselines y Ridge → 9. LightGBM → 10. inferencia → 11. monitorización y reentrenamiento. Antes de la primera ejecución real: ADR de pre-registro.
