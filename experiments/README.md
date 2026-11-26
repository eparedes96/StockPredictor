# experiments/
Registro de lo que **entrena, evalúa o consulta el test** (ADR 0015). Es evidencia: se versiona o se respalda, y **no se purga** si respalda un modelo registrado o una consulta al test.

- `test_access_log.csv`: una fila por consulta al test final (ADR 0021). Un candidato se toca una vez; cada consulta cuenta para la deflación Bonferroni por hashes.
- `promotions_log.csv`: promociones y rollbacks de champion (asistidas; ver `docs/mlops.md`).
- Subcarpetas por run de entrenamiento o evaluación, con configuración, hash de datos, commit y métricas (por crear con el código).

Los resúmenes de ejecución de las etapas del pipeline (`fetch`, `transform`, `features`, `dataset`, `predict`, `monitor`, calidad) van en `runs/`, no aquí.
