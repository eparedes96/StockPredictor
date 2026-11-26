# Datos de referencia (tablas manuales versionadas)
Única carpeta de `data/` que entra en git, y solo `*.csv` y este README. Cada fila lleva **fuente** (`source`, `source_ref`, `source_date`) y `confidence`; lo que se haya revisado a mano, `reviewed`. Hoy están **vacías, solo con cabecera**.

**Cabeceras propuestas**: salen de lo que describen los planes (P1, P2, P5), no de datos reales; se ajustan al implementar los contratos (`quality/`). El nombre y los valores siguen el glosario de `docs/convenciones.md`.

| Archivo | Para qué | Plan |
|---|---|---|
| `bme_code_map.csv` | Mapeo de códigos BME a `company_id` y revisión de cambios de código (un cambio de código no es una salida) | P1 T1.1, P2 P2.12 |
| `index_membership/ibex35.csv` | Composición histórica: empresa, índice, intervalo, fechas de anuncio y efectiva. Un CSV por índice | P1, P2 8a, P8 |
| `exit_events.csv` | Salidas del índice: última fecha con precio, motivo (expropiación, liquidación, absorción...) y resolución | P2 46a, P5a.2 |
| `price_jump_review.csv` | Revisión manual de saltos candidatos a evento corporativo, empresa por empresa | P2 46a |
| `statutory_tax_rates.csv` | Tasas legales por país y año para el ROIC (con fuente citada) | P4 25a |
| `taxonomy_concept_map.csv` | Mapeo concepto → campo canónico por taxonomía y época (CNMV) | P2 24a |

**Antes de rellenar**: estimar las horas (137 revisiones de BME, cambios de código indistinguibles de salidas). Es trabajo manual aún no presupuestado.

`index_membership/` tiene un CSV por índice. Las tablas derivadas (`universe_membership`, calendarios Parquet) no viven aquí: se generan y quedan fuera de git.
