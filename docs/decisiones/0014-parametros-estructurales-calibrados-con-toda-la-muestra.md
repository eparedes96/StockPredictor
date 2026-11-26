# ADR 0014: Parámetros estructurales calibrados con toda la muestra (excepción acotada a la regla 7) (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique.

**Contexto.** La regla 7 exige estimar umbrales con el train de cada fold. Varios parámetros solo se pueden medir con la distribución real: retraso conservador (p95 global), `max_staleness_days`, cobertura mínima de ventana, train mínimo, umbrales de calidad y cobertura. Cada plan lo declaraba, pero no había un ADR que acotara el riesgo.

**Decisión.** Estos parámetros son **estructurales** (desfases, tolerancias, cobertura), no predictores. Se calibran **solo con datos anteriores al bloque de test final** y, si afectan a features, dentro del train de cada fold cuando sea factible. Se fijan por ADR antes de entrenar y **nunca se ajustan mirando métricas del modelo**. Lista de parámetros: retraso conservador, `max_staleness_days`, percentil de las filas estimadas, `window_min_coverage`, `n_min`, `min_names_per_date`, umbrales de calidad y de cobertura de índice, train mínimo, test final y embargo.

**Alternativas.** Calibrar cada uno por fold (inviable para desfases globales); sin regla (opacidad).

**Consecuencias.** La regla 7 de CLAUDE.md incluye la excepción. Los umbrales provisionales de `configs/` llevan comentario "provisional" hasta que el ADR de pre-registro los fije. Cada cambio posterior necesita justificación escrita.
