# ADR 0019: Etiqueta de resultado según el MDE (corrige la regla de P0 5a) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-1.

**Contexto.** Con unas 35 empresas, el MDE probable del RankIC va de unos 0,066 (h90) a unos 0,13 (h365) con fundamentales. Es aritmética orientativa de la revisión crítica, no medida. Un resultado nulo con MDE alto no prueba que no haya señal.

**Decisión.** El **efecto de interés** es un **RankIC medio de 0,05**. Cada resultado lleva una de tres etiquetas: "señal detectada"; "sin señal con potencia suficiente" (MDE ≤ 0,05); "no concluyente" (MDE > 0,05). "No concluyente" no justifica parar ni reformular. Con 0,05, si el MDE del IBEX a h90 es > 0,05 y el Mercado Continuo no lo baja a ≤ 0,05, el IBEX pasa a **universo de validación técnica** (ADR 0027). El mismo criterio vale a h365: con MDE > 0,05 el horizonte queda "no concluyente por diseño" y solo se reporta. Reserva: 0,05 es el extremo alto del rango 0,02 a 0,05 que cita la revisión crítica (no verificado).

**Alternativas.** Mantener "sin señal detectable" sin referencia al MDE.

**Consecuencias.** El MDE se calcula con datos reales en P1-0 y se actualiza al entrenar. Se aplica junto a la regla de viabilidad del ADR 0007: ambas etiquetas se reportan y la del MDE manda en la etiqueta final. Una persona con experiencia en factores debería revisar el análisis de potencia.
