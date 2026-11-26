# ADR 0006: Target de salidas del índice sin `adjclose` (modifica la regla 5) (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. Antes ADR-P5-2.

**Contexto.** La regla 5 fija `Adjusted Close`. Las salidas del índice con `price_quality = close_only` (p. ej. Bankia, Popular) no lo tienen. Excluirlas deja el sesgo de supervivencia en su máximo.

**Decisión.** El target usa `price_for_returns`, producido por el panel de P3: `adj_close` cuando existe; si no, `close_raw` con eventos confirmados en revisión manual (`price_for_returns_kind` ∈ {`adj_close`, `close_confirmed`}; el dataset copia el valor como `target_price_kind`). Para `close_only`: retorno de precio sin dividendos, `target_close_only = True`; con un evento sin confirmar en la ventana, el target es NaN. Toda evaluación se reporta con y sin esas filas.

**Alternativas.** Solo `adj_close` y excluir; dos targets paralelos; reintegrar dividendos (no verificado).

**Consecuencias.** Sesgo de nivel a la baja para esas empresas (sin dividendos), declarado en `docs/limitaciones.md`. La regla 5 de CLAUDE.md queda actualizada en este mismo PR.
