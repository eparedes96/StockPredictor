# ADR 0026: Muestreo de fechas de decisión (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-8.

**Contexto.** Las fechas diarias solapan casi por completo a 90 y 365 días y no mejoran el número de observaciones independientes.

**Decisión.** Entrenamiento y evaluación con fechas **semanales para h90** y **mensuales para h365**. Si se mantiene el diario, con pesos por unicidad.

**Alternativas.** Diario sin pesos.

**Consecuencias.** No mejora T_eff; reduce coste y rotación artificial. El panel de `transform` sigue siendo diario completo.
