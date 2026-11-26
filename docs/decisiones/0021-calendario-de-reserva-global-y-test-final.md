# ADR 0021: Calendario de reserva global y test final como control de catástrofes (matiza la regla 6) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-3.

**Contexto.** El bloque de test final de un horizonte largo lo ven los demás horizontes en walk-forward: el investigador aprende de ese periodo sin que el registro de accesos lo detecte. Con 3 años a h365, el MDE ronda 0,27 (orientativo, no medido).

**Decisión.** Un bloque de fechas de decisión **reservado para todos los horizontes** y excluido del walk-forward hasta abrir el test (`reserved_calendar`, global). El test final es **control de catástrofes, no confirmación**; así lo declara el pre-registro. `final_test_years = 3`. El estadístico reportado se deflacta por **Bonferroni sobre el número de hashes** que han tocado el test, aplicado al p-valor del RankIC con submuestras no solapadas; el método de Bailey y López de Prado no se adapta sin justificación. La purga del ADR 0008 se aplica también contra las fechas reservadas.

**Alternativas.** Bloques por horizonte (estado anterior); no deflactar.

**Consecuencias.** La confirmación real es hacia delante, con las predicciones archivadas desde el primer baseline. El calendario se dimensiona con h90 y h365 (ADR 0030).
