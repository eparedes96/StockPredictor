# ADR 0013: Valoraciones apagadas sin `Close` real verificado (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique.

**Contexto.** La regla 4 exige `Close` sin ajustar para market cap y ratios de valoración. Yahoo solo entrega un `close` ya ajustado por splits y los eventos que no declara quedan ocultos. Solo España (Bolsamanía) y Taiwán tienen `Close` real; en EE. UU. y el resto no hay segunda fuente.

**Decisión.** En cada mercado sin `Close` real, las valoraciones (market cap, P/E, P/B, P/S, EV, dividend yield) quedan **apagadas** (`valuation_enabled: false`) hasta contar con una muestra de **10 cierres reales verificados**. Entonces, por ADR, se activan solo en ese mercado. Se declara en la ficha de cada mercado. En España se activan, con acciones en circulación marcadas `shares_low_quality` mientras no haya fuente verificada; si la regla de Bolsamanía falla con el universo real, la calidad baja a `adj_only` y se apagan.

**Alternativas.** Calcular con el factor acumulado de splits donde los eventos fueran verificables (versión inicial, provisional); calcular igualmente con `close` ajustado (valoraciones falsas).

**Consecuencias.** En F2 el bloque de valoración empieza vacío y la evaluación lo reporta. El modelo de control de la evaluación excluye las features de valoración.
