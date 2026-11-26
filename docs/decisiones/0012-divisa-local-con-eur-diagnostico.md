# ADR 0012: Divisa del retorno, local con EUR de diagnóstico (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. Cierra la decisión abierta 9.2.

**Contexto.** F2 y F3 mezclan divisas. El target de un valor de EE. UU. en EUR absorbería la volatilidad EUR/USD, que puede dominar a horizontes cortos.

**Decisión.** `return_currency` parametrizado (`configs/target.yaml`): **moneda local** como objetivo principal y **EUR como diagnóstico**, calculado con FX point-in-time (tipos de referencia del BCE; hora oficial de publicación sin verificar). En F1 no cambia nada. Las valoraciones con divisa de informe distinta a la de precio son NaN con `currency_mismatch`, sin convertir. El filtro de liquidez y el valor negociado se calculan en moneda local por mercado.

**Alternativas.** EUR como objetivo principal (exige FX limpio desde el inicio); dos modelos, uno por divisa (duplica coste).

**Consecuencias.** La evaluación no convierte divisas. El diagnóstico en EUR lo produce la fase de mercados adicionales (P8a.2) y la plantilla de informe lleva una sección fija, "n/a" cuando no aplique.
