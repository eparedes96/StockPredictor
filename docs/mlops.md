# Inferencia y mejora continua
Diseño vigente. Todo umbral, frecuencia y calendario es **provisional y no medido**; se fija antes de ver resultados y se calibra con repetición histórica as-of en F1.

## Inferencia
- Una API Python estable (`predict(as_of, universe_id, horizon, ...)` devuelve un DataFrame polars con contrato) sobre la que se apoyan la CLI y una interfaz futura. Sin rutas absolutas ni estado oculto.
- Subcomandos: `fetch`, `predict`, `monitor`, `retrain`, `promote`, `housekeeping`, `export-model` (vía única; ADR 0015).
- Misma lógica de `transform` y `features` que en entrenamiento: se recomputa el histórico completo y se devuelve la fila pedida. Mismo criterio de `available_at` que en entrenamiento, fuente por fuente (donde se entrenó con fecha estimada, la inferencia usa también la estimada hasta que la paridad demuestre que la diferencia es despreciable).
- Cada predicción guarda `model_version`, `data_as_of`, `prediction_status` y la calidad de entrada. Se archiva (inmutable) en `data/predictions/` para el paper trading. Datos de prueba nunca van al archivo oficial. Antes de tener señal, las predicciones son experimentales y no consejo de inversión.
- Si el proveedor bloquea o falta una sesión, se marca la entrada como obsoleta y `predict` se niega o avisa según el umbral de frescura. Instantánea de entrada en `data/snapshots/`.

## Registro
`models/{universe_id}/h{N}/v{versión}/` con `metadata.json`, preprocesador y estado de los transformadores; `CHAMPION` por universo y horizonte (ver `models/README.md`). Formato de serialización sin código ejecutable; hash y versión de esquema verificados al cargar. Si el hash del champion no coincide, `predict` se niega.

## Disparadores
- **Principal:** drift de features, de nulos y de predicciones frente a la distribución de entrenamiento (PSI o KS por feature, tasa de nulos, frescura), más calendario. Método y umbrales sin verificar.
- **El RankIC realizado** sobre predicciones maduras se reporta con N_eff e intervalo por bloques y **solo avisa**: a 365 días el primer resultado tarda más de un año y a 1500 más de cuatro. No es disparador por sí solo.
- Drift por régimen: distribución de predicciones por periodo y correlación de la predicción media con el retorno de mercado reciente, como diagnóstico.

## Reentrenamiento
- **Refresco:** misma especificación congelada (features, hiperparámetros, semilla pre-registrada); solo se añaden datos. Calendario propuesto sin base medida: h90 trimestral; h365 y h1500 semestral o anual; más disparo por drift fuerte o cambio de universo.
- **Candidato nuevo:** cualquier cambio de especificación; sigue el proceso de evaluación con su hash y su propio test.

## Promoción (champion/challenger)
- No se reutiliza el test final del candidato anterior. Un refresco se comprueba con walk-forward reciente anterior a su entrenamiento, paridad, drift y comparación sombra con el champion. Un candidato nuevo necesita un bloque posterior a todo dato usado para elegirlo, con consulta registrada y hash congelado.
- **Asistida:** el sistema propone con informe y Enrique aprueba; la decisión queda registrada en `experiments/` (y como ADR corto si cambia reglas). Criterios provisionales: no peor en riesgo, mejora mínima fijada de antemano, intervalo con bloques que respeten el solape, paridad y drift en verde. Se pre-registran antes de la primera promoción.
- **En horizontes largos casi nunca se promoverá:** cada candidato nuevo agota el bloque posterior y los resultados maduros tardan años. "No promover" es el valor por defecto. Es coherente con el diseño, pero la mejora continua es lenta por construcción.
- `promote --rollback` restaura el champion anterior sin tocar datos; el champion previo se conserva siempre.
- Si ningún modelo supera a los baselines, el champion es el baseline etiquetado.

## Versión ligera y datos propios
- Perfil del mismo paquete (`uv sync --no-dev`): `predict`, `monitor`, `export-model`/`import-model`. Significa **pocas dependencias, no pocos datos**: necesita las entradas históricas completas que exige su modelo. No importa `training/`, `evaluation/` ni `extraction/`.
- Datos propios: pasan por el validador de contrato (esquema, unidades, divisa, `available_at`) y por una comprobación de compatibilidad con el modelo. Datos reales sin `available_at` se rechazan. No se mezclan con `raw` oficial.

## Retención y copia
Ver ADR 0018. Copia fuera del equipo, manual o programada, de lo insustituible: predicciones archivadas, champions, instantáneas referenciadas y manifiestos. Lo demás se regenera.
