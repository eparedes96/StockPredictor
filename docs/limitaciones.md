# Limitaciones conocidas
Lo marcado "no verificado" no se ha comprobado. Los datos de proveedores de abajo vienen del estudio de fuentes de la planificación, con una o pocas empresas por caso.

## Sesgo de supervivencia (todo resultado se etiqueta así mientras aplique)
- **No hay precios gratuitos de empresas deslistadas fuera de España.** En España, Bolsamanía las cubre con calidad inferior (`source_tier`). En EE. UU. solo algunas (p. ej. FRCB y SBNY sí; TWTR y ATVI no, verificado con pocos casos). Yahoo responde 404 a las desaparecidas. En Corea hay fundamentales de deslistadas, pero no precios.
- Consecuencia: el sesgo en F2 y F3 es cuantificable pero no corregible. Se mide por año el porcentaje de miembros sin precio (umbrales provisionales: 90 % de fechas con composición y 80 % de miembros con precio).
- IBEX 35: parseado el PDF oficial de BME (137 revisiones, 1991-2026; ADR 0032). Composición anterior al lanzamiento (1992-01-14) reconstruida por BME y no contrastable con una fuente gratuita (31 códigos inferidos de las bajas + 4 por el recuento; el CNMV coincide en 21 de 26 empresas). Fecha de efecto frente a fecha de anuncio sin verificar. 103 de 134 filas del mapa contrastadas con Wikipedia, 7 códigos sin identificar y 24 con conflicto o sin segunda fuente. El 36 de 2012 es un hecho real; el 33 de 2006 no tiene segunda fuente de fecha. Las salidas con `price_quality = close_only` tienen target sin dividendos (ADR 0006).

## Datos y fuentes
- **Precios:** un solo proveedor no oficial (Yahoo), accesible solo desde el equipo de Enrique (429 desde el cloud) y sin segunda fuente para `adj_close`. Cualquier cambio de formato o bloqueo detiene F2 y F3. **`adj_close` cambia con cada dividendo posterior**: cada descarga es una instantánea y se prevé un test de regresión de retornos entre instantáneas. Los ajustes no declarados podrían deberse a ampliaciones con derechos o scrip (hipótesis sin verificar; prueba con 2 o 3 empresas antes de cerrar P2).
- **`Close` real** solo en España (Bolsamanía, sin volumen; coherencia interna verificada en 8 de 8 empresas, con escalones sin explicar en Sabadell y Sacyr, y `Variación %` de Bolsamanía no utilizable) y Taiwán. En el resto, valoraciones apagadas (ADR 0013).
- **Fundamentales de España:** solo semestrales (CNMV IPP), historia XBRL desde 2005-07-01. `available_at` con fecha y sin hora verificada. El mercado pudo conocer las cifras antes por la nota de resultados (la fecha de CNMV es conservadora).
- **Acciones en circulación en España:** sin fuente verificada (BORME es candidato). La market cap española queda `shares_low_quality`.
- **Sector:** histórico solo en EE. UU. (SIC por filing). Fuera, sector actual con `not_point_in_time`.
- **Macro:** vintages solo de EE. UU. (ALFRED). Zona euro y España: instantánea propia desde la fecha en que se empiece a guardar; lo anterior es la versión revisada, no la original (`not_point_in_time`; regla 2).
- **Índice de referencia:** sin retorno total gratuito; se usa el índice de precio, etiquetado. Proxy con ETF, sin probar.
- **FX:** hora oficial de publicación del BCE sin verificar.
- **Precios de toda la vida de la cotización:** se descargan completos, no solo la etapa en el índice. Las tablas manuales (mapeo de códigos de BME, `exit_events`, revisión de saltos) son trabajo manual aún sin estimar en horas: 137 revisiones y cambios de código indistinguibles de salidas reales.
- **Varias clases de acciones:** provisional la más líquida (mediana del valor negociado de 60 sesiones, point-in-time); la otra queda fuera del panel transversal. Peseta/euro: solo importes de liquidez, a 166,386; los retornos no cambian.
- **Retenciones sobre dividendos:** sin decidir.
- **Retraso conservador de `available_at`:** se calibra con la distribución real y es global, no por fold (ADR 0020). Los parámetros estructurales se calibran con datos anteriores al test final.
- **Licencias y términos de uso:** no se registran por proveedor. El proyecto es de uso propio (ADR 0010); si deja de serlo hay que revisar cada fuente.

## Modelado
- **Potencia limitada.** Con unas 35 empresas y unas 13 observaciones independientes a 365 días, el MDE orientativo del RankIC va de unos 0,066 (h90) a unos 0,13 (h365) con fundamentales (aritmética de la revisión crítica, **no medida**; P1-0 la sustituye por el número real). Frente al efecto de interés de 0,05, lo esperable en el IBEX es "no concluyente", sobre todo a 365 (ADR 0019). Más empresas del mismo mercado no ayudan: comparten ciclo.
- **h1500 sin modelo** (ADR 0030): solo estadística descriptiva. Si se reactiva, probablemente sería exploratorio o no evaluable (unas 2 ventanas fuera de muestra con unos 21 años; sin medir).
- **El test final es control de catástrofes**, no confirmación: con 3 años a h365 su MDE ronda 0,27 (orientativo). La confirmación real es hacia delante (ADR 0021).
- **Componente de mercado:** el modelo transversal no predice el nivel del mercado; el componente de mercado es la media histórica expansiva y se evalúa aparte sin pretensión de poder predictivo (ADR 0029). El retorno absoluto predicho es, en la práctica, selección relativa más esa media.
- **Muestra pequeña** (unas 35 empresas, unas 29 features de nivel A/B): riesgo alto de sobreajuste; modelo de control de 10 a 12 features sin valoración.
- **Régimen de mercado:** el retorno absoluto a largo plazo lo domina el ciclo. F2 y F3 comparten ciclo con F1, así que F2 no es una réplica independiente. Reportar siempre por subperiodo.
- **Costes de transacción y liquidez:** supuestos etiquetados. Sin volumen en Bolsamanía, el filtro de liquidez es "no filtrable" para esas filas. Los costes no dicen que un mercado sea operable desde España (ADR 0011).
- **Mejora continua lenta por construcción:** a N=365 los primeros resultados maduros tardan más de 1 año; "no promover" es el valor por defecto (`docs/mlops.md`).

## Entorno
- Las pruebas de librerías de contratos y calendarios se hicieron con Python 3.13 y polars 2.2.0; el proyecto fija 3.12. Repetir la prueba mínima con `uv.lock`.
