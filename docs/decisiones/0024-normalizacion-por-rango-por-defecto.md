# ADR 0024: Normalización por rango transversal por defecto (matiza la regla 7) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-6.

**Contexto.** Con unos 28 a 35 nombres por fecha, el winsorizing y la z robusta con estado por fold añaden complejidad y estimaciones ruidosas.

**Decisión.** Rango por fecha en [−0,5, 0,5], sin winsorizing ni estado ajustado por fold por defecto. La z robusta tras winsorizing [1, 99] queda como **ablación**. La regla 7 se mantiene para todo lo que sí se ajuste con datos (imputación para modelos lineales, hiperparámetros, selección de features, umbrales). Sustituye en lo que toca al ADR 0016: los transformadores con `fit` siguen existiendo, pero ya no son la normalización por defecto.

**Alternativas.** Mantener z robusta con winsorizing por fold.

**Consecuencias.** Menos estado que viaja con el modelo; se pierde la magnitud de las diferencias, y la ablación lo mide. `configs/features.yaml` pone `normalization: rank`.
