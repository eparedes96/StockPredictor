# ADR 0017: Glosario de columnas y valores en inglés, y marca de datos de prueba (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. (C4, C5, C19 de la auditoría).

**Contexto.** Los planes mezclaban nombres de columna distintos para lo mismo (`close_raw`/`close_real`, tres nombres para composición) y valores en español (`solo_close_real`, `sin_precios`, `accesible_desde_españa`, con "ñ"). Dos flags distintos marcaban datos de prueba.

**Decisión.** Código, columnas y valores en inglés. El glosario canónico vive en `docs/convenciones.md`. Los contratos de datos lo implementan. Un solo flag de prueba, `is_test_data`; la fecha inventada lleva `available_at_source = 'invented_test'`, y `available_at_estimated` queda reservado a estimaciones conservadoras de datos reales. Se retira `synthetic_available_at`.

**Alternativas.** Mantener valores en español (renombrar después sale caro).

**Consecuencias.** Hay que decidirlo antes de crear los contratos de datos. `status` de la tabla de predicciones pasa a `prediction_status`.
