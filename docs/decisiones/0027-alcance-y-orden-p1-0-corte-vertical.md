# ADR 0027: Alcance y orden, P1-0, corte vertical y go/no-go (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-9, con las decisiones v3 y v3.1.

**Contexto.** El plan original dejaba los fundamentales de CNMV como requisito previo del primer "sistema OK", con meses de trabajo manual no presupuestado y sin saber si la muestra permite detectar algo.

**Decisión.** Orden: **P1-0** (N_eff, ventanas evaluables, error típico del RankIC de los baselines transversales y MDE, solo con precios y composición de BME, con permutación real) → **go/no-go 1** → composición, precios de toda la vida de la cotización, referencia y macro → **corte vertical con el plan B** (IBEX, precios, unas 8 técnicas, h90, Ridge, baselines transversales, walk-forward con purga, informe) → **go/no-go 2** → fundamentales de CNMV como bloque. Solo se construye P7a (inferencia y registro); P7b queda aplazado. Predicciones archivadas desde el primer baseline. Mercado Continuo: decisión condicionada al MDE de P1-0; hay que verificar la cobertura de Bolsamanía y la composición histórica (no verificado). Regla de go/no-go: si el MDE del IBEX a h90 es > 0,05 y el Mercado Continuo no lo baja a ≤ 0,05, el IBEX pasa a universo de validación técnica; igual criterio a h365 con su MDE. **Los go/no-go se disparan por hito, no por fecha; Enrique fija las horas en el primero.**

**Alternativas.** Mantener el orden P1 → P2 → ... con fundamentales primero.

**Consecuencias.** Decisiones abiertas: horas y fechas de cada go/no-go. F2 se presenta como ampliación de datos y validación técnica del pipeline, no como evidencia independiente (comparte ciclo). La fase se detalla en `docs/plan_fases.md`.
