# ADR 0020: Cantidades pre-registradas (integra al ADR 0014) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-2.

**Contexto.** Hay cuatro "10" provisionales con significados distintos (`n_min` de normalización, mínimo de empresas por fecha del dataset, `min_names_per_date` del RankIC, umbral de viabilidad), más embargo, train mínimo, test final y cobertura. El ADR 0014 acotaba los parámetros calibrados con toda la muestra.

**Decisión.** Un solo ADR, y un solo archivo `configs/preregistered.yaml`, con nombre propio y valor para cada cantidad, firmado antes del pre-registro. Incluye `effect_of_interest_rankic = 0,05` y `final_test_years = 3`. Las cantidades calibradas con datos usan **solo datos anteriores al bloque reservado** (ADR 0021). Integra el contenido del ADR 0014, que queda como antecedente.

**Alternativas.** Dejar cada cantidad en el archivo de su dominio (nombres repetidos y valores dispersos).

**Consecuencias.** Requisito previo del pre-registro. Mientras no se firme, los valores de `preregistered.yaml` son provisionales y están marcados así. Cambiarlos requiere justificación escrita y nunca después de mirar métricas del modelo.
