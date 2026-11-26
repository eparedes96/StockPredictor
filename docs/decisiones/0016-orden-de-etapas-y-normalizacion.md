# ADR 0016: Orden de etapas y quién normaliza (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. (C16 de la auditoría). Matizado por el ADR 0024: la normalización por defecto pasa a ser por rango, sin estado por fold; el orden de etapas se mantiene.

**Contexto.** La normalización cross-sectional y el winsorizing se atribuían a P3 (etapa final), a P4 (la bruta) y a P5/P6 (fit por fold) sin que ningún subcomando los ejecutara después de `features`.

**Decisión.** Orden: **panel de `transform`** (alineado) → **`features`** (columnas brutas; P4 solo declara qué se normaliza) → **`dataset`** (guarda features crudas) → **`fit` por fold** en entrenamiento. Los transformadores de winsorizing, normalización e imputación se implementan en `transform/` con `fit`/`transform`/`save`/`load` y estado en JSON; la fase de entrenamiento los ajusta con el train de cada fold. El subcomando `transform` produce solo el panel. `price_for_returns` y `price_for_returns_kind` son columnas del panel, no features.

**Alternativas.** Normalizar en una etapa final de `transform` sobre toda la muestra (fuga); duplicar la lógica en `features`.

**Consecuencias.** El dataset no contiene features normalizadas. La inferencia aplica los transformadores guardados con el modelo. Winsorizing con percentiles [1, 99] ajustados con train; imputación a 0 más indicador solo para modelos lineales.
