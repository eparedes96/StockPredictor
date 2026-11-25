# StockPredictor: instrucciones permanentes

## 1. Objetivo
Pipeline de punta a punta que predice el **retorno absoluto de acciones individuales a N días** (N variable: 90, 365, 1500...). Etapas: extracción de datos → transformación y features → diseño de entrenamiento y validación → dataset → entrenamiento y test → inferencia (reutilizando módulos) → reentrenamiento y mejora continua.
Es investigación cuantitativa. Ningún resultado se presenta como recomendación de inversión.

**Fases:** F1 IBEX 35 → F2 + Nasdaq-100 → F3 todos los mercados con acciones individuales accesibles desde España. El código es multi-mercado desde F1 (calendarios, divisas, zonas horarias), aunque F1 use un solo mercado. La fase activa se fija en `configs/universe.yaml`.

**Fuentes:** solo gratuitas (APIs gratuitas y scraping). Reglas de scraping: respetar términos de uso y `robots.txt`, limitar la tasa, cachear todo en `data/raw` y no volver a pedir lo ya descargado.

## 2. Reglas innegociables
1. **Anti look-ahead.** Todo dato periódico o macro se une con `merge_asof` por `available_at` (fecha real de disponibilidad pública), nunca por `period_end`. Para fundamentales, fecha de aceptación del filing. Si se publica tras el cierre, vale desde la sesión siguiente. Si falta la fecha real: `available_at = period_end + retraso conservador` y flag `available_at_estimated`.
2. **Point-in-time.** Prohibido usar cifras reexpresadas o macro revisada si existe versión original. Si el proveedor solo da la última, anotarlo en `docs/limitaciones.md`.
3. **Universo point-in-time.** El universo en cada fecha es la composición del índice en esa fecha, no la actual: incluye empresas que después salieron del índice. Usar solo los constituyentes actuales introduce sesgo de supervivencia. Sector, bolsa e índice, vigentes en cada fecha. Si la composición histórica es incompleta, anotarlo en `docs/limitaciones.md`; mientras quede sesgo, **todo resultado se etiqueta "con sesgo de supervivencia"**.
4. **Precios.** `Adjusted Close` solo para retornos y señales técnicas. Market cap, P/E, P/B, P/S y dividend yield usan `Close` sin ajustar × acciones vigentes en esa fecha (o EPS ajustado de forma coherente). Mezclar `Adjusted Close` con acciones o EPS de otra fecha da valoraciones falsas.
5. **Timing.** Features con información hasta el cierre de `t`. Entrada al **cierre de `t+1`**. El target es `ln(P_{t+1+N} / P_{t+1})` con `Adjusted Close`. No cambiarlo sin registrar la decisión en `docs/decisiones/`.
6. **Validación.** Solo walk-forward con embargo y purga ≥ N días (los targets solapan). Prohibido el k-fold aleatorio. El test final se toca una vez por candidato y cada consulta se anota en `experiments/`.
7. **Ajuste solo con train.** Winsorizing, escalado, imputación, selección de features, hiperparámetros y umbrales se estiman con datos de entrenamiento de cada fold. La normalización cross-sectional por sector y fecha es válida porque solo usa la misma fecha.
8. **Sin invenciones.** Nunca presentar métricas, precios, límites o licencias de proveedores sin haberlos ejecutado o verificado. Si algo no está comprobado, decirlo.

## 3. Decisiones de modelado
- **Horizonte N:** parámetro en `configs/horizons.yaml`. Un modelo por horizonte. Nada fija N a mano.
- **Target:** regresión sobre log-retorno absoluto. Clasificación (p. ej. P(retorno>0)) solo como derivada posterior. El exceso sobre índice se calcula como diagnóstico, no como objetivo.
- **Modelos:** baseline Ridge/Lasso; principal LightGBM (XGBoost/CatBoost como alternativas). LSTM/TFT solo con justificación y si lo anterior no basta.
- **Métricas:** estadísticas (RMSE/MAE; AUC/log-loss si clasifica) y financieras (RankIC por fecha, Sharpe, máximo drawdown). Las financieras incluyen costes de transacción y filtro de liquidez, o no se reportan como definitivas.
- **Comparaciones obligatorias:** contra retorno medio histórico, momentum simple y el índice.
- **Horizontes largos:** para N≥365, reportar siempre el número efectivo de observaciones independientes. No afirmar poder predictivo a N=1500 sin ese dato. El retorno absoluto a largo plazo lo domina el ciclo de mercado: vigilar que el modelo no aprenda solo el régimen.
- **Producción:** un modelo nuevo solo sustituye al vigente (champion/challenger) si lo supera en walk-forward reciente sin empeorar el riesgo.

## 4. Convenciones de ingeniería
- **Stack:** Python con versión fijada, lockfile, Parquet + DuckDB, polars como DataFrame único, scikit-learn, LightGBM. pandas no es dependencia base: solo extra opcional (`pyproject.toml`) si LightGBM o scikit-learn lo exigen, y únicamente en el borde del modelado, nunca en `transform/` ni `features/`.
- **Capas de datos:** `raw` (inmutable, con proveedor y fecha de descarga) → `interim` (limpio, tipado) → `features` → `datasets` versionados. Nunca editar `raw` a mano.
- **Un solo código para entrenar e inferir.** `src/stockpredictor/transform/` (alineación point-in-time, TTM, nulos, winsorizing, normalización) y `src/stockpredictor/features/` (ratios y técnicos) los reutiliza la inferencia. Prohibido duplicar transformaciones.
- **`transform/` aislado.** Toda la lógica anti look-ahead (`merge_asof` por `available_at`, ffill por empresa, TTM) vive solo en `transform/`; `features/` no une tablas por fecha. Winsorizing, escalado e imputación son transformadores con `fit` (solo train) y `transform`.
- **Contratos de datos:** cada tabla tiene esquema (columnas, tipos, unidades, divisa) validado al leer y escribir.
- **Nulos:** distinguir "no aplica", "no reportado" y "error de extracción". Política por variable en `configs/features.yaml`. Los árboles aceptan NaN; los modelos lineales necesitan imputación ajustada solo con train.
- **Divisiones y negativos:** ratios con denominador ≤ 0 (P/E con EPS negativo, ROE con equity negativo) devuelven NaN más un indicador, nunca inf.
- **Magnitudes monetarias:** no entran crudas. Escalar por activos, market cap o ventas (también Working Capital y FCF).
- **Entidades financieras:** bancos y aseguradoras no tienen EBITDA ni deuda comparables. Tratarlos con features propias o excluir esas métricas, y documentarlo.
- **Sectores pequeños:** si un sector tiene pocas empresas en una fecha, el z-score por sector degenera. Definir un mínimo y un fallback (agrupar subsectores o usar el mercado completo).
- **Divisa:** por decidir (moneda local o EUR). Hasta entonces, retornos en moneda local y FX solo como feature. Documentar en `docs/convenciones.md`.
- **ROIC:** tasa de impuestos acotada a [0%, 35%] o tasa legal del país (propuesta, sin confirmar).
- **Reproducibilidad:** semillas fijas, config en YAML, cada run guarda hash de datos, commit, config y métricas.
- **Tests:** unitarios para cada fórmula y tests anti-fuga en `tests/leakage/` (cambiar un dato futuro no debe alterar features pasadas). Un cambio en features o alineación no se da por bueno sin pasarlos.
- **Ejecuciones largas:** entrenamientos y descargas masivas se lanzan con `scripts/`, con registro de progreso, nunca dentro de notebooks.

## 5. Carpeta temporal
`tmp/` guarda descargas intermedias, pruebas y cosas para borrar. Está en `.gitignore`, no es fuente de verdad y puede vaciarse en cualquier momento. Lo que deba conservarse va a `data/raw` (con proveedor y fecha) o se convierte en código/documentación. Nada del pipeline puede depender de `tmp/`.

## 6. Reentrenamiento y mejora continua
- Calendario y disparadores (drift de features, RankIC rodante) definidos en `docs/mlops.md`.
- Cada modelo se registra en `models/h{N}/v{versión}/` con `metadata.json` (features, fechas de entrenamiento, dataset, config y métricas); el champion vigente por horizonte se indica en `models/h{N}/CHAMPION`. Ver `models/README.md`. Cada predicción guarda versión del modelo y fecha de datos.
- Las predicciones reales se archivan para evaluarlas después (paper trading).

## 7. Estructura del repositorio
`configs/` parámetros · `data/` datos (fuera de git; incluye `data/reference/` con composición histórica de índices) · `src/stockpredictor/{extraction,quality,universe,transform,features,dataset,training,evaluation,inference,monitoring}` · `models/` registro por horizonte y versión · `experiments/` runs · `notebooks/` exploración · `tests/{unit,leakage,integration}` · `scripts/` CLI · `docs/` convenciones, limitaciones, decisiones · `tmp/` temporal. Detalle en `docs/estructura_proyecto.md`.

## 8. Cómo trabajar con Enrique
- Responder en español, empezando por "Enrique". Conciso, sin explicar lo básico.
- Cuestionar el planteamiento cuando haya fallos. Sin halagos.
- Antes de afirmar datos de proveedores, límites, licencias o regulación: buscar en la web y citar. La memoria queda desactualizada.
- Si algo es ambiguo, preguntar. Ante un trade-off, dar opciones con evidencia y que decida Enrique. No elegir en silencio el camino fácil.
- Fórmulas de Excel (si se piden): en español, separador `;`.
- Registrar decisiones relevantes en `docs/decisiones/` (ADR corto: contexto, decisión, alternativas, consecuencias).

## 9. Decisiones abiertas
1. Qué significa "accesible desde España" (depende del bróker). Bloquea F3.
2. Retornos en moneda local o en EUR (F2/F3).
3. Tasa de impuestos para ROIC.
4. Fuente exacta de composición histórica del IBEX 35 (F1) y de precios de los miembros que salieron del índice.
5. Retraso conservador para `available_at` cuando falte la fecha real (calibrar con datos).
