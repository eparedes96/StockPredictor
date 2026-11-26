# ADR 0011: La accesibilidad desde España no es filtro (2026-11-26)
**Estado.** Aceptado por Enrique.

**Contexto.** F3 se definía como "mercados accesibles desde España", lo que dependía del bróker y bloqueaba la fase. Enrique: "es una herramienta".

**Decisión.** Entra en F3 todo mercado cuya ficha (`configs/markets/`) tenga estado `ready`, `viable` o `partial`. `accessible_from_spain` queda como metadato opcional, vacío por defecto y sin efecto. Se abre un mercado cada vez, con informe de cobertura y de sesgo. Alemania queda fuera por ahora; Francia entra como parcial.

**Alternativas.** Exigir accesibilidad según un bróker (descartada por Enrique).

**Consecuencias.** Los resultados no dicen que un mercado sea operable desde España; los costes de transacción son supuestos etiquetados. Se retira la decisión abierta 9.1.
