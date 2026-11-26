# ADR 0008: Purga y embargo (modifica la regla 6) (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. Antes ADR-P5-4.

**Contexto.** "Embargo y purga ≥ N" era ambiguo. En walk-forward solo hacia delante, lo que protege de la fuga por solape de targets es la purga por fin de target.

**Decisión.** Invariante: `max(label_end_date de train) < inicio del test − embargo`, con un embargo extra provisional de 5 sesiones (`embargo_sessions`). `embargo_days: horizon` de `validation.yaml` desaparece; la purga cubre ≥ N días por construcción.

**Alternativas.** Solo purga; embargo de 2N.

**Consecuencias.** Test de invariante en `tests/leakage/`. El valor del embargo se revisa con evidencia de autocorrelación de features. El calendario de reserva global (ADR 0021) excluye también las fechas reservadas del walk-forward de todos los horizontes. La regla 6 de CLAUDE.md queda reescrita en este PR.
