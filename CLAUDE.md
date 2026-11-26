# StockPredictor: instrucciones permanentes

## 1. Objetivo
Pipeline de punta a punta que predice el **retorno absoluto de acciones individuales a N días** (N variable; horizontes activos 90 y 365, con 1500 como estadística descriptiva, ADR 0030). El modelo de selección es transversal y el retorno absoluto se compone con un componente de mercado aparte (ADR 0029). Etapas: extracción de datos → transformación y features → diseño de entrenamiento y validación → dataset → entrenamiento y test → inferencia (reutilizando módulos) → reentrenamiento y mejora continua.
Es investigación cuantitativa. Ningún resultado se presenta como recomendación de inversión.

**Fases:** F1 IBEX 35 → F2 + Nasdaq-100 → F3 mercados adicionales, de uno en uno, con ficha de mercado y datos verificables (ADR 0011: la accesibilidad desde España no es filtro). El código es multi-mercado desde F1 (calendarios, divisas, zonas horarias), aunque F1 use un solo mercado. La fase activa se fija en `configs/universe.yaml`. **Orden de trabajo (ADR 0027):** P1-0 (N_eff y MDE solo con precios) → go/no-go 1 → corte vertical con el plan B (IBEX, precios, técnicas, h90, Ridge, baselines transversales) → go/no-go 2 → fundamentales de CNMV como bloque. Solo se construye P7a. F2 es ampliación de datos y validación técnica del pipeline, no evidencia independiente (comparte ciclo con F1).

**Fuentes:** solo gratuitas (APIs gratuitas y scraping), sin claves de pago ni evasión de controles anti-bot. Uso propio: no se exige respetar `robots.txt` (ADR 0010). Se mantienen el límite de tasa y la parada ante respuestas anómalas (para no ser bloqueado), la caché en `data/raw` y no volver a pedir lo ya descargado. Cada descarga es una instantánea con manifiesto.

## 2. Reglas innegociables
1. **Anti look-ahead.** Todo dato periódico o macro se une con `merge_asof` por `available_at` (fecha real de disponibilidad pública), nunca por `period_end`. Para fundamentales, fecha de aceptación del filing. Si se publica tras el cierre, vale desde la sesión siguiente. Si falta la fecha real: `available_at = period_end + retraso conservador` y flag `available_at_estimated`. En datos de prueba la fecha inventada lleva `available_at_source = 'invented_test'` e `is_test_data` (ADR 0017).
2. **Point-in-time.** Se usa la **versión conocida en cada fecha**: una reexpresión entra solo desde su `available_at`; la primera versión se conserva como diagnóstico (`first_release_value`) (ADR 0009). Prohibido usar cifras reexpresadas o macro revisada con fecha anterior a su publicación. Si el proveedor solo da la última, anotarlo en `docs/limitaciones.md`.
3. **Universo point-in-time.** El universo en cada fecha es la composición del índice en esa fecha, no la actual: incluye empresas que después salieron del índice. Usar solo los constituyentes actuales introduce sesgo de supervivencia. Sector, bolsa e índice, vigentes en cada fecha. Si la composición histórica es incompleta, anotarlo en `docs/limitaciones.md`; mientras quede sesgo, **todo resultado se etiqueta "con sesgo de supervivencia"**.
4. **Precios.** `Adjusted Close` solo para retornos y señales técnicas. Market cap, P/E, P/B, P/S y dividend yield usan `Close` sin ajustar (`close_raw`) × acciones vigentes en esa fecha (o EPS ajustado de forma coherente). Mezclar `Adjusted Close` con acciones o EPS de otra fecha da valoraciones falsas. Las valoraciones de un mercado sin `Close` real verificado quedan **apagadas** hasta tener 10 cierres reales verificados (ADR 0013).
5. **Timing y target.** Features con información hasta el cierre de `t`. Entrada al **cierre de `t+1`**. Con `price_for_returns` (`Adjusted Close` o, si no existe, `Close` real con eventos confirmados; `target_price_kind`, ADR 0006), el retorno es `y = ln(P_{t+1+N} / P_{t+1})`. El **target de entrenamiento es transversal**: `y_cs = y − mediana por fecha del universo elegible` (ADR 0029). El retorno absoluto se reconstruye como `y_cs_pred + componente de mercado`, con el componente = media histórica expansiva del retorno mediano a N días usando solo etiquetas maduras (`label_end_date ≤ t`). Se guardan `y`, `y_med` e `y_cs`. Macro, FX y retorno del índice no entran en el modelo transversal. N se mide en **días naturales** (ADR 0005); las ventanas de features, en sesiones. No cambiarlo sin registrar la decisión en `docs/decisiones/`.
6. **Validación.** Solo walk-forward con purga por fin de target (`max(label_end_date de train) < inicio del test − embargo`, embargo provisional de 5 sesiones; ADR 0008). Los targets solapan, por eso la purga cubre ≥ N días. Prohibido el k-fold aleatorio. Un **calendario de reserva global** (ADR 0021) excluye de todos los horizontes un bloque de fechas hasta abrir el test final. El test final (3 años) es **control de catástrofes, no confirmación**: se toca una vez por candidato, cada consulta se anota en `experiments/` y el estadístico se deflacta por Bonferroni sobre el número de hashes que lo han tocado. La confirmación real es hacia delante, con las predicciones archivadas.
7. **Ajuste solo con train.** Imputación, selección de features, hiperparámetros, umbrales y cualquier transformador con estado se estiman con datos de entrenamiento de cada fold. La normalización por defecto es por **rango transversal por fecha** (ADR 0024), válida porque solo usa la misma fecha y no tiene estado; la z robusta con winsorizing por fold es ablación. Excepción acotada (ADR 0020): las cantidades pre-registradas (retraso conservador, antigüedad máxima, cobertura de ventana, train mínimo, etc.) se calibran solo con datos anteriores al bloque reservado y nunca mirando métricas del modelo.
8. **Sin invenciones.** Nunca presentar métricas, precios, límites o licencias de proveedores sin haberlos ejecutado o verificado. Si algo no está comprobado, decirlo.

## 3. Decisiones de modelado
- **Horizonte N:** parámetro en `configs/horizons.yaml` (activos: 90 y 365). Un modelo por horizonte y universo. Nada fija N a mano. El código es paramétrico en N, así que 1500 es reactivable.
- **Target:** regresión sobre el log-retorno transversal `y_cs` (regla 5, ADR 0029); la predicción absoluta se compone con el componente de mercado, que se evalúa aparte (RMSE frente a la media expansiva, sin pretensión de poder predictivo). Clasificación (p. ej. P(retorno>0)) solo como derivada posterior. El exceso sobre índice se calcula como diagnóstico. Muestreo de fechas semanal en h90 y mensual en h365 (ADR 0026).
- **Modelos:** baseline Ridge/Lasso; principal LightGBM (XGBoost/CatBoost como alternativas). LSTM/TFT solo con justificación y si lo anterior no basta.
- **Métricas:** estadísticas (RMSE/MAE; AUC/log-loss si clasifica) y financieras. La métrica primaria es el RankIC medio por fecha. Backtest con terciles o cartera ponderada por rango, solo largos y con tramos mensuales. Las financieras incluyen costes de transacción y filtro de liquidez, o no se reportan como definitivas: ITF español de 0,2 % desde 2021-01-16, costes de cada época más un escenario con los de hoy (ADR 0028), siempre etiquetados "supuesto". Contraste principal con submuestras no solapadas y permutación real (ADR 0022).
- **Comparaciones obligatorias (ADR 0023):** baselines transversales (momentum 12-1, reversión a 1 mes, baja volatilidad 60; value y tamaño si hay datos) para RankIC y terciles; baselines de serie temporal (media histórica expansiva, equiponderada, índice de precio) para RMSE, R² y retorno absoluto.
- **Horizontes largos:** para N≥365, reportar siempre el número efectivo de observaciones independientes. No afirmar poder predictivo a N=1500 sin ese dato. **Etiqueta de resultado por MDE (ADR 0019):** efecto de interés = RankIC medio 0,05; "señal detectada", "sin señal con potencia suficiente" (MDE ≤ 0,05) o "no concluyente" (MDE > 0,05, que no justifica parar ni reformular). **Regla de viabilidad (ADR 0007):** se cuentan las ventanas disjuntas de longitud N fuera de muestra evaluables (tras train mínimo y purga): ≥10 viable, 4 a 9 exploratorio, <4 no evaluable con rigor. Umbrales provisionales; no se tocan tras ver métricas. Aplica a los horizontes activos y a cualquiera que se reactive. El retorno absoluto a largo plazo lo domina el ciclo de mercado: vigilar que el modelo no aprenda solo el régimen.
- **Producción (solo P7a por ahora):** un modelo nuevo solo sustituye al vigente (champion/challenger) si lo supera en walk-forward reciente sin empeorar el riesgo. Promoción asistida (propone el sistema, aprueba Enrique); "no promover" es el valor por defecto. Detalle en `docs/mlops.md`.
- **Divisa:** el retorno se calcula en moneda local; el EUR es solo diagnóstico con FX point-in-time (ADR 0012).

## 4. Convenciones de ingeniería
- **Stack:** Python con versión fijada, lockfile, Parquet + DuckDB, polars como DataFrame único, scikit-learn, LightGBM. pandas no es dependencia base: solo extra opcional (`pyproject.toml`) si LightGBM o scikit-learn lo exigen, y únicamente en el borde del modelado, nunca en `transform/` ni `features/`.
- **Capas de datos:** `raw` (inmutable, con proveedor y fecha de descarga) → `interim` (limpio, tipado) → `features` → `datasets` versionados. Nunca editar `raw` a mano.
- **Un solo código para entrenar e inferir.** `transform` produce solo el panel alineado; los transformadores con `fit` (imputación para modelos lineales y, en la ablación, winsorizing y z robusta) se ajustan por fold con el train y viajan con el modelo; la normalización por defecto es por rango, sin estado (ADR 0016 y 0024). `src/stockpredictor/transform/` (alineación point-in-time, TTM, nulos, winsorizing, normalización) y `src/stockpredictor/features/` (ratios y técnicos) los reutiliza la inferencia. Prohibido duplicar transformaciones.
- **`transform/` aislado.** Toda la lógica anti look-ahead (`merge_asof` por `available_at`, ffill por empresa, TTM) vive solo en `transform/`; `features/` no une tablas por fecha. Winsorizing, escalado e imputación son transformadores con `fit` (solo train) y `transform`.
- **Contratos de datos:** cada tabla tiene esquema (columnas, tipos, unidades, divisa) validado al leer y escribir.
- **Nulos:** distinguir "no aplica", "no reportado" y "error de extracción". Política por variable en `configs/features.yaml`. Los árboles aceptan NaN; los modelos lineales necesitan imputación ajustada solo con train.
- **Divisiones y negativos:** ratios con denominador ≤ 0 (P/E con EPS negativo, ROE con equity negativo) devuelven NaN más un indicador, nunca inf.
- **Magnitudes monetarias:** no entran crudas. Escalar por activos, market cap o ventas (también Working Capital y FCF).
- **Entidades financieras:** bancos y aseguradoras no tienen EBITDA ni deuda comparables. Tratarlos con features propias o excluir esas métricas, y documentarlo.
- **Sectores pequeños:** si un sector tiene pocas empresas en una fecha, el z-score por sector degenera. Definir un mínimo y un fallback (agrupar subsectores o usar el mercado completo).
- **ROIC:** tasa de impuestos efectiva TTM acotada a [0%, 35%], con fallback a la tasa legal del país. Pendiente de verificar que la taxonomía de CNMV trae impuesto y beneficio antes de impuestos, y de citar las tasas legales con fuente.
- **Reproducibilidad:** semillas fijas, config en YAML, cada run guarda hash de datos, commit, config y métricas.
- **Tests:** unitarios para cada fórmula y tests anti-fuga en `tests/leakage/` (cambiar un dato futuro no debe alterar features pasadas). Un cambio en features o alineación no se da por bueno sin pasarlos.
- **Ejecuciones largas:** cada etapa se lanza con un subcomando de la CLI (`stockpredictor <etapa>`), vía única; `scripts/` solo contiene envoltorios finos (ADR 0015). Entrenamientos y descargas masivas con registro de progreso, nunca dentro de notebooks.
- **Idioma de identificadores:** código, columnas y valores en inglés; glosario en `docs/convenciones.md` (ADR 0017).
- **Pandas:** prohibido por lint fuera de `training/` y `evaluation/`; el código con pandas para calendarios y referencia de tests vive en `tools/calendars/` y en el grupo `dev` (ADR 0015).

## 5. Carpeta temporal
`tmp/` guarda descargas intermedias, pruebas y cosas para borrar. Está en `.gitignore`, no es fuente de verdad y puede vaciarse en cualquier momento. Lo que deba conservarse va a `data/raw` (con proveedor y fecha) o se convierte en código/documentación. Nada del pipeline puede depender de `tmp/`.

## 6. Reentrenamiento y mejora continua
- Calendario y disparadores (drift de features, RankIC rodante) definidos en `docs/mlops.md`.
- Cada modelo se registra en `models/{universe_id}/h{N}/v{versión}/` con `metadata.json` (features, fechas de entrenamiento, dataset, config, métricas y estado de los transformadores); el champion vigente por universo y horizonte se indica en `models/{universe_id}/h{N}/CHAMPION`. Ver `models/README.md`. Cada predicción guarda versión del modelo y fecha de datos (`data_as_of`).
- Las predicciones reales se archivan para evaluarlas después (paper trading).

## 7. Estructura del repositorio
`configs/` parámetros · `data/` datos (fuera de git; incluye `data/reference/` con composición histórica de índices) · `src/stockpredictor/{extraction,interim,quality,universe,transform,features,dataset,training,evaluation,registry,inference,monitoring}` · `models/` registro por horizonte y versión · `experiments/` runs de entrenamiento y evaluación, accesos al test y promociones · `runs/` resúmenes de ejecución de las etapas (fuera de git, purgable) · `notebooks/` exploración · `tests/{unit,leakage,integration}` · `scripts/` envoltorios finos · `tools/calendars/` generación de calendarios (con pandas) · `docs/` convenciones, limitaciones, decisiones · `tmp/` temporal. Detalle en `docs/estructura_proyecto.md`.

## 7b. Flujo de ramas
`main` estable, `develop` de integración y ramas cortas por tarea (`feat/`, `fix/`, `docs/`) que van por PR a `develop`. De `develop` se pasa a `main` por PR solo si no hay fallos, y solo cuando Enrique lo pide. Detalle en `CONTRIBUTING.md` y ADR 0031.

## 8. Cómo trabajar con Enrique
- Responder en español, empezando por "Enrique". Conciso, sin explicar lo básico.
- Cuestionar el planteamiento cuando haya fallos. Sin halagos.
- Antes de afirmar datos de proveedores, límites, licencias o regulación: buscar en la web y citar. La memoria queda desactualizada.
- Si algo es ambiguo, preguntar. Ante un trade-off, dar opciones con evidencia y que decida Enrique. No elegir en silencio el camino fácil.
- Fórmulas de Excel (si se piden): en español, separador `;`.
- Registrar decisiones relevantes en `docs/decisiones/` (ADR corto: contexto, decisión, alternativas, consecuencias).

## 9. Decisiones abiertas
Cerradas: accesibilidad desde España (ADR 0011), divisa (ADR 0012), horizontes y target (ADR 0029 y 0030, por delegación).
1. Composición histórica del IBEX 35: hay un PDF oficial de BME con 137 revisiones (1991-2026); falta mapear códigos a empresa y los precios de las salidas siguen limitados (ver `docs/limitaciones.md`).
2. Tasa de impuestos del ROIC: encaminada, pendiente de verificar la taxonomía de CNMV.
3. Retraso conservador de `available_at`: se calibra con datos reales y se fija por ADR antes de entrenar.
4. Cantidades pre-registradas (ADR 0020): se firman antes de la primera ejecución real.
5. **Efecto de interés** (RankIC 0,05, fijado por delegación; revisable antes de ver el MDE de P1-0) y **presupuesto de horas** de los dos go/no-go: las fija Enrique en el primero.
6. Mercado Continuo (condicionado al MDE de P1-0), varias clases de acciones y retenciones sobre dividendos.
Lista completa en `docs/decisiones/pendientes.md`.
