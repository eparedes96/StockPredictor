# Decisiones y verificaciones pendientes
Actualizado el 2026-11-26. Las cerradas están en los ADR 0004 a 0018.

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
10. **Revisión de Enrique** de lo aceptado por el coordinador: ADR 0005 a 0008 y 0012 a 0017.
11. **Protección de `main`** y merge del PR 1.
