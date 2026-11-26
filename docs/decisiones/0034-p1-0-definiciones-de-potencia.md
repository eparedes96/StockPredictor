# ADR 0034: Definiciones operativas de P1-0 (potencia solo con precios) (2026-11-26)
**Estado.** Propuesto por el hilo de desarrollo; pendiente de revisión del coordinador y de Enrique.

**Contexto.** Los ADR 0019, 0022 y 0027 fijan qué medir (N_eff, error típico, MDE, permutación) pero no las definiciones operativas con las que se calcula.

**Decisión.**
- **Fechas de decisión:** última sesión de cada semana ISO (h90) o mes (h365). Calendario de sesiones = unión de fechas con precio de alguna empresa.
- **Fuera de muestra:** empieza tras `prices_from + train mínimo` (8 años principal; 5 y 10 como sensibilidad), la purga por fin de etiqueta y 5 sesiones de embargo. Acaba antes del bloque reservado de 3 años (ADR 0021) menos el embargo. El bloque reservado no entra en ningún retorno ni RankIC.
- **N_eff:** tamaño de la submuestra de etiquetas disjuntas (entrada ≥ fin de la etiqueta anterior), mediana entre todos los desfases iniciales.
- **Error típico y t:** por submuestra disjunta y desfase; se reporta la media entre desfases. σ = desviación típica del RankIC por fecha en la submuestra.
- **MDE:** α = 5 % bilateral, potencia 80 %, t de Student no central con n−1 g.l. y σ empírica. **Cifra titular = mediana de los tres baselines.** Etiqueta "detectable" si MDE ≤ 0,05; si no, "no concluyente por diseño".
- **σ nula (permutación):** se reporta aparte como cota optimista; no se usa para etiquetar, porque el RankIC varía en el tiempo más de lo que explica el azar.
- **Permutación:** 1.000 repeticiones, semilla fija, barajando `y_cs` entre nombres dentro de cada fecha.
- **Señales:** momentum 12-1 (ln P[t−21] − ln P[t−252]), baja volatilidad 60 (−σ de retornos diarios, ≥ 48 observaciones) y reversión a 1 mes (−ln P[t]/P[t−21]); ventanas en sesiones, solo `adj_close`.

**Alternativas.** MDE titular con la σ nula (da ~0,07 a h90 y ~0,16 a h365); el máximo de los baselines; una sola señal.

**Consecuencias.** Elegir la mediana y la σ empírica es una decisión de diseño que cambia el resultado frente a la σ nula; queda registrada para revisión. Todo resultado lleva "con sesgo de supervivencia (sin deslistadas)" hasta integrar Bolsamanía.
