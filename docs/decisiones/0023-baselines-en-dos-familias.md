# ADR 0023: Baselines en dos familias (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-5.

**Contexto.** La media histórica, la cartera equiponderada y el índice dan la misma predicción a todos los nombres en cada fecha, así que su RankIC es indefinido.

**Decisión.** **Transversales** (para RankIC y terciles): momentum 12-1, reversión a 1 mes, baja volatilidad a 60 sesiones y, si hay datos, value y tamaño. **De serie temporal** (para RMSE, R² y retorno absoluto): media histórica expansiva, equiponderada e índice de precio. La media histórica expansiva alimenta también el componente de mercado (ADR 0029).

**Alternativas.** Una sola lista de baselines.

**Consecuencias.** "Supera a los baselines" se evalúa dentro de su familia. La plantilla de informe los separa.
