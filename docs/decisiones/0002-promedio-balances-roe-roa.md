# ADR 0002: Promedio de balance para ROE, ROA y Asset Turnover (2026-11-25)
**Estado.** Revisable. Propuesto por el coordinador de la sesión; Enrique no la ha confirmado.

**Contexto.** `plan_datos.md` define ROE, ROA y Asset Turnover con numerador TTM y denominador "(promedio)" sin precisar el promedio.

**Decisión.** El denominador es la media de los 5 balances trimestrales: el de inicio de la ventana TTM y los 4 cierres trimestrales. Es coherente con un numerador de 4 trimestres. Si faltan balances, se usa la media del balance de inicio y del de fin. Cada fila registra cuál de los dos casos se aplicó. Todos los balances se alinean por `available_at` (regla 1).

**Alternativas.** Solo balance final (sesgo si cambia mucho el patrimonio o los activos en el año); media de inicio y fin siempre (más simple, menos robusta a estacionalidad).

**Consecuencias.** Hace falta tener 5 balances por empresa para el caso principal, lo que recorta el historial útil inicial. Con equity ≤ 0 se aplica la regla de ratios (NaN más indicador). Se revisa si la cobertura de P1 muestra muchas empresas con balances faltantes.
