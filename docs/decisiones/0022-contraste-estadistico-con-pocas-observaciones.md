# ADR 0022: Contraste estadístico con pocas observaciones independientes (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-4.

**Contexto.** Con unas 13 observaciones independientes a 365 días, el bootstrap como contraste principal (decisión previa de la evaluación) es poco fiable.

**Decisión.** Contraste principal: **submuestras no solapadas** (una fecha cada N días; t o signos sobre el IC), repetido con todos los desfases iniciales. Secundarios: HAC / Diebold-Mariano con la corrección de Harvey, Leybourne y Newbold (1997) y t de Student; bootstrap por bloques ≥ N. Además, contraste de **permutación real** (1.000 repeticiones barajando el target entre nombres dentro de cada fecha).

**Alternativas.** Bootstrap principal; HAC sin corrección.

**Consecuencias.** Menos eficiente pero honesto con T_eff cercano a 13. El detalle de HLN se verifica con el artículo antes de implementar.
