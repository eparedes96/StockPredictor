# ADR 0034: Extracción de precios de Bolsamanía como complemento de Yahoo (2026-11-28)
**Estado.** Aceptado por el coordinador (P1-0, incremento 2b); pendiente de revisión de Enrique.

**Contexto.** Yahoo no tiene 33 empresas que pasaron por el IBEX (404, deslistadas) y empieza en 2000-01-03 (ADR 0033). Bolsamanía (P1.2 ronda 11, P2.1) da el `Close` real sin ajustar en la columna `Precio`, sin volumen; `Variación %` está ajustada y no se usa. Comprobado el 2026-11-28 desde el navegador de Enrique: la serie más antigua empieza el **2006-11-30** (Santander, Bankinter; sin filas en 1995, 2000 ni 2005), así que **no cubre 1993-1999 ni 2000-2006**.

**Decisión.**
- **Alcance.** Solo las 33 empresas sin datos en Yahoo (`purpose = gap_fill`) más 8 con las dos series para el diagnóstico (`comparison`). Lo que acaba antes de 2006-11-30 no se pide (13 empresas) y se declara.
- **Unidad de descarga.** Tramo `(slug, desde, hasta)` de 92 días por POST a `/accion/<slug>/historico-precios` (`startDate`, `endDate`). La web devuelve como mucho ~85 filas, las más recientes: un tramo con ≥ 80 filas se parte por la mitad y no se guarda como bueno.
- **Raw.** HTML de cada respuesta, comprimido en gzip determinista, inmutable, con manifiesto (sha256, filas, fechas, intentos) y una fila por tramo (la última manda). Estados cacheados: `ok`, `empty`, `slug_not_found` (HTTP 200 con "Página no encontrada") y `no_history` (ficha sin sección de históricos). Una página que no encaja en ninguno es anómala: cuenta como error y tres seguidas paran la ejecución.
- **Tasa.** 2 s más hasta 0,3 s de jitter; backoff ante 429/5xx; sin reintento ante 403; sin evasión de controles.
- **Slugs.** `data/reference/bolsamania_slugs.csv` por `company_id`, manual (el slug no sigue al ticker: `BANCO-SANTANDER`, `MEDIASET-ESPANA` para Telecinco, `POPULAR` es una acción de EE. UU.). Nacen `candidate`.
- **Tabla.** `prices.parquet` con `close_raw`, `high`, `low`, `open`, `price_quality = close_only` y `source = bolsamania`. Sin volumen y sin `Variación %` (test).
- **Diagnóstico P2 10a.** En las empresas con las dos series, el cociente `close_raw / adj_close` por fecha común; un escalón (|Δln| > 0,5 %) es un evento candidato. Solo diagnóstico: no se confirma ni se ajusta nada.
- **Dónde corre.** El cloud no llega a `www.bolsamania.com` (proxy); la descarga oficial se ejecuta en el equipo de Enrique.

**Alternativas.** Pedir años enteros (se trunca a 85 filas sin avisar); ajustar el precio de Bolsamanía con Yahoo (mezcla fuentes y oculta eventos); inferir slugs por nombre automáticamente (no determinista).

**Consecuencias.**
- 1993-1999 sigue sin precios para todos los miembros, y 2000-2006-11 sin precios para las 33 empresas sin Yahoo. El sesgo de supervivencia en esos años no baja con este incremento.
- Las empresas recuperadas son `close_only`: sin `adj_close`, el target de P5 usa precio sin dividendos y el detector de escalones no puede aplicarse (P2 46a, ADR 0006).
- Los slugs son manuales y se descubren a mano; los que no se hallaron quedan con `slug_status = none` y la lista de intentos en `notes`.
