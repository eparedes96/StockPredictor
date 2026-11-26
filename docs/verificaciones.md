# Verificaciones técnicas pendientes
Una "semana de verificaciones" al inicio del desarrollo. Cada una acaba como **resuelta** o **descartada**, con la evidencia. Hoy ninguna está hecha.

| # | Verificación | Dónde se necesita | Estado |
|---|---|---|---|
| 1 | pandera.polars, calendarios y polars con `uv.lock` en Python 3.12 (las pruebas previas fueron con 3.13 y polars 2.2.0); pandera con tablas grandes, `Decimal` y `LazyFrame` | ADR 0003, contratos de P2 | pendiente |
| 2 | `join_asof` de polars con el caso real (P3 43a) | `transform/align` | pendiente |
| 3 | Varianza con solape; submuestras no solapadas, HAC con corrección de Harvey, Leybourne y Newbold (1997), bootstrap por bloques | ADR 0022 | pendiente |
| 4 | PSI frente a KS y sus umbrales | `monitoring/` | pendiente |
| 5 | Compatibilidad de polars con LightGBM y scikit-learn | `training/` | pendiente |
| 6 | Límite `start` de los calendarios | `tools/calendars/` | pendiente |
| 7 | Prueba de scrip con 2 o 3 empresas y test de regresión de `adj_close` entre instantáneas de Yahoo | P2 | pendiente |
| 8 | Regla del `Close` real de España con las empresas reales del universo y una agrupación conocida | ADR 0013 | pendiente |
| 9 | Acciones en circulación en España (BORME) en 3 a 5 empresas | P4 valoración | pendiente |
| 10 | Taxonomía de CNMV: impuesto sobre beneficios y beneficio antes de impuestos; tasas legales | ROIC | pendiente |
| 11 | Hora oficial de publicación del FX del BCE | P8 | pendiente |
| 12 | ITF: tasas y fechas con fuente oficial | ADR 0028 | pendiente |
| 13 | Cobertura de Bolsamanía fuera del IBEX y composición histórica del Mercado Continuo | ADR 0027 | pendiente |
| 14 | Serie del IBEX 35 con dividendos: descarga gratuita | P6 benchmark | pendiente |
