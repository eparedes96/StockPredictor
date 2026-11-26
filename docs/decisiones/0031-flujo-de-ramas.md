# ADR 0031: Flujo de ramas, `main`, `develop` y ramas cortas (2026-11-26)
**Estado.** Aceptado por Enrique.

**Contexto.** El repositorio nació con `main` y los tres primeros PR se apilaron sobre ramas de trabajo. Hace falta un flujo estable antes del primer código.

**Decisión.** `main` es la rama estable; `develop` es la de integración; el trabajo va en ramas cortas por tarea (`feat/`, `fix/`, `docs/`) que se abren por PR contra `develop`. Los cambios pasan de `develop` a `main` por PR solo si no hay fallos y cuando Enrique lo pide. `main` solo recibe PR desde `develop`, con CI obligatorio, sin force-push ni borrado. `develop` exige CI y no admite force-push. Los PR se fusionan con commit de merge y un mensaje descriptivo (los PR apilados se encadenan sin squash).

**Alternativas.** Trunk-based puro (todo a `main`); GitFlow completo con ramas de release.

**Consecuencias.** La protección de ramas se configura en GitHub (ver `CONTRIBUTING.md`); hasta que se active, el flujo se cumple por convención. El CI corre en PR y en push a `main` y `develop`.
