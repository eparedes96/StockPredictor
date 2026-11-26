# ADR 0004: Promedio de balance con datos semestrales (2026-11-26)
**Estado.** Aceptado por Enrique. Sustituye al ADR 0002.

**Contexto.** El ADR 0002 suponía balances trimestrales. La fuente de fundamentales de España (CNMV IPP) es solo semestral, así que la ventana TTM y el promedio de balance cambian.

**Decisión.** El denominador de ROE, ROA y Asset Turnover (y el capital invertido del ROIC) es la media de 3 balances semestrales: T−12 meses, T−6 meses y T. Si faltan, se cae a 2 puntos y luego a 1, y cada fila registra el caso (`avg_case`). Todos los balances se alinean por `available_at`. El TTM es `acumulado_actual + FY_previo − acumulado_previo_mismo_periodo`, sin desacumular; el crecimiento compara el mismo acumulado del año anterior (H1/H1, FY/FY). Se exigen 12 meses exactos por `period_start`/`period_end`; si no, `insufficient_history`.

**Alternativas.** Mantener 5 balances trimestrales (no existen en España); solo balance final; media de inicio y fin (más simple, menos robusta).

**Consecuencias.** El umbral del plan B de fundamentales se expresa en años (4 años con `available_at` real). Es una hipótesis de diseño sin evidencia: se comprueba por ablación en la evaluación. Para fuentes trimestrales (EE. UU.) la lógica se adaptará a sus periodos al abrir F2.
