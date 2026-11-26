> **Histórico (2026-11-26).** Borrador inicial, superado en parte por la planificación posterior. Vigente: `CLAUDE.md`, `docs/convenciones.md`, `docs/limitaciones.md`, `docs/mlops.md` y `docs/decisiones/`. Ante un conflicto manda lo vigente.

# Plan de Datos: Modelo Predictivo de Cotización

> Transcrito tal cual del mensaje de Enrique del 2026-11-25. Las tres tablas están sin cambios. Las divergencias con `CLAUDE.md` se anotan al final; ante un conflicto, manda `CLAUDE.md`.

## 1. Datos a Extraer

| Dato a extraer | Tipo / Frecuencia | Fuentes de origen sugeridas |
| --- | --- | --- |
| Identificador de empresa (`ticker` / `company_id`), nombre y fecha (`date` / `filing_date` / `period_end`) | Clave / Diario o Trimestral | Proveedor de datos financieros (Financial Modeling Prep, EODHD, Polygon/Massive, Refinitiv/S&P), registros regulatorios (SEC EDGAR, CNMV) |
| País / región (sede fiscal) | Estático / Categórico | Proveedor de datos financieros, registros mercantiles / regulatorios |
| Bolsa de cotización (NYSE, Nasdaq, BME, etc.) | Estático / Categórico | Proveedor de datos financieros, fichas de mercados bursátiles |
| Sector y subsector (estándar GICS) | Estático / Categórico | Proveedor de datos financieros, taxonomía GICS (MSCI / S&P) |
| Divisa de cotización | Estático / Categórico | Proveedor de datos financieros, bolsas de valores |
| Precio de apertura (`Open`), máximo (`High`), mínimo (`Low`), cierre (`Close`) | Diario (mercado) | Proveedor de datos de mercado (Yahoo Finance, EODHD, Polygon/Massive, Alpha Vantage, Stooq) |
| Precio de cierre ajustado (`Adjusted Close` por *splits* y dividendos) | Diario (mercado) | Proveedor de datos de mercado (Yahoo Finance, EODHD, Polygon/Massive) |
| Volumen de negociación (`Volume`) | Diario (mercado) | Proveedor de datos de mercado (Yahoo Finance, EODHD, Polygon/Massive, Stooq) |
| Número de acciones en circulación (`Shares Outstanding`) | Trimestral / Diario | Proveedor de datos financieros, estados financieros (10-Q / 10-K / informes periódicos) |
| Revenue / Ingresos totales (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales (Financial Modeling Prep, EODHD, S&P/Refinitiv), informes financieros oficiales |
| Gross Profit / Beneficio bruto (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| EBITDA (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| EBIT / Beneficio operativo (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Net Income / Beneficio neto (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| EPS básico y EPS diluido (PyL) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Total Assets / Activo total (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Total Liabilities / Pasivo total (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Total Equity / Patrimonio neto (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Deuda a corto plazo y deuda a largo plazo (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Cash & equivalentes / Efectivo y equivalentes (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Activo corriente y pasivo corriente (Balance) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Gastos por intereses / *Interest Expense* (PyL / notas) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Operating Cash Flow / Flujo de caja operativo (Cash Flow) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| CapEx / Gasto de capital (Cash Flow) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Dividendos pagados (Cash Flow) | Trimestral (indexado por `filing_date`) | Proveedor de datos fundamentales, informes financieros oficiales |
| Tipos de interés de referencia (banco central / curva soberana) | Diario / Mensual | Bancos centrales (BCE, Reserva Federal), FRED, Eurostat, Banco de España |
| Inflación (IPC) | Mensual | Eurostat, INE, BLS, FRED, OCDE |
| PIB / Crecimiento económico | Trimestral | Eurostat, INE, BEA, FRED, Banco Mundial |
| Índice de referencia del mercado (S&P 500, IBEX 35, etc.) | Diario | Proveedor de datos de mercado (Yahoo Finance, Stooq, EODHD, índices oficiales) |
| Tipo de cambio (`FX`) si la divisa de cotización difiere de la base | Diario | BCE, FRED, proveedores de datos FX (EODHD, Alpha Vantage, Yahoo Finance) |

---

## 2. Datos a Calcular

| Dato a calcular | Fórmula / Regla de cálculo | Datos de entrada / brutos utilizados |
| --- | --- | --- |
| Alineación temporal de fundamentales (`as-of` sin *look-ahead*) | Asignar a cada `date` diaria el último dato trimestral cuya `filing_date` sea menor o igual a `date` (agrupado por empresa) | `date`, `filing_date`, métricas trimestrales de PyL, Balance y Cash Flow |
| Días desde última publicación (`days_since_report`) | Diferencia en días naturales o bursátiles entre `date` actual y la `filing_date` vigente | `date`, `filing_date` |
| Métricas TTM (*Trailing Twelve Months*) | Suma de los últimos 4 trimestres disponibles para variables de flujo (o promedio de 4 trimestres para stocks/balances) | Revenue, Gross Profit, EBITDA, EBIT, Net Income, CFO, CapEx, dividendos pagados, partidas de balance |
| Crecimiento YoY de ingresos y beneficios | `(Valor_trimestre_actual - Valor_mismo_trimestre_año_anterior) / abs(Valor_mismo_trimestre_año_anterior)` (o sobre TTM) | Revenue, Net Income, EPS, `period_end`, `filing_date` |
| Capitalización bursátil (`Market Cap`) | `Adjusted Close * Shares Outstanding` (convertido a divisa base si aplica) | `Adjusted Close`, `Shares Outstanding`, `FX` (si aplica) |
| Categoría de `Market Cap` | Clasificación en *Small / Mid / Large Cap* según umbrales definidos o percentiles del mercado | `Market Cap` calculada |
| Deuda total (`Total Debt`) | `Deuda corto plazo + Deuda largo plazo` | Deuda a corto plazo, deuda a largo plazo |
| Deuda neta (`Net Debt`) | `Deuda total - Cash & equivalentes` | `Total Debt`, `Cash & equivalentes` |
| `Working Capital` (si no viene dado o para validar) | `Activo corriente - Pasivo corriente` | Activo corriente, pasivo corriente |
| `Free Cash Flow` (`FCF`, si no viene dado o para validar) | `Operating Cash Flow - CapEx` | Operating Cash Flow, CapEx |
| Márgenes (`Gross Margin %`, margen operativo, margen neto) | `Gross Profit / Revenue`, `EBIT / Revenue`, `Net Income / Revenue` | Gross Profit, EBIT, Net Income, Revenue |
| `ROE` (*Return on Equity*) | `Net Income (TTM) / Total Equity` (promedio) | Net Income, Total Equity |
| `ROA` (*Return on Assets*) | `Net Income (TTM) / Total Assets` (promedio) | Net Income, Total Assets |
| `ROIC` (*Return on Invested Capital*) | `NOPAT / Capital Invertido` (`NOPAT = EBIT * (1 - tasa_efectiva_impuestos)`; `Capital Invertido = Total Debt + Total Equity - Cash & equivalentes`) | EBIT, impuestos / beneficio antes de impuestos, deuda total, total equity, cash & equivalentes |
| `Debt / Equity` | `Total Debt / Total Equity` | `Total Debt`, `Total Equity` |
| `Net Debt / EBITDA` | `Net Debt / EBITDA (TTM)` | `Net Debt`, EBITDA |
| `Current Ratio` | `Activo corriente / Pasivo corriente` | Activo corriente, pasivo corriente |
| `Interest Coverage` | `EBIT (TTM) / Interest Expense (TTM)` | EBIT, gastos por intereses |
| `Asset Turnover` | `Revenue (TTM) / Total Assets` (promedio) | Revenue, Total Assets |
| `P/E` (*Price-to-Earnings*) | `Adjusted Close / EPS (TTM)` | `Adjusted Close`, EPS básico o diluido |
| `P/B` (*Price-to-Book*) | `Market Cap / Total Equity` (o `Adjusted Close / Book Value per Share`) | `Market Cap`, Total Equity, `Shares Outstanding` |
| `EV/EBITDA` (*Enterprise Value / EBITDA*) | `(Market Cap + Total Debt - Cash & equivalentes) / EBITDA (TTM)` | `Market Cap`, `Total Debt`, `Cash & equivalentes`, EBITDA |
| `P/S` (*Price-to-Sales*) | `Market Cap / Revenue (TTM)` | `Market Cap`, Revenue |
| `PEG` (*Price/Earnings-to-Growth*) | `(P/E) / (Tasa de crecimiento YoY de EPS o beneficios en puntos porcentuales)` | `P/E`, crecimiento YoY de EPS o Net Income |
| `Dividend Yield` | `(Dividendos pagados por acción en últimos 12 meses) / Adjusted Close` | Dividendos pagados, `Shares Outstanding`, `Adjusted Close` |
| Retornos a distintos horizontes (`1d`, `1w` ~5d, `1m` ~21d) | `(Adjusted_Close_t / Adjusted_Close_{t-k}) - 1` o `ln(Adjusted_Close_t / Adjusted_Close_{t-k})` | `Adjusted Close` |
| Volatilidad histórica | Desviación estándar de los retornos diarios en ventana móvil (ej. 20 y 60 días), anualizada si procede | `Adjusted Close` (vía retornos diarios) |
| Medias móviles (`20d`, `50d`, `200d`) | Promedio móvil simple o exponencial de `Adjusted Close` en ventanas de 20, 50 y 200 sesiones | `Adjusted Close` |
| `RSI` (*Relative Strength Index*) | Oscilador de momentum (típicamente 14 periodos) basado en ganancias y pérdidas medias | `Adjusted Close` |
| `MACD` | Diferencia entre EMA rápida (12) y EMA lenta (26), junto con línea de señal (EMA 9) | `Adjusted Close` |
| `Beta` respecto al índice de referencia | `Cov(Retorno_acción, Retorno_índice) / Var(Retorno_índice)` en ventana móvil (ej. 252 días) | `Adjusted Close` de la acción, índice de referencia del mercado |
| Normalización por sector y fecha (*z-score* o percentil) | `(Ratio_i,t - Media_sector,t) / DesvStd_sector,t` (o percentil dentro del sector en la fecha `t`) | Ratios seleccionados (`P/E`, `EV/EBITDA`, margen operativo, `ROIC`, `Net Debt/EBITDA`, etc.), `Sector`, `date` |
| Variable objetivo (`Target` de retorno futuro a $N$ días) | `(Adjusted_Close_{t+N} / Adjusted_Close_t) - 1` (o exceso frente al índice / etiqueta de clase) | `Adjusted Close` (y opcionalmente índice de referencia) |

---

## 3. Datos a Emplear en el Modelo

| Dato a emplear | Rol en el modelo | Formato / Tratamiento en entrenamiento |
| --- | --- | --- |
| País / región (sede fiscal) | Feature categórica / contextual | Codificación categórica (nativa en árboles o *one-hot* / *embedding*) |
| Bolsa de cotización | Feature categórica / contextual | Codificación categórica |
| Sector y subsector (GICS) | Feature categórica / contextual + agrupación para normalización | Codificación categórica |
| Categoría de `Market Cap` (*Small / Mid / Large Cap*) | Feature categórica / contextual | Variable ordinal o categórica |
| Divisa de cotización | Feature categórica / contextual | Codificación categórica |
| Días desde última publicación (`days_since_report`) | Feature de frescura de información fundamental | Numérica continua |
| Crecimiento YoY de ingresos y beneficios | Feature fundamental de tendencia | Numérica continua (tratamiento de *outliers* / *winsorizing* si aplica) |
| `Working Capital` (normalizado o escalado si aplica) | Feature fundamental de liquidez operativa | Numérica continua |
| `Free Cash Flow` (`FCF`) | Feature fundamental de generación de caja | Numérica continua |
| Márgenes (`Gross Margin %`, margen operativo, margen neto) | Feature fundamental de rentabilidad operativa | Numérica continua |
| `ROE`, `ROA`, `ROIC` | Features fundamentales de rentabilidad sobre capital/activos | Numérica continua |
| `Debt / Equity`, `Net Debt / EBITDA`, `Current Ratio`, `Interest Coverage` | Features fundamentales de solvencia y apalancamiento | Numérica continua |
| `Asset Turnover` | Feature fundamental de eficiencia de activos | Numérica continua |
| `P/E`, `P/B`, `EV/EBITDA`, `P/S`, `PEG`, `Dividend Yield` | Features de valoración relativa al precio | Numérica continua (gestionar divisiones por cero / negativos) |
| Ratios normalizados por sector y fecha (*z-score* / percentil) | Features de posición relativa dentro del sector en cada fecha | Numérica continua en escala comparable cross-sectional |
| Retornos pasados (`1d`, `1w`, `1m`) | Features de momentum / reversión de corto y medio plazo | Numérica continua |
| Volumen de negociación (o volumen relativo / log-volumen) | Feature de actividad y liquidez de mercado | Numérica continua (recomendable transformar para reducir asimetría) |
| Volatilidad histórica | Feature de régimen de riesgo | Numérica continua |
| Medias móviles (`20d`, `50d`, `200d`, típicamente como ratios o distancias al precio) | Features de tendencia técnica | Numérica continua (preferible `Precio / MA` o distancia % frente a nivel bruto) |
| `RSI`, `MACD` | Features de momentum técnico | Numérica continua |
| `Beta` respecto al índice de referencia | Feature de sensibilidad sistemática al mercado | Numérica continua |
| Tipos de interés, inflación (`IPC`), PIB, tipo de cambio (`FX`) | Features macroeconómicas de contexto | Numérica continua (alineadas a la fecha de disponibilidad del dato) |
| Índice de referencia del mercado (retorno / nivel relativo) | Feature sistémica de entorno de mercado | Numérica continua |
| Variable objetivo (`Target` de retorno futuro a $N$ días) | Etiqueta a predecir (`y`) | Numérica continua (regresión) o categórica (clasificación) |

---

## Divergencias con CLAUDE.md (añadido, no forma parte del texto original)
Manda `CLAUDE.md`. Puntos del plan original que lo contradicen y deben corregirse al implementar:
1. **Market Cap, P/E, P/B, P/S, Dividend Yield** usan aquí `Adjusted Close`. `CLAUDE.md` (regla 4) exige `Close` sin ajustar × acciones vigentes en esa fecha.
2. **Target:** aquí `Adjusted_Close_{t+N} / Adjusted_Close_t - 1`. `CLAUDE.md` (regla 5) fija `ln(P_{t+1+N} / P_{t+1})`, con entrada al cierre de `t+1`.
3. **Alineación:** aquí por `filing_date`. `CLAUDE.md` (regla 1) usa `available_at` (fecha de aceptación del filing, y sesión siguiente si sale tras el cierre).
4. **Tipos de interés, IPC y PIB:** deben usarse en su versión original no revisada (regla 2) y alineados por fecha de publicación.
5. **ROE, ROA, Asset Turnover** dicen "(promedio)" sin definir el promedio: definido en `docs/decisiones/0002-promedio-balances-roe-roa.md` (media de 5 balances trimestrales; fallback inicio y fin; revisable).
6. **Magnitudes crudas** (Working Capital, FCF) deben escalarse por activos, market cap o ventas.
