# Plan Básico: Modelo Predictivo de Cotización

## 1. Objetivo y Entradas del Modelo

Desarrollar un modelo predictivo para estimar el **retorno futuro a** $N$ **días** (o el exceso de retorno respecto al índice de referencia) de una acción.

* **Entradas principales:** El modelo recibirá los **datos actuales y fundamentales vigentes de la empresa** junto con su **historial de cotización** (el detalle completo de variables brutas, calculadas y finales se adjuntará en un documento aparte).
* **Control de universo:** Usar la composición histórica del índice en cada fecha (incluidas empresas que después salieron del índice) para evitar sesgo de supervivencia.

## 2. Métodos de Ajuste Temporal

Para alinear frecuencias distintas (datos periódicos frente a cotización diaria) y evitar fugas de información (*look-ahead bias*):

* **Alineación `as-of` (`merge_asof`):** Vincular los datos periódicos y macroeconómicos con cada sesión bursátil utilizando estrictamente su **fecha real de publicación pública** (`filing_date <= date`), nunca la fecha de cierre del periodo.
* **Arrastre hacia adelante controlado (*Forward-Fill*):** Propagar los últimos datos vigentes sesión a sesión agrupando siempre por empresa hasta la siguiente publicación oficial.
* **Ajuste por eventos corporativos:** Emplear series históricas ajustadas por *splits* y dividendos para mantener la continuidad de la serie temporal.
* **Ventanas móviles (*Rolling Windows*) y TTM:** Utilizar acumulaciones de 12 meses móviles (*Trailing Twelve Months*) y ventanas deslizantes para métricas históricas y de tendencia.

## 3. Métodos de Normalización

Para garantizar la comparabilidad entre empresas de distinto tamaño, sector y momento histórico:

* **Normalización Cross-Sectional por Sector:** En cada fecha $t$, estandarizar las métricas clave dentro de su mismo sector mediante ***Z-Score*** ($\frac{x - \mu_{\text{sector}, t}}{\sigma_{\text{sector}, t}}$) o **Rank / Percentil** sectorial.
* **Normalización Temporal / Estacionariedad:** Trabajar con variaciones relativas (retornos porcentuales o logarítmicos) y ratios adimensionales en lugar de magnitudes monetarias absolutas.
* **Tratamiento de valores extremos y escalado:** Aplicar *Winsorizing* (recorte de percentiles extremos) para mitigar *outliers* contables y escalado estándar/robusto cuando lo requiera el algoritmo.

## 4. Métodos Recomendados para el Modelo

### Algoritmos
* **Baseline (Referencia):** Regresión lineal regularizada (*Ridge* / *Lasso*) o Regresión Logística (si se plantea como clasificación direccional).
* **Modelos Principales:** Algoritmos de *Gradient Boosting* sobre árboles de decisión (**LightGBM**, **XGBoost** o **CatBoost**), recomendados por su capacidad para manejar relaciones no lineales, variables categóricas (sector, país, bolsa) y valores nulos sin requerir escalado estricto.
* **Alternativa Secuencial (opcional):** Redes neuronales temporales (LSTM / Temporal Fusion Transformer) si se prioriza el modelado profundo de secuencias largas.

### Validación y Evaluación
* **Esquema de Validación:** **Walk-Forward Validation** (ventanas expansivas o deslizantes en el tiempo) incorporando un periodo de **embargo de $N$ días** entre entrenamiento y prueba para evitar solapamiento con el horizonte objetivo.
* **Métricas de Evaluación:** Combinar métricas estadísticas (RMSE, MAE o AUC/Log-Loss) con métricas financieras (*Information Coefficient* / RankIC, Sharpe Ratio y Maximum Drawdown).