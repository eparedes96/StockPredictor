# data/
Fuera de git salvo los `.gitkeep` y las tablas manuales de `reference/`. Capas: `raw` (instantáneas inmutables con proveedor, fecha y manifiesto) → `interim` (limpio, tipado, bitemporal; `_quarantine/`, `_reports/`) → `features` → `datasets/{universe_id}/h{N}/v{hash}/`. Además: `predictions/` (archivo inmutable), `snapshots/`, `archive/` y `user/` (datos propios validados); estas cuatro se crean al usarlas.

Reglas de retención: ADR 0018. No se edita `raw` a mano. Primera tarea de extracción: **guardar ya las instantáneas de macro europea** (cada semana sin guardar es historia irrecuperable).
