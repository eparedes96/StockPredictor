# Cómo contribuir
Flujo de ramas decidido en el ADR 0031.

## Ramas
- `main`: estable. Solo recibe PR desde `develop`, cuando Enrique lo pide y no hay fallos.
- `develop`: integración. Recibe PR de las ramas cortas.
- Ramas cortas por tarea, desde `develop`: `feat/…`, `fix/…`, `docs/…`. Una tarea, una rama, un PR contra `develop`. Se borran al fusionar.
- Sin commits directos en `main` ni en `develop`.

## Pull requests
1. Rama desde `develop` actualizado.
2. Antes de abrir el PR: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` y `uv run pytest`.
3. Cambios que modifican una regla de `CLAUDE.md` o una decisión de fondo llevan ADR nuevo en `docs/decisiones/` (siguiente número libre) y actualizan su índice.
4. PR contra `develop` con el CI en verde. Si hay PR apilados, se fusionan en orden con commit de merge (sin squash).
5. Mensaje de merge descriptivo: título con lo que cambia y cuerpo con el porqué, las decisiones tocadas y lo no verificado.
6. Fusión de `develop` a `main`: PR aparte, solo a petición de Enrique.

## Commits
Mensajes en español, en imperativo, con el qué y el porqué. Datos, secretos y `.env` nunca van a git.

## Protección de ramas (ajustes de GitHub)
La protección no se puede crear desde las herramientas de Claude; hay que pulsarla en **Settings → Branches → Add branch ruleset** (o regla clásica):

**`main`**
- Require a pull request before merging, con la rama de origen `develop`.
- Require status checks to pass: `test (3.11)` y `test (3.12)`; con "Require branches to be up to date".
- Block force pushes y Restrict deletions.

**`develop`**
- Require status checks to pass: `test (3.11)` y `test (3.12)`.
- Block force pushes y Restrict deletions.

GitHub no filtra por rama de origen en las reglas clásicas: "solo PR desde `develop`" se garantiza por convención (o con un workflow que falle si el PR a `main` no viene de `develop`).
