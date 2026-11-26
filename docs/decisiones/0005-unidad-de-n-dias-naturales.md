# ADR 0005: Unidad de N en días naturales (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. Antes ADR-P5-1.

**Contexto.** `horizons.yaml` fijaba `[90, 365, 1500]` sin unidad y CLAUDE.md decía "N días". La viabilidad de N=1500 cambia de unos 4,1 a unos 6 años según la unidad.

**Decisión.** N se mide en **días naturales**. Entrada: cierre de `t+1` de la cotización. Salida: última sesión ≤ fecha de entrada + N días, según el calendario Parquet de la cotización. Las ventanas de features siguen en sesiones.

**Alternativas.** N en sesiones por cotización (coherente con las features, pero peor para 1500 y distinto por mercado); ambas por parámetro.

**Consecuencias.** `horizons.yaml` documenta la unidad. P5a mide la sensibilidad a la otra unidad. El calendario por cotización se usa solo para localizar fechas.
