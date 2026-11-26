# ADR 0018: Retención de `raw` (2026-11-26)
**Estado.** Aceptado por Enrique. (lectura confirmada de la decisión 11a).

**Contexto.** P0 y P1 decían "`raw` vigente se conserva; no se archiva"; P8 pedía archivar `raw` comprimido y purgar lo regenerable.

**Decisión.** Un `raw` referenciado por el manifiesto de un dataset o de un modelo registrado **se conserva** y es restaurable con hash. Lo demás se archiva comprimido con manifiesto, o se mueve a local en el caso de pruebas de desarrollo. Lo regenerable (panel de features, runs antiguos) se purga. Cada archivo lleva estado en el manifiesto (`current`, `test`, `archived`). Todo con `--dry-run` por defecto.

**Alternativas.** No borrar ni mover nada; purga automática por antigüedad (puede romper la reproducibilidad de un modelo vivo).

**Consecuencias.** Hace falta un módulo de manifiestos antes del primer `raw`. Las predicciones archivadas no se pueden regenerar: copia de seguridad fuera del equipo, ver `docs/mlops.md`.
