# StockPredictor
Python pipeline that predicts N-day absolute stock returns (90, 365, 1500...) from free data. It uses point-in-time features with no look-ahead, walk-forward validation with an embargo, LightGBM and champion/challenger retraining.

Pipeline para predecir el retorno absoluto de acciones a N días. Reglas en `CLAUDE.md`. Estructura en `docs/estructura_proyecto.md`.
Fases: F1 IBEX 35, F2 + Nasdaq-100, F3 todos los mercados accesibles desde España.
`tmp/` es temporal y se puede vaciar.

Es investigación cuantitativa; ningún resultado es una recomendación de inversión.
