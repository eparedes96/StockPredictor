> **Histórico (2026-11-26).** Borrador inicial, superado en parte por la planificación posterior. Vigente: `CLAUDE.md`, `docs/convenciones.md`, `docs/limitaciones.md`, `docs/mlops.md` y `docs/decisiones/`. Ante un conflicto manda lo vigente.

# Plan de fases vigente (v3, 2026-11-26; ADR 0027, 0029 y 0030)

## Orden de trabajo
1. **P1-0, fase previa.** Con Yahoo `adjclose` del IBEX y la composición del PDF de BME, solo con precios: ventanas fuera de muestra evaluables, N_eff, error típico real del RankIC de los baselines transversales (momentum 12-1, reversión a 1 mes, baja volatilidad 60) y **MDE** por horizonte (h90 y h365), con contraste de permutación real. Entregable: informe en `docs/` con tablas por horizonte. **Go/no-go 1.**
2. **P1a.** Composición histórica, precios de toda la vida de la cotización, referencia y macro. Las tablas manuales (mapeo de códigos de BME, `exit_events`, revisión de saltos) van en CSV versionados con fuente por fila, con **estimación de horas antes de empezar**.
3. **Corte vertical con el plan B.** IBEX, precios, unas 8 técnicas, h90, Ridge, baselines transversales, walk-forward con purga, informe. Con P2 a P6 en su versión mínima. **Go/no-go 2.**
4. **P1b.** Fundamentales de CNMV como bloque encima (el plan A de 4b).
5. **P7a solo.** Inferencia, registro y archivo de predicciones, con el primer baseline archivado desde el principio. P7b, aplazado.
6. **F2** (Nasdaq-100): ampliación de datos y validación técnica del pipeline, no evidencia independiente. Espera al go/no-go tras P1-0 y tras el corte vertical.

## Reglas de go/no-go
Se disparan por hito, no por fecha; **Enrique fija las horas en el primero**. Si el MDE del IBEX a h90 es > 0,05 y el Mercado Continuo no lo baja a ≤ 0,05, el IBEX pasa a universo de validación técnica. Igual criterio a h365 con su MDE. El Mercado Continuo es una decisión condicionada al MDE de P1-0 (cobertura de Bolsamanía y composición histórica sin verificar).

## Horizontes
Activos: 90 y 365. 1500 es estadística descriptiva (ADR 0030); reactivable.

---
*Lo que sigue es el borrador inicial, conservado como historial. Donde contradiga lo anterior (horizontes `90, 365, 1500`, orden de P1 a P8, N=1500 como horizonte de entrenamiento), manda lo anterior.*

# Plan por fases (borrador 1: solo fases, sin detalle de tareas)

Fecha: 2026-11-25. Estado: propuesto, pendiente de aprobación de Enrique.

## Principios del plan
1. **Primero un corte vertical fino en F1, luego se ensancha.** Cada fase de desarrollo (P0 a P7) se cierra con IBEX 35 y un solo horizonte (365) funcionando de punta a punta antes de añadir Nasdaq-100 (F2) o más horizontes. Motivo: los errores de alineación temporal se descubren al ver el pipeline completo, y es más barato corregirlos con un mercado.
2. **Dos ejes.** Las fases de desarrollo (P0 a P7) son *qué se construye*. Las fases de universo (F1, F2, F3) son *sobre qué datos*. El código es multi-mercado desde P1, aunque F1 solo use uno.
3. **Ninguna fase cierra sin sus tests anti-fuga** (`tests/leakage/`) y sin actualizar `docs/limitaciones.md`.
4. Todo resultado de F1/F2 se etiqueta "con sesgo de supervivencia" mientras la composición histórica sea incompleta.

## Mapa resumido

| Fase | Nombre | Universo en que se cierra | Bloqueada por |
|---|---|---|---|
| P0 | Cimientos y decisiones | n/a | Decisión 4 (parcial) |
| P1 | Universo y extracción | F1 | Decisión 4 |
| P2 | Calidad y capa interim | F1 | P1 |
| P3 | Transformación point-in-time | F1 | Decisión 5 |
| P4 | Features | F1 | Decisión 3 (solo ROIC) |
| P5 | Dataset y validación | F1 | P4 |
| P6 | Entrenamiento y evaluación | F1, luego F2 | P5, decisión 2 para F2 |
| P7 | Inferencia y MLOps | F1, luego F2 | P6 |
| P8 | Expansión a F2 y F3 | F2, F3 | Decisiones 1 y 2 |

## P0. Cimientos y decisiones
- **Objetivo:** repositorio operativo y decisiones que no se pueden posponer tomadas.
- **Entregables:** repositorio en GitHub (lo crea Enrique), `pyproject.toml` con Python fijado y lockfile, CI mínima (lint + tests), `plan_datos.md` completo (Enrique debe repegar las tablas), ADRs de las decisiones abiertas que toquen a F1.
- **Criterio de salida:** `pytest` corre en limpio en CI; `plan_datos.md` lista cada variable con fuente candidata y fecha de disponibilidad.
- **Bloquea:** todo lo posterior, porque sin repositorio no hay PRs ni CI.

## P1. Universo y extracción (F1)
- **Objetivo:** datos brutos de IBEX 35 en `data/raw` con proveedor y fecha de descarga.
- **Entregables:** composición histórica del IBEX 35 en `data/reference/`; OHLCV (Close y Adjusted Close) de miembros actuales y pasados; fundamentales trimestrales con fecha de publicación; sector/bolsa/divisa; macro con fecha de publicación; caché y límites de tasa; informe de cobertura por fuente.
- **Criterio de salida:** informe de cobertura medido (no supuesto): % de miembros históricos con precios, % de trimestres con fecha real de publicación frente a estimada, y qué proveedores permiten uso y scraping según sus términos (verificados, con cita).
- **Riesgo principal:** la composición histórica y los precios de empresas que salieron del índice con fuentes gratuitas. Si la cobertura es baja, se mantiene el sesgo de supervivencia, se declara y se cuantifica. Este es el mayor riesgo del proyecto entero y conviene atacarlo primero.
- **Decisión que lo bloquea:** 4 (fuente de composición histórica).

## P2. Calidad y capa interim
- **Objetivo:** pasar de raw a datos limpios, tipados y con contrato.
- **Entregables:** esquemas validados al leer y escribir en cada tabla; tratamiento de splits, dividendos y precios erróneos; distinción de nulos ("no aplica", "no reportado", "error de extracción"); `docs/limitaciones.md` al día con lo que los proveedores no dan en point-in-time (cifras reexpresadas, macro revisada).
- **Criterio de salida:** informe de calidad reproducible; ninguna tabla interim sin esquema.

## P3. Transformación point-in-time
- **Objetivo:** el módulo `transform/` que toda la fase de features y la inferencia reutilizarán.
- **Entregables:** `merge_asof` por `available_at`, flag `available_at_estimated`, TTM, ffill por empresa, nulos, winsorizing, escalado y normalización por sector y fecha como transformadores con `fit`/`transform`, y fallback para sectores pequeños.
- **Criterio de salida:** tests de fuga en verde (cambiar un dato futuro no altera ninguna fila pasada); retraso conservador calibrado con datos.
- **Decisión que lo bloquea:** 5 (retraso conservador). Se calibra con la cobertura de P1.

## P4. Features
- **Objetivo:** ratios de rentabilidad, solvencia y valoración, más técnicos.
- **Entregables:** `features/` con fórmulas unitariamente testeadas, política de nulos por variable en `configs/features.yaml`, tratamiento propio de bancos y aseguradoras, ratios con denominador ≤ 0 devuelven NaN más indicador.
- **Criterio de salida:** tests unitarios por fórmula; valoración con Close sin ajustar × acciones vigentes (regla 4) verificada con tests.
- **Decisión que lo bloquea:** 3, solo para ROIC. El resto de features avanza sin ella.

## P5. Dataset y diseño de validación
- **Objetivo:** dataset versionado y esquema walk-forward que no filtre.
- **Entregables:** target `ln(P_{t+1+N}/P_{t+1})` por horizonte; folds con embargo y purga ≥ N; dataset en `data/datasets/` con hash; cálculo del **número efectivo de observaciones independientes** por horizonte.
- **Criterio de salida:** con IBEX 35 y N=1500 el número efectivo de observaciones independientes está calculado. **Si es demasiado bajo, N=1500 se descarta o se reformula antes de entrenar**, no después.
- **Nota:** el IBEX tiene 35 acciones muy correlacionadas con un mismo ciclo; el N efectivo a 1500 días será muy pequeño. Lo medimos, no lo asumimos.

## P6. Entrenamiento y evaluación
- **Objetivo:** primeros resultados honestos.
- **Entregables:** baselines (media histórica, momentum simple, índice), Ridge, luego LightGBM; métricas estadísticas y financieras (RankIC por fecha, Sharpe, drawdown con costes y filtro de liquidez); registro de runs en `experiments/`; test final tocado una vez por candidato.
- **Criterio de salida:** informe por horizonte con intervalos de incertidumbre, comparación con baselines y comprobación de que el modelo no aprende solo el régimen de mercado. Un resultado nulo es un resultado válido.
- **Orden:** horizonte 365 primero, luego 90, luego 1500 solo si P5 lo permite.

## P7. Inferencia y MLOps
- **Objetivo:** predecir con datos recientes reutilizando `transform/` y `features/`.
- **Entregables:** `scripts/` de extracción incremental e inferencia; registro `models/h{N}/v{ver}/` con `metadata.json` y `CHAMPION`; archivo de predicciones (paper trading) con versión de modelo y fecha de datos; `docs/mlops.md` con calendario de reentrenamiento y disparadores de drift; regla champion/challenger.
- **Criterio de salida:** una predicción reproducible de extremo a extremo; test de que entrenamiento e inferencia producen las mismas features para la misma fecha.

## P8. Expansión a F2 y F3
- **F2 (Nasdaq-100):** repetir P1 a P6 para el nuevo mercado reutilizando código; revisar calendarios, zonas horarias, divisa y composición histórica del índice. **Bloqueada por la decisión 2** (moneda local o EUR). Con dos mercados, el modelo puede ser conjunto o separado: se decide con evidencia en P6.
- **F3 (todos los mercados accesibles):** **bloqueada por la decisión 1** (qué es "accesible desde España", depende del bróker). Aquí sí se necesita filtro de liquidez estricto y revisar los términos de scraping de cada fuente.
- **Criterio de salida de cada una:** informe de cobertura y de sesgo de supervivencia propio del universo.

## Decisiones abiertas y en qué fase muerden

| # | Decisión | Fase afectada | ¿Bloquea? |
|---|---|---|---|
| 1 | "Accesible desde España" | F3 (P8) | Solo F3 |
| 2 | Moneda local o EUR | F2 | Solo F2 en adelante |
| 3 | Tasa fiscal ROIC | P4 | Solo esa feature |
| 4 | Fuente de composición histórica y precios de salidos | P1 | **Sí, es la primera** |
| 5 | Retraso conservador de `available_at` | P3 | Sí, se calibra con datos de P1 |

## Puntos que cuestionar
1. **N=1500 en IBEX 35 probablemente no tenga poder estadístico.** El plan lo mide en P5 antes de gastar tiempo entrenando.
2. **El riesgo de datos pesa más que el riesgo de modelo.** Con fuentes gratuitas, la fiabilidad de fundamentales point-in-time y de la composición histórica decide si el resultado vale algo. Por eso P1 y P2 llevan criterios de salida medibles.
3. **Sin repositorio no hay plan ejecutable.** P0 depende de que Enrique cree el repositorio en GitHub.

## Lo que no se ha verificado
Ninguna fuente, límite o licencia de proveedor está comprobada todavía; se hará en P1 con búsqueda web y cita.
