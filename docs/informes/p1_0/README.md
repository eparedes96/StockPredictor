# P1-0: N_eff y MDE solo con precios (ADR 0027)
**Estado: ejecutada con precios de Yahoo (instantánea 2026-11-26), con sesgo de supervivencia (sin deslistadas). Resultados en `informe.md`; regenerar con `stockpredictor report-p1-0 --snapshot 2026-11-26 --raw-dir <raw>`. Definiciones en el ADR 0034.** Es la fase previa: decide si compensa el trabajo grande de fundamentales. Entradas: Yahoo `adjclose` del IBEX histórico y la composición de BME (`data/reference/`). Sin fundamentales.

## Entregable: `informe.md` en esta carpeta
Por horizonte (h90 y h365), con target transversal `y_cs`, fechas semanales (h90) y mensuales (h365):
- ventanas disjuntas fuera de muestra evaluables, con train mínimo hipotético de 5, 8 y 10 años (y las del periodo entero, informativas);
- N_eff y correlación transversal de los targets;
- error típico real del RankIC de momentum 12-1, reversión a 1 mes y baja volatilidad 60 (Spearman por fecha);
- **MDE** (α = 5 %) frente al efecto de interés 0,05, y contraste de permutación real (1.000 repeticiones);
- porcentaje de salidas del índice con precios posteriores a la salida y estimación de horas de las tablas manuales.

La aritmética orientativa de la revisión crítica (MDE ≈ 0,066 a h90, ≈ 0,13 a h365 con fundamentales, ≈ 0,095 a h365 solo con precios) **no está medida**; este informe la sustituye por el número real.

## Go/no-go 1
Se registra en `docs/decisiones/go_no_go.md`. Regla: si el MDE del IBEX a h90 es > 0,05 y el Mercado Continuo no lo baja a ≤ 0,05, el IBEX pasa a universo de validación técnica. Las horas las fija Enrique en este primer go/no-go.
