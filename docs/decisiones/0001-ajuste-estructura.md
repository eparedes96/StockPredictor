# ADR 0001: Ajuste de la estructura base (2026-11-25)
**Contexto.** Revisión de la estructura inicial antes de escribir código.
**Decisión.**
1. `transform/` nuevo para alineación point-in-time, TTM, nulos, winsorizing y normalización; `features/` solo ratios y técnicos.
2. `validation_data/` pasa a `quality/` (evita confusión con validación de modelos).
3. `universe/` nuevo y `data/reference/`: composición histórica de índices. Sin universo de delisted (solo empresas de índices populares), pero las empresas que entraron y salieron del índice se mantienen para evitar sesgo de supervivencia.
4. polars + DuckDB como stack; pandas solo como extra opcional en el borde de LightGBM/scikit-learn si lo exigen (sin verificar).
5. Registro de modelos `models/h{N}/v{versión}/` con `metadata.json` y `CHAMPION` por horizonte. Binarios fuera de git.
6. Se borran `estructura_proyecto.md` e `instrucciones_proyecto.md` de la raíz (obsoletos).
**Alternativas.** Mantener features/ monolítico (más difícil de testear contra fugas); pandas y polars a la vez (duplica código).
**Consecuencias.** CLAUDE.md cambia: debe repegarse en las instrucciones del proyecto.
