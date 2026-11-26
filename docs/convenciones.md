# Convenciones
Manda `CLAUDE.md`; aquí el detalle. Cambios en lo que sigue, vía ADR (ver `docs/decisiones/README.md`).

## Tiempo y target
- `available_at`: instante desde el que un dato es público. Fundamentales: fecha de publicación (CNMV) o de aceptación del filing (SEC). Si se publica con hora y es posterior al cierre real de la sesión (calendario Parquet, con cierres anticipados), vale desde la sesión siguiente. Sin hora (CNMV da solo fecha): sesión siguiente.
- Se guardan `available_date`, `available_at` (UTC, nulo si no hay hora) y `available_time_known`. `available_at_estimated` solo para estimaciones conservadoras de datos reales; `available_at_source = 'invented_test'` para fechas inventadas de prueba.
- Señal al cierre de `t`, entrada al cierre de `t+1`. Target: `ln(P_{t+1+N} / P_{t+1})` con `price_for_returns` (ADR 0006).
- **N en días naturales** (ADR 0005): salida = última sesión ≤ entrada + N días. **Ventanas de features en sesiones** del calendario de la cotización (retornos 1, 5, 21, 63, 126, 252; volatilidad 20 y 60; medias móviles 20, 50, 200; beta 252).
- Validación: purga por `label_end_date` más embargo de 5 sesiones, provisional (ADR 0008).
- Versión de un dato: la conocida en cada fecha (ADR 0009).

## Divisa y precios
- Retorno en moneda local; EUR como diagnóstico (ADR 0012). Precios con unidad menor (GBp) se normalizan a la unidad mayor y se guarda `price_unit_original`.
- Cada descarga de precios es una instantánea; el dataset referencia cuál usó.
- Valoraciones solo donde hay `Close` real verificado (ADR 0013).

## Etapas y orden (ADR 0016)
`extraction` → `raw` → `interim` (limpio, tipado, bitemporal, todas las versiones) → `transform` (panel alineado) → `features` (columnas brutas) → `dataset` (features crudas más target por N) → ajuste de transformadores por fold → entrenamiento. La inferencia recomputa el histórico completo y devuelve la fila pedida, con el mismo código.

## Glosario de columnas y valores (ADR 0017)
Inglés, minúsculas con guion bajo. Los planes antiguos conservan nombres anteriores; manda esta tabla.

| Concepto | Nombre |
|---|---|
| Close sin ajustar | `close_raw` |
| Adjusted close del proveedor | `adj_close` |
| Close ajustado solo por splits (Yahoo) | `close_split_adjusted` |
| Precio para el target | `price_for_returns`, con `price_for_returns_kind` ∈ {`adj_close`, `close_confirmed`}; el dataset copia `target_price_kind` |
| Calidad de precio | `price_quality` ∈ {`raw_verified`, `split_only`, `adj_only`, `close_only`} |
| Cobertura de precios | `no_prices` (miembros que salieron del índice sin precios) |
| Eventos derivados | `declared`, `undeclared`, `dividend`, `unclassified` |
| Estado de archivo | `current`, `test`, `archived` |
| Composición de índices | `index_membership` (empresa, índice, intervalo, fechas de anuncio y efectiva); tabla puente `universe_membership` |
| Identificadores | `company_id` (fundamentales), `security_id` (cotización; una primaria por empresa), `universe_id`, `market_id` |
| Estado de nulo | `not_applicable`, `not_reported`, `extraction_error`; razones en `quality_flag`. Precedencia en derivadas: `not_applicable` > `extraction_error` > `not_reported` |
| Datos de prueba | `is_test_data` |
| Estado de la predicción | `prediction_status` (no confundir con el estado de nulo) |
| Metadato opcional | `accessible_from_spain` (sin efecto) |
| Versión de esquema | `schema_version` en cada tabla |
| Otros | `shares_low_quality`, `capital_event_since_report`, `currency_mismatch`, `insufficient_history`, `avg_case`, `first_release_value`, `not_point_in_time`, `vintage_known` |

## Nulos y ratios
Ratios con denominador ≤ 0 devuelven NaN más indicador, nunca inf. Entidades financieras: las métricas que no aplican (EBITDA, deuda comparable) son `not_applicable`. Las magnitudes monetarias se escalan por activos, ventas o market cap. Normalización: z-score robusto (mediana y MAD) tras winsorizing [1, 99]; `n_min` provisional de 10 por grupo.
