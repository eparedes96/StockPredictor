# ADR 0030: h1500 sale del entrenamiento (revierte la decisión 6b de P0) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-12.

**Contexto.** A h1500 quedan unas 2 ventanas fuera de muestra: "no evaluable" antes de empezar. La purga de unos 4,1 años elimina mucho train y obliga a adelantar el bloque reservado; el primer resultado maduro llegaría hacia 2031.

**Decisión.** `horizons.yaml = [90, 365]`. 1500 queda como **estadística descriptiva** (distribución de retornos a 1500 días, dispersión transversal, N_eff) y reactivable porque el código es paramétrico en N. Sin modelo, registro, drift ni promoción de h1500. El calendario de reserva global se dimensiona con h90 y h365.

**Alternativas.** Mantenerlo como exploratorio sin MLOps; sin cambios (6b).

**Consecuencias.** Reduce el coste de purga y de MLOps. La regla de viabilidad (ADR 0007) se aplica a cualquier horizonte que se reactive. Las menciones de 1500 en los textos pasan a ser descriptivas.
