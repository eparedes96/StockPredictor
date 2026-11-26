# Estructura de carpetas y archivos

Pensada para repositorio Python. Un módulo por etapa del pipeline, con la lógica de features compartida entre entrenamiento e inferencia.

```
stockpredictor/
├── README.md                    # Qué es, cómo ejecutar cada etapa
├── CLAUDE.md                    # Instrucciones permanentes (de instrucciones_proyecto.md)
├── pyproject.toml / lockfile    # Dependencias fijadas
├── configs/
│   ├── universe.yaml            # Fase activa (ibex35 | +nasdaq100 | all), mercados, filtros
│   ├── markets.yaml             # Por mercado: calendario, divisa, zona horaria, proveedor
│   ├── horizons.yaml            # Lista de N (90, 365, 1500...) y un modelo por cada uno
│   ├── data_sources.yaml        # Proveedores, endpoints, límites, mapeo de campos
│   ├── features.yaml            # Ventanas, winsorizing, política de nulos por variable
│   ├── target.yaml              # N, tipo (retorno/exceso/clase), precio de ejecución
│   ├── validation.yaml          # Walk-forward: ventanas, embargo, purga
│   └── models/                  # Un YAML por algoritmo (ridge, lgbm, xgb, catboost)
├── data/                        # Fuera de git (DVC o similar)
│   ├── raw/                     # Descargas inmutables, por proveedor y fecha
│   ├── reference/               # Composición histórica de índices y datos de referencia (con proveedor y fecha)
│   ├── interim/                 # Limpio y tipado, aún sin features
│   ├── features/                # Panel (ticker, date) con features
│   └── datasets/                # Datasets de entrenamiento versionados
├── src/stockpredictor/
│   ├── extraction/              # 1. Extracción
│   │   ├── prices.py            # OHLCV, adjusted close, splits, dividendos
│   │   ├── fundamentals.py      # PyL, balance, cash flow con filing/accepted date
│   │   ├── reference.py         # País, bolsa, sector, divisa
│   │   ├── macro.py             # Tipos, IPC, PIB (con fecha de publicación/vintage), FX, índice
│   │   ├── scrapers/            # Scrapers (CNMV, composición histórica de índices) con caché y límite de tasa
│   │   ├── sec_edgar.py         # Fundamentales EE. UU. (F2), con fecha de aceptación del filing
│   │   ├── cnmv.py              # Fundamentales IBEX (F1), ESEF/XBRL y PDF
│   │   └── cache.py             # Evita descargas repetidas, registra proveedor y fecha
│   ├── quality/                 # Contratos y control de calidad de datos (no confundir con validación de modelos)
│   │   ├── schemas.py           # Esquemas por tabla
│   │   └── quality_checks.py    # Duplicados, huecos, outliers contables, identidades (Activos = Pasivo + Equity)
│   ├── universe/                # Universo point-in-time (datos en data/reference/)
│   │   ├── constituents.py      # Composición histórica de índices: altas, bajas y fechas
│   │   └── membership.py        # Miembros vigentes en cada fecha; sector y bolsa vigentes
│   ├── transform/               # 2a. Alineación point-in-time y tratamiento (compartido con inferencia)
│   │   ├── align.py             # merge_asof por available_at, ffill por empresa, days_since_report
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
│   │   └── pipeline.py          # Orquestación única: universe → transform → features → transform (normalización)
│   ├── target.py                # Cálculo del target y comprobación anti-fuga
│   ├── dataset/
│   │   └── build.py             # Panel final, filtros de universo, split temporal, versionado
│   ├── training/                # 3. Diseño de entrenamiento
│   │   ├── cv.py                # Walk-forward con embargo y purga
│   │   ├── models.py            # Baselines y GBM
│   │   ├── tuning.py            # Búsqueda de hiperparámetros (solo sobre train)
│   │   ├── metrics.py           # RMSE/MAE/AUC + RankIC, Sharpe, drawdown con costes
│   │   ├── registry.py          # Lectura/escritura del registro en models/
│   │   └── train.py             # Entrenamiento y registro del modelo
│   ├── evaluation/
│   │   ├── backtest.py          # Long/short o top-decil, costes de transacción
│   │   └── reports.py           # Informes de resultados por periodo, sector y régimen
│   ├── inference/               # 4. Inferencia
│   │   ├── fetch_latest.py      # Extracción incremental de datos recientes
│   │   ├── predict.py           # Carga el modelo registrado, reutiliza features/
│   │   └── store.py             # Guarda predicciones con versión del modelo
│   └── monitoring/              # 5. Reentrenamiento y mejora continua
│       ├── drift.py             # Drift de features y de RankIC rodante
│       ├── retrain.py           # Disparadores y reentrenamiento programado
│       └── promote.py           # Champion/challenger, promoción o rollback
├── models/                      # Registro: models/h{N}/v{versión}/metadata.json + CHAMPION por horizonte (ver models/README.md)
├── experiments/                 # Registro de runs (también de cada consulta al test)
├── notebooks/                   # Exploración; nada que el pipeline necesite
├── tests/
│   ├── unit/                    # Fórmulas (ROIC, TTM, márgenes...)
│   ├── leakage/                 # Tests anti look-ahead: cambiar el futuro no cambia el pasado
│   └── integration/             # Pipeline completo con datos de juguete
├── scripts/                     # CLI: extract, build_features, train, predict, retrain
└── docs/
    ├── plan_modelo.md           # Plan de modelo original
    ├── plan_datos.md            # Plan de datos original (tablas 1-3)
    ├── convenciones.md          # available_at, timing de señal, divisa, definición de N
    ├── limitaciones.md          # Limitaciones de datos conocidas (restatements, GICS histórico...)
    ├── mlops.md                 # Calendario y reglas de reentrenamiento
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
| `models/` | Registro por horizonte y versión con metadata; base del reentrenamiento y del champion/challenger. |
| `tests/leakage/` | Protege la regla más importante del proyecto. |
| `docs/decisiones/` | Memoria de por qué se eligió cada cosa. |

## Fases
| Fase | Universo | Objetivo |
| --- | --- | --- |
| F1 | IBEX 35 | Pipeline completo de punta a punta, con tests de fuga y limitaciones documentadas |
| F2 | + Nasdaq-100 | Segundo mercado: valida el diseño multi-mercado (FX, calendarios, SEC EDGAR) |
| F3 | Todos los accesibles desde España | Escala; requiere definir la lista de mercados y las composiciones históricas de cada índice |

## Orden de construcción sugerido (F1)
1. Fijar fuentes gratuitas (ADR) → 2. `extraction/` + `data/raw` (precios, fundamentales CNMV, composición histórica) → 3. `align.py` y tests de fuga → 4. `universe/`, features y target con N parametrizable → 5. CV walk-forward y baseline Ridge → 6. LightGBM → 7. inferencia → 8. monitorización y reentrenamiento.
