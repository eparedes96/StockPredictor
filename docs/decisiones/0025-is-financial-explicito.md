# ADR 0025: `is_financial` explícito (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-7.

**Contexto.** Los `not_applicable` de bancos y aseguradoras actuaban como variable de sector implícita.

**Decisión.** Columna booleana `is_financial` declarada en el contrato de fundamentales. Los NaN `not_applicable` no hacen de indicador de sector.

**Alternativas.** Excluir las financieras del modelo con fundamentales y evaluarlas solo con precios.

**Consecuencias.** El modelo puede usar `is_financial` de forma explícita y auditable. La alternativa se reconsidera si la ablación muestra que contamina.
