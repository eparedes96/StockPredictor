# StockPredictor: instrucciones permanentes

## 1. Objetivo
Pipeline de punta a punta que predice el **retorno absoluto de acciones individuales a N días** (N variable: 90, 365, 1500...). Etapas: extracción de datos → transformación y features → diseño de entrenamiento y validación → dataset → entrenamiento y test → inferencia (reutilizando módulos) → reentrenamiento y mejora continua.
Es investigación cuantitativa. Ningún resultado se presenta como recomendación de inversión.

**Fases:** F1 IBEX 35 → F2 + Nasdaq-100 → F3 mercados adicionales, de uno en uno, con ficha de mercado y datos verificables (ADR 0011: la accesibilidad desde España no es filtro). El código es multi-mercado desde F1 (calendarios, divisas, zonas horarias), aunque F1 use un solo mercado. La fase activa se fija en `configs/universe.yaml`.

**Fuentes:** solo gratuitas (APIs gratuitas y scraping), sin claves de pago ni evasión de controles anti-bot. Uso propio: no se exige respetar `robots.txt` (ADR 0010). Se mantienen el límite de tasa y la parada ante respuestas anómalas (para no ser bloqueado), la caché en `data/raw` y no volver a pedir lo ya descargado. Cada descarga es una instantánea con manifiesto.

## 2. Reglas innegociables
1. **Anti look-ahead.** Todo dato periódico o macro se une con `merge_asof` por `available_at` (fecha real de disponibilidad pública), nunca por `period_end`. Para fundamentales, fecha de aceptación del filing. Si se publica tras el cierre, vale desde la sesión siguiente. Si falta la fecha real: `available_at = period_end + retraso conservador` y flag `available_at_estimated`. En datos de prueba la fecha inventada lleva `available_at_source = 'invented_test'` e `is_test_data` (ADR 0017).
2. **Point-in-time.** Se usa la **versión conocida en cada fecha**: una reexpresión entra solo desde su `available_at`; la primera versión se conserva como diagnóstico (`first_release_value`) (ADR 0009). Prohibido usar cifras reexpresadas o macro revisada con fecha anterior a su publicación. Si el proveedor solo da la última, anotarlo en `docs/limitaciones.md`.
3. **Universo point-in-time.** El universo en cada fecha es la composición del índice en esa fecha, no la actual: incluye empresas que después salieron del índice. Usar solo los constituyentes actuales introduce sesgo de supervivencia. Sector, bolsa e índice, vigentes en cada fecha. Si la composición histórica es incompleta, anotarlo en `docs/limitaciones.md`; mientras quede sesgo, **todo resultado se etiqueta "con sesgo de supervivencia"**.
4. **Precios.** `Adjusted Close` solo para retornos y señales técnicas. Market cap, P/E, P/B, P/S y dividend yield usan `Close` sin ajustar (`close_raw`) × acciones vigentes en esa fecha (o EPS ajustado de forma coherente). Mezclar `Adjusted Close` con acciones o EPS de otra fecha da valoraciones falsas. Las valoraciones de un mercado sin `Close` real verificado quedan **apagadas** hasta tener 10 cierres reales verificados (ADR 0013).
5. **Timing.** Features con información hasta el cierre de `t`. Entrada al **cierre de `t+1`**. El target es `ln(P_{t+1+N} / P_{t+1})` con `price_for_returns`: `Adjusted Close` o, si no existe, `Close` real con eventos confirmados (`target_price_kind`, ADR 0006). N se mide en **días naturales** (ADR 0005); las ventanas de features, en sesiones. No cambiarlo sin registrar la decisión en `docs/decisiones/`.
6. **Validación.** Solo walk-forward con purga por fin de target (`max(label_end_date de train) < inicio del test − embargo`, embargo provisional de 5 sesiones; ADR 0008). Los targets solapan, por eso la purga cubre ≥ N días. Prohibido el k-fold aleatorio. El test final se toca una vez por candidato y cada consulta se anota en `experiments/`.
7. **Ajuste solo con train.** Winsorizing, escalado, imputación, selección de features, hiperparámetros y umbrales se estiman con datos de entrenamiento de cada fold. La normalización cross-sectional por sector y fecha es válida porque solo usa la misma fecha. Excepción acotada (ADR 0014): los parámetros estructurales (retraso conservador, antigüedad máxima, cobertura de ventana, train mínimo) se calibran solo con datos anteriores al bloque de test final y nunca mirando métricas del modelo.
8. **Sin invenciones.** Nunca presentar métricas, precios, límites o licencias de proveedores sin haberlos ejecutado o verificado. Si algo no está comprobado, decirlo.

## 3. Decisiones de modelado
- **Horizonte N:** parámetro en `configs/horizons.yaml`. Un modelo por horizonte. Nada fija N a mano.
- **Target:** regresión sobre log-retorno absoluto. Clasificación (p. ej. P(retorno>0)) solo como derivada posterior. El exceso sobre índice se calcula como diagnóstico, no como objetivo.
- **Modelos:** baseline Ridge/Lasso; principal LightGBM (XGBoost/CatBoost como alternativas). LSTM/TFT solo con justificación y si lo anterior no basta.
- **Métricas:** estadísticas (RMSE/MAE; AUC/log-loss si clasifica) y financieras (RankIC por fecha, Sharpe, máximo drawdown). Las financieras incluyen costes de transacción y filtro de liquidez, o no se reportan como definitivas.
- **Comparaciones obligatorias:** contra retorno medio histórico, momentum simple y el índice.
- **Horizontes largos:** para N≥365, reportar siempre el número efectivo de observaciones independientes. No afirmar poder predictivo a N=1500 sin ese dato. **Regla de viabilidad (ADR 0007):** se cuentan las ventanas disjuntas de longitud N fuera de muestra evaluables (tras train mínimo y purga): ≥10 viable, 4 a 9 exploratorio, <4 no evaluable con rigor. Umbrales provisionales; no se tocan tras ver métricas. Los tres horizontes se entrenan igualmente, etiquetados. El retorno absoluto a largo plazo lo domina el ciclo de mercado: vigilar que el modelo no aprenda solo el régimen.
- **Producción:** un modelo nuevo solo sustituye al vigente (champion/challenger) si lo supera en walk-forward reciente sin empeorar el riesgo. Promoción asistida (propone el sistema, aprueba Enrique); "no promover" es el valor por defecto. Detalle en `docs/mlops.md`.
- **Divisa:** el retorno se calcula en moneda local; el EUR es solo diagnóstico con FX point-in-time (ADR 0012).

## 4. Convenciones de ingeniería
- **Stack:** Python con versión fijada, lockfile, Parquet + DuckDB, polars como DataFrame único, scikit-learn, LightGBM. pandas no es dependencia base: solo extra opcional (`pyproject.toml`) si LightGBM o scikit-learn lo exigen, y únicamente en el borde del modelado, nunca en `transform/` ni `features/`.
- **Capas de datos:** `raw` (inmutable, con proveedor y fecha de descarga) → `interim` (limpio, tipado) → `features` → `datasets` versionados. Nunca editar `raw` a mano.
- **Un solo código para entrenar e inferir.** `transform` produce solo el panel alineado; los transformadores con `fit` (winsorizing, normalización, imputación) se ajustan por fold con el train y viajan con el modelo (ADR 0016). `src/stockpredictor/transform/` (alineación point-in-time, TTM, nulos, winsorizing, normalización) y `src/stockpredictor/features/` (ratios y técnicos) los reutiliza la inferencia. Prohibido duplicar transformaciones.
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

## 8. Cómo trabajar con Enrique
- Responder en español, empezando por "Enrique". Conciso, sin explicar lo básico.
- Cuestionar el planteamiento cuando haya fallos. Sin halagos.
- Antes de afirmar datos de proveedores, límites, licencias o regulación: buscar en la web y citar. La memoria queda desactualizada.
- Si algo es ambiguo, preguntar. Ante un trade-off, dar opciones con evidencia y que decida Enrique. No elegir en silencio el camino fácil.
- Fórmulas de Excel (si se piden): en español, separador `;`.
- Registrar decisiones relevantes en `docs/decisiones/` (ADR corto: contexto, decisión, alternativas, consecuencias).

## 9. Decisiones abiertas
Cerradas: accesibilidad desde España (no es filtro, ADR 0011) y divisa (ADR 0012).
1. Composición histórica del IBEX 35: hay un PDF oficial de BME con 137 revisiones (1991-2026); falta mapear códigos a empresa y los precios de las salidas siguen limitados (ver `docs/limitaciones.md`).
2. Tasa de impuestos del ROIC: encaminada, pendiente de verificar la taxonomía de CNMV.
3. Retraso conservador de `available_at`: se calibra con datos reales y se fija por ADR antes de entrenar.
4. Umbrales pre-registrados (calidad, cobertura, train mínimo, test final): se fijan antes de la primera ejecución real.
Lista completa en `docs/decisiones/pendientes.md`.
