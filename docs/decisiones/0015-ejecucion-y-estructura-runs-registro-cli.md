# ADR 0015: Ejecución y estructura, `runs/`, registro de modelos, CLI y pandas aislado (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. (C2, C6, C7, C14 de la auditoría).

**Contexto.** Los planes mencionaban `runs/` y `experiments/` sin reparto, tres rutas distintas para el registro de modelos, `scripts/` y subcomandos como vías de lanzamiento, y el ADR 0003 prohíbe pandas por lint salvo en `training/` y `evaluation/`, mientras los calendarios (`exchange_calendars`) y la implementación de referencia de tests lo necesitan.

**Decisión.** (1) `experiments/` guarda los runs de entrenamiento y evaluación, el registro de accesos al test y las promociones y rollbacks; `runs/` guarda los resúmenes de ejecución de las etapas (`fetch`, `transform`, `features`, `dataset`, `predict`, `monitor`, calidad), fuera de git y purgable. (2) Registro de modelos: `models/{universe_id}/h{N}/v{versión}/`, con `CHAMPION` por universo y horizonte; el estado de los transformadores y el preprocesador viajan con el modelo. (3) Los subcomandos de la CLI (`stockpredictor <etapa>`) son la única vía de lanzamiento; `scripts/` solo contiene envoltorios finos. (4) El código con pandas para generar calendarios vive en `tools/calendars/` (subcomando `calendars`, extra `calendars`) y la referencia de tests en el grupo `dev`; ruff lo permite solo en esas rutas y en `training/`, `evaluation/` y `tests/`.

**Alternativas.** Un solo directorio para runs y experimentos; `scripts/` como vía principal; relajar el lint de pandas globalmente.

**Consecuencias.** Se actualizan `estructura_proyecto.md`, `models/README.md` y `pyproject.toml` (excepción de ruff). La retención: `runs/` purgable; `experiments/` con test y modelos registrados, no.
