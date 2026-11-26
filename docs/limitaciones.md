# Limitaciones conocidas
Lo marcado "no verificado" no se ha comprobado. Los datos de proveedores de abajo vienen del estudio de fuentes de la planificación, con una o pocas empresas por caso.

## Sesgo de supervivencia (todo resultado se etiqueta así mientras aplique)
- **No hay precios gratuitos de empresas deslistadas fuera de España.** En España, Bolsamanía las cubre con calidad inferior (`source_tier`). En EE. UU. solo algunas (p. ej. FRCB y SBNY sí; TWTR y ATVI no, verificado con pocos casos). Yahoo responde 404 a las desaparecidas. En Corea hay fundamentales de deslistadas, pero no precios.
- Consecuencia: el sesgo en F2 y F3 es cuantificable pero no corregible. Se mide por año el porcentaje de miembros sin precio (umbrales provisionales: 90 % de fechas con composición y 80 % de miembros con precio).
- IBEX 35: hay PDF oficial de BME con 137 revisiones (1991-2026); falta mapear códigos a empresa. Las salidas con `price_quality = close_only` tienen target sin dividendos (ADR 0006).

## Datos y fuentes
- **Precios:** un solo proveedor no oficial (Yahoo), accesible solo desde el equipo de Enrique (429 desde el cloud) y sin segunda fuente para `adj_close`. Cualquier cambio de formato o bloqueo detiene F2 y F3.
- **`Close` real** solo en España (Bolsamanía, sin volumen; coherencia interna verificada en 8 de 8 empresas, con escalones sin explicar en Sabadell y Sacyr, y `Variación %` de Bolsamanía no utilizable) y Taiwán. En el resto, valoraciones apagadas (ADR 0013).
- **Fundamentales de España:** solo semestrales (CNMV IPP), historia XBRL desde 2005-07-01. `available_at` con fecha y sin hora verificada. El mercado pudo conocer las cifras antes por la nota de resultados (la fecha de CNMV es conservadora).
- **Acciones en circulación en España:** sin fuente verificada (BORME es candidato). La market cap española queda `shares_low_quality`.
- **Sector:** histórico solo en EE. UU. (SIC por filing). Fuera, sector actual con `not_point_in_time`.
- **Macro:** vintages solo de EE. UU. (ALFRED). Zona euro y España: instantánea propia desde la fecha en que se empiece a guardar; lo anterior es la versión revisada, no la original (`not_point_in_time`; regla 2).
- **Índice de referencia:** sin retorno total gratuito; se usa el índice de precio, etiquetado. Proxy con ETF, sin probar.
- **FX:** hora oficial de publicación del BCE sin verificar.
- **Retraso conservador de `available_at`:** se calibra con la distribución real y es global, no por fold (ADR 0014). Los parámetros estructurales se calibran con datos anteriores al test final.
- **Licencias y términos de uso:** no se registran por proveedor. El proyecto es de uso propio (ADR 0010); si deja de serlo hay que revisar cada fuente.

## Modelado
- **Pocas observaciones independientes.** Con unos 21 años de fundamentales, N=1500 probablemente quede exploratorio o no evaluable (ADR 0007; aritmética sin medir). Más empresas no ayudan: comparten ciclo.
- **Muestra pequeña** (unas 35 empresas, unas 29 features de nivel A/B): riesgo alto de sobreajuste; modelo de control de 10 a 12 features sin valoración.
- **Régimen de mercado:** el retorno absoluto a largo plazo lo domina el ciclo. F2 y F3 comparten ciclo con F1, así que F2 no es una réplica independiente. Reportar siempre por subperiodo.
- **Costes de transacción y liquidez:** supuestos etiquetados. Sin volumen en Bolsamanía, el filtro de liquidez es "no filtrable" para esas filas. Los costes no dicen que un mercado sea operable desde España (ADR 0011).
- **Mejora continua lenta por construcción:** a N=365 y 1500 los primeros resultados maduros tardan más de 1 y más de 4 años; "no promover" es el valor por defecto (`docs/mlops.md`).

## Entorno
- Las pruebas de librerías de contratos y calendarios se hicieron con Python 3.13 y polars 2.2.0; el proyecto fija 3.12. Repetir la prueba mínima con `uv.lock`.
