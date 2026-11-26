# ADR 0009: Aclaración de la regla 2, versión conocida en cada fecha (2026-11-26)
**Estado.** Aceptado por Enrique. (decisión 12a de P3).

**Contexto.** La regla 2 prohíbe cifras reexpresadas "si existe versión original", lo que se podía leer como "usar siempre la primera versión". P3 comparó dos lecturas: la versión conocida en cada fecha, o solo la primera.

**Decisión.** Se usa la **versión conocida en cada fecha** (as-known-at-t): la última con `available_at` ≤ la sesión. Una reexpresión entra solo desde su `available_at`. La primera versión se conserva como diagnóstico (`first_release_value`, `n_restatements`). Aplica a todos los mercados, también Brasil (donde la CVM da `VERSAO` y `DT_RECEB`).

**Alternativas.** Usar solo la primera versión (más pura frente a reexpresiones, pero ignora información realmente pública y complica la comparación entre mercados).

**Consecuencias.** `interim` guarda todas las versiones (bitemporal). Se declara en `docs/limitaciones.md` que macro europea anterior a la instantánea propia es la versión revisada (`not_point_in_time`).
