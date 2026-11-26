# tests/
Sin tests de pipeline todavía. Se crean primero con **datos sintéticos** (`fixtures/`); la muestra real solo en local y marcada. Un cambio en features o alineación no se da por bueno sin pasarlos.

- `unit/`: una prueba por fórmula (ROIC, TTM, márgenes...) con valores a mano y referencia independiente en el grupo `dev`.
- `leakage/`: cambiar un dato futuro no altera ninguna fila pasada. Previstos: alineación y features (P3, P4), `test_target`, `test_splits_purge` (invariante de purga, ADR 0008), `test_fit_isolation`, `test_dataset_hash`, equivalencia incremental, y **dos calendarios** de mercados distintos.
- `integration/`: pipeline completo con sintéticos y un dataset F1 congelado. Marcadores `leakage` y `network` en `pyproject.toml`.
- `fixtures/`: datos sintéticos compartidos, con casos inyectados.
- Perfil ligero: un test de importación comprobará que `predict` no importa `training/`, `evaluation/` ni `extraction/` (ADR 0003).
