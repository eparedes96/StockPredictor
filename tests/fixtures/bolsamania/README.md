# Fixtures de Bolsamanía

Grabadas de respuestas reales el 2026-11-28 (POST a `/accion/<slug>/historico-precios` con `startDate`, `endDate`, `output`) y reducidas al `<h1>` y a la tabla `table-bm`; el resto de la página (menús, boletín) se ha eliminado. Las cifras de `BANKINTER...html` son las reales de la respuesta (2007-07-16..31, con el split 5:1 del 2007-07-23: el precio cae de 64,05 a 13,04 y la columna `Variación %` dice +1,80 %, ajustada).

- `empty.html`: slug válido sin datos en el rango (`No se han encontrado resultados`).
- `slug_not_found.html`: slug inexistente (HTTP 200 con `Página no encontrada`).
- `no_history.html`: ficha sin sección de históricos (GAMESA).
