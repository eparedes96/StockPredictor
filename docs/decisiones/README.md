# Registro de decisiones (ADR)
Un archivo por decisión, `NNNN-slug.md`, con contexto, decisión, alternativas y consecuencias. La numeración es correlativa por orden de creación, no por fase. El repositorio es la fuente de verdad.

**Estados.** "Aceptado por Enrique" o "Aceptado por el coordinador; pendiente de revisión de Enrique". Enrique puede revisar o revertir cualquiera; los que modifican reglas de `CLAUDE.md` son 0006, 0008, 0009, 0010, 0013 y 0014 (más 0007, que añade la regla de viabilidad).

| Nº | Decisión | Estado | Origen |
|---|---|---|---|
| 0001 | Ajuste de la estructura base | Aceptado | |
| 0002 | Promedio de balances (trimestral) | **Sustituido por 0004** | |
| 0003 | Entorno y empaquetado (uv, CLI, extras) | Aceptado | PR 1 |
| 0004 | Balance semestral (3 puntos) | Enrique | P3 18a |
| 0005 | N en días naturales | Coordinador | ADR-P5-1 |
| 0006 | Target sin `adjclose` (regla 5) | Coordinador | ADR-P5-2 |
| 0007 | Regla de viabilidad por horizonte | Coordinador | ADR-P5-3 |
| 0008 | Purga y embargo (regla 6) | Coordinador | ADR-P5-4 |
| 0009 | Regla 2: versión conocida en cada fecha | Enrique | P3 12a |
| 0010 | Scraping sin `robots.txt` | Enrique | P1 28b |
| 0011 | Accesibilidad desde España no es filtro | Enrique | P8 3a |
| 0012 | Divisa local con EUR de diagnóstico | Coordinador | P5 6a, P8 5a |
| 0013 | Valoraciones apagadas sin `Close` real | Coordinador | C3 |
| 0014 | Parámetros estructurales calibrados con toda la muestra | Coordinador | C15 |
| 0015 | `runs/` y `experiments/`, registro de modelos, CLI, pandas aislado | Coordinador | C2, C6, C7, C14 |
| 0016 | Orden de etapas y quién normaliza | Coordinador | C16 |
| 0017 | Glosario en inglés y marca de datos de prueba | Coordinador | C4, C5, C19 |
| 0018 | Retención de `raw` | Enrique | P0 11a |

## ADR prometidos por la planificación, aún sin escribir
Se numeran al crearlos, con el siguiente número libre, y antes de implementar lo que afectan.
- **Datos (P1, P2):** proveedores de precios y fundamentales; librería de contratos (pandera sobre polars) probada con tablas grandes, `Decimal` y `LazyFrame`; calendarios.
- **Transformación (P3):** disponibilidad y retraso conservador calibrado (el valor, no el criterio); sesión de validez.
- **Features (P4):** ventana finita de EMA/RSI/MACD; P/E calculado sobre market cap en lugar de `Close / EPS`.
- **Pre-registro (P5, P6):** umbrales de calidad y de cobertura, train mínimo, test mínimo, paso, test final, lista del modelo de control, umbrales de coste y liquidez. Debe firmarse antes de la primera ejecución con datos reales.
- **MLOps (P7):** formato de serialización, registro, `available_at` en producción, evaluación de predicciones maduras, disparadores, reentrenamiento (refresco frente a candidato nuevo), test del challenger y regla de promoción (esta, pre-registrada antes de la primera promoción).
- **Mercados (P8):** divisa y FX, pertenencia múltiple, cobertura de índices, evaluación de F2, retención.
