# Decisiones y verificaciones pendientes
Actualizado el 2026-11-26 (v3). Las cerradas están en los ADR 0004 a 0030.

## Cerradas
- Accesibilidad desde España: no es filtro (ADR 0011).
- Divisa: local con EUR de diagnóstico (ADR 0012).
- `robots.txt`: no se exige (ADR 0010).

## Abiertas, con responsable
1. **Composición histórica del IBEX 35** (decisión abierta 4): hay PDF oficial de BME (137 revisiones, 1991 a 2026); falta mapear códigos a empresa y revisar cambios de código. Los precios de las salidas del índice: solo Bolsamanía en España, de calidad inferior.
2. **Tasa de impuestos del ROIC:** encaminada (efectiva TTM acotada [0%, 35%], fallback legal); falta verificar la taxonomía de CNMV y citar las tasas legales.
3. **Retraso conservador de `available_at`:** se calibra con datos reales y se fija por ADR antes de entrenar (ADR 0014).
4. **Umbrales pre-registrados** (aceptación de calidad, cobertura de P1, cobertura de índices 90 % y 80 %, train mínimo, test mínimo, paso, test final): se proponen con el informe de cobertura y se fijan antes de la primera ejecución real.
5. **Regla del `Close` real en España** con las empresas reales del universo, incluida una agrupación conocida. Si falla: `price_quality = adj_only` y valoraciones españolas apagadas.
6. **Acciones en circulación en España:** BORME es candidato sin probar; verificar en 3 a 5 empresas antes de cerrar el bloque de valoración.
7. **Composición histórica del Nasdaq-100** y muestra de 10 cierres reales por mercado: antes de abrir F2.
8. **Verificaciones técnicas** (una "semana de verificaciones", resultados en `docs/verificaciones.md`): `join_asof` de polars con el caso real; varianza con solape y bootstrap por bloques; HAC y Diebold-Mariano; PSI frente a KS; compatibilidad de polars con LightGBM y scikit-learn; pandera con tablas grandes; límite `start` de los calendarios; repetir la prueba de pandera y calendarios en el entorno de `uv.lock` (se probó con Python 3.13).
9. **Antes de F2:** hora oficial del FX del BCE, impuestos sobre transacciones y costes por mercado, términos de uso por fuente. Contacto del User-Agent de la SEC (lo da Enrique; solo en `.env`).
10. **Revisión de Enrique** de lo aceptado por el coordinador o por delegación: ADR 0005 a 0008 y 0012 a 0030. Como bloqueo antes del primer código, al menos 0019, 0021, 0024 y 0029; y revisión del análisis de potencia (0019) por una persona con experiencia en factores.
11. **Protección de ramas** (`main` y `develop`): requiere ajustes en GitHub que Enrique debe pulsar; ver `CONTRIBUTING.md`. PR 1 a 3 ya fusionados en `develop`.
12. **Horas y fechas de los go/no-go** (tras P1-0 y tras el corte vertical): las fija Enrique en el primer go/no-go (ADR 0027). Presupuesto de horas abierto.
13. **Efecto de interés 0,05:** fijado por delegación; es el extremo alto del rango 0,02 a 0,05 citado por la revisión crítica (no verificado). Revisable antes de ver el MDE de P1-0.
14. **Mercado Continuo:** cobertura de Bolsamanía fuera del IBEX y composición histórica (no verificado; Bolsamanía da 403 desde el cloud). Depende del MDE de P1-0.
15. **Benchmark con dividendos:** BME calcula el IBEX 35 con dividendos; falta probar que la serie se descarga gratis.
16. **Varias clases de acciones** (p. ej. Grifols): provisional la más líquida (mediana del valor negociado de 60 sesiones, point-in-time), la otra fuera del panel transversal. **Retenciones sobre dividendos:** sin decidir.
17. **ITF:** tasas y fechas (España 0,2 % desde 2021-01-16 con capitalización > 1.000 M€; Francia 0,4 % desde 2025-04-01) vienen de la revisión crítica; verificar con fuente oficial.
18. **Estimación de horas** de las tablas manuales (137 revisiones de BME, mapeo de códigos, `exit_events`) antes de empezar.
