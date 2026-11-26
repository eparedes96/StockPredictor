Construir StockPredictor: un pipeline de punta a punta que predice el retorno absoluto de acciones individuales a N días (N variable: 90, 365, 1500...), con datos gratuitos (APIs y scraping).

Etapas del pipeline:
1. Extracción de datos brutos de empresas y cotización: precios OHLCV, fundamentales trimestrales con su fecha real de publicación, datos de referencia (sector, bolsa, divisa), macro y composición histórica de índices, incluidas empresas desaparecidas.
2. Transformación: alineación temporal sin look-ahead (as-of por fecha de publicación), TTM, ratios de rentabilidad, solvencia y valoración, indicadores técnicos, normalización por sector y fecha, tratamiento de nulos, negativos y outliers.
3. Diseño del entrenamiento: selección de modelo (Ridge de baseline, LightGBM principal), hiperparámetros, validación walk-forward con embargo y purga, métricas estadísticas y financieras (RankIC, Sharpe, drawdown con costes).
4. Dataset de entrenamiento versionado, entrenamiento y test por horizonte.
5. Inferencia: extraer datos recientes y predecir con el modelo registrado, reutilizando el mismo código de features.
6. Reentrenamiento y mejora continua: detección de drift, champion/challenger, registro de modelos y predicciones.

Fases del universo: F1 IBEX 35, F2 con Nasdaq-100, F3 todos los mercados con acciones individuales accesibles desde España.

Reglas que mandan sobre todo lo demás: sin look-ahead, sin fugas entre train y test, sesgo de supervivencia siempre declarado, y ninguna métrica o dato de proveedor presentado sin haberlo verificado. Lo detallado está en las instrucciones del proyecto y en el CLAUDE.md del repositorio.

Quiero que cuestiones mis decisiones cuando tengan fallos, que preguntes cuando algo sea ambiguo y que me des opciones con evidencia cuando haya trade-offs.
