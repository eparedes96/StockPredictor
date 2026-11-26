# ADR 0003: Entorno, empaquetado y crecimiento (2026-11-25)
**Contexto.** El proyecto debe poder crecer hacia terminal, versión ligera, instalable e interfaz, sin rehacer la base.
**Decisión.**
1. **uv** como gestor: `uv.lock` versionado, `.python-version` = 3.12, `requires-python >=3.11,<3.14`. CI prueba 3.11 y 3.12.
2. **Paquete instalable** (`src/` layout, build setuptools) con entrada `stockpredictor` (`stockpredictor.cli:main`, también `python -m stockpredictor`). La CLI usa solo la librería estándar; cada etapa será un subcomando.
3. **Núcleo ligero** (polars, DuckDB, scikit-learn, LightGBM, pyarrow). La interfaz va en el extra `ui` (streamlit, sin usar aún). pandas sigue siendo extra opcional.
4. **Calidad:** ruff (con `pandas` prohibido por lint fuera de training/evaluation), mypy, pytest (marcadores `leakage`, `network`), pre-commit y CI en GitHub Actions.
5. Secretos en `.env` (ignorado); plantilla en `.env.example`.
**Alternativas.** pip-tools (más manual); Poetry (más pesado). Para la UI, FastAPI + frontend propio (más flexible, mucho más trabajo); se decide cuando haga falta.
**Pendiente (2026-11-26).** Repetir con `uv.lock` en Python 3.12 las pruebas de pandera.polars y de calendarios y la compatibilidad de polars con LightGBM y scikit-learn (las previas se hicieron con 3.13 y polars 2.2.0) antes de darlo por probado; si algo cambia, ADR nuevo.

**Consecuencias.** Instalar: `uv sync` (desarrollo) o `uv sync --no-dev` (ligero); con interfaz: `uv sync --extra ui`. Las versiones de los hooks de pre-commit y de las acciones de CI no se han ejecutado todavía en GitHub.
