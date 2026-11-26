# ADR 0032: Composición histórica del IBEX 35 desde el PDF de BME (2026-11-26)
**Estado.** Aceptado por el coordinador (P1-0, incremento 1).

**Contexto.** El PDF oficial de BME lista 137 revisiones (1991 a 2026) solo con códigos BME que entran y salen. No trae la composición inicial, nombres ni ISIN, y el texto plano pierde la leyenda de color (revisión extraordinaria, cambio de código).

**Decisión.**
- Se lee el PDF con `pdfplumber` (extra `pdf`, también en `dev`) porque expone los rellenos de las celdas de fecha: lila = extraordinaria, naranja = cambio de código. Parser en `universe/bme_pdf.py`, sin pandas.
- Los eventos viven en `data/reference/index_membership/ibex35_events.csv` (regenerable con `python -m stockpredictor.universe.bme_pdf`). La composición inicial se infiere: una baja de un código sin alta previa implica miembro inicial (31 códigos). El PDF nunca menciona a 4 miembros de 2026 (BKT, IBE, REP, TEF); el recuento de 35 al inicio exige exactamente 4, y se añaden como iniciales con confianza baja. Fecha inicial: 1989-12-29, fecha base del índice según la ficha de BME.
- `bme_code_map.csv` mapea código y ventana de fechas a `company_id` (los códigos se reutilizan: AMS, CRI, ENC, UNI). `bme_code_changes.csv` lista los cambios de código y de clase de acciones; la composición se reproduce por `company_id`, de modo que un cambio de código no cuenta como salida. `ibex35.csv` son los intervalos derivados.
- Semántica de fechas (suposición sin verificar): alta o baja con `effective_date = d` rige desde la sesión de `d`. `announcement_date` queda vacío (el PDF no la trae).
- Lo no identificado no se inventa: `company_id = es_unresolved_<código>`, `confidence = low`, `reviewed = false`.

**Alternativas.** Extraer el texto con `pdftotext` (pierde los colores y depende de un binario); fijar el 35 como invariante (el PDF da 34 entre una baja extraordinaria y su sustitución, un 33 y un 36).

**Consecuencias.** Hasta revisar a mano, `confidence` y `reviewed` marcan qué filas son fiables; el sesgo de supervivencia sigue declarado. Los nombres de empresa son de conocimiento previo, no verificados con fuente. El PDF no se versiona (va en `data/raw`, sha256 en `data/reference/README.md`).
