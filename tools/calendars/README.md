# tools/calendars/
Genera calendarios de sesiones por mercado a Parquet (apertura y cierre en UTC, con cierres anticipados). **Usa pandas** (`exchange_calendars` lo exige): por eso vive fuera de `src/` y con el extra `calendars`; ruff lo permite solo aquí (ADR 0015). El pipeline solo lee el Parquet.

Se lanza con el subcomando `stockpredictor calendars` (aún sin implementar). Pendiente: comprobar el límite `start` de la librería y repetir la prueba con `uv.lock` en Python 3.12. Sin código todavía.
