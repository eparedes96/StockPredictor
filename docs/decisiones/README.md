# Registro de decisiones (ADR)
Un archivo por decisión, `NNNN-slug.md`, con contexto, decisión, alternativas y consecuencias. La numeración es correlativa por orden de creación, no por fase. El repositorio es la fuente de verdad.

**Estados.** "Aceptado por Enrique" o "Aceptado por el coordinador; pendiente de revisión de Enrique". Enrique puede revisar o revertir cualquiera; los que modifican reglas de `CLAUDE.md` son 0006, 0007, 0008, 0009, 0010, 0013, 0021, 0024 y 0029. Se recomienda que Enrique lea al menos 0019, 0021, 0024 y 0029 antes del primer código; una persona con experiencia en factores debería revisar el análisis de potencia (0019).

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
| 0014 | Parámetros estructurales calibrados con toda la muestra (integrado en 0020) | Coordinador | C15 |
| 0015 | `runs/` y `experiments/`, registro de modelos, CLI, pandas aislado | Coordinador | C2, C6, C7, C14 |
| 0016 | Orden de etapas y quién normaliza | Coordinador | C16 |
| 0017 | Glosario en inglés y marca de datos de prueba | Coordinador | C4, C5, C19 |
| 0018 | Retención de `raw` | Enrique | P0 11a |
| 0019 | Etiqueta de resultado por MDE; efecto de interés 0,05 | Coordinador (delegado) | ADR-RC-1 |
| 0020 | Cantidades pre-registradas (integra 0014) | Coordinador (delegado) | ADR-RC-2 |
| 0021 | Calendario de reserva global y test final como control de catástrofes (regla 6) | Coordinador (delegado) | ADR-RC-3 |
| 0022 | Contraste estadístico con pocas observaciones | Coordinador (delegado) | ADR-RC-4 |
| 0023 | Baselines en dos familias | Coordinador (delegado) | ADR-RC-5 |
| 0024 | Normalización por rango por defecto (regla 7) | Coordinador (delegado) | ADR-RC-6 |
| 0025 | `is_financial` explícito | Coordinador (delegado) | ADR-RC-7 |
| 0026 | Muestreo de fechas de decisión | Coordinador (delegado) | ADR-RC-8 |
| 0027 | Alcance y orden: P1-0, corte vertical, go/no-go | Coordinador (delegado) | ADR-RC-9 |
| 0028 | Costes con ITF por época | Coordinador (delegado) | ADR-RC-10 |
| 0029 | Target transversal y componente de mercado (regla 5) | Coordinador (delegado) | ADR-RC-11 |
| 0030 | h1500 sale del entrenamiento (revierte 6b) | Coordinador (delegado) | ADR-RC-12 |
| 0031 | Flujo de ramas: `main`, `develop` y ramas cortas | Enrique | 2026-11-26 |

## ADR prometidos por la planificación, aún sin escribir
Se numeran al crearlos, con el siguiente número libre (0032 en adelante), y antes de implementar lo que afectan.
- **Datos (P1, P2):** proveedores de precios y fundamentales; librería de contratos (pandera sobre polars) probada con `uv.lock` y 3.12; calendarios; prueba de scrip y test de regresión de Yahoo entre instantáneas.
- **Transformación (P3):** retraso conservador calibrado (el valor, no el criterio); sesión de validez.
- **Features (P4):** ventana finita de EMA/RSI/MACD; P/E calculado sobre market cap en lugar de `Close / EPS`.
- **Pre-registro (P5, P6):** firma de `configs/preregistered.yaml` (ADR 0020), lista del modelo de control, umbrales de coste y liquidez. Antes de la primera ejecución con datos reales.
- **MLOps (P7a):** formato de serialización, registro, `available_at` en producción, evaluación de predicciones maduras, regla de promoción (pre-registrada antes de la primera promoción). P7b queda aplazado.
- **Mercados (P8):** pertenencia múltiple, cobertura de índices, evaluación de F2, retención.
- **Abiertos sin decidir:** varias clases de acciones (decisión provisional de la más líquida, ver `convenciones.md`), retenciones sobre dividendos, horas y fechas de los go/no-go.
