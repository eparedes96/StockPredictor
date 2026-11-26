# ADR 0029: Target transversal y componente de mercado (modifica la regla 5; sustituye a P6 29a) (2026-11-26)
**Estado.** Aceptado por el coordinador por delegación de Enrique (2026-11-26); pendiente de revisión de Enrique. Antes ADR-RC-11.

**Contexto.** El RankIC por fecha no puntúa el componente de mercado, pero una pérdida cuadrática sobre el retorno absoluto gasta capacidad en él con unas 13 observaciones independientes a 365 días. Macro, FX y retorno del índice, constantes por fecha, son la vía más directa al sobreajuste.

**Decisión.** El modelo de selección se entrena con `y_cs = ln(P_salida / P_entrada) − mediana por fecha del universo elegible` (misma `price_for_returns`, mismo timing, mismo `label_end_date`). La predicción absoluta se compone: `y_abs_pred = y_cs_pred + componente de mercado`, con el componente = **media histórica expansiva** del retorno mediano del universo a N días usando solo etiquetas maduras (`label_end_date ≤ t`), evaluado aparte. Se guardan `y` (absoluto), `y_med` (mediana por fecha) e `y_cs`. **Macro, FX y retorno del índice salen del modelo transversal**; pueden alimentar solo un submodelo de mercado, que no es candidato por ahora. El exceso sobre el índice sigue como diagnóstico. `days_since_report` casi pierde sentido; la ablación se mantiene.

**Alternativas.** Mantener el absoluto quitando las features constantes por fecha; entrenar ambos como candidatos (consume trials y potencia).

**Consecuencias.** El objetivo declarado "retorno absoluto" se cumple por composición y la métrica primaria (RankIC) evalúa la parte transversal. El componente de mercado se evalúa con RMSE frente a la media expansiva, sin pretensión de poder predictivo. Es una decisión de objetivo, no solo técnica: Enrique debe revisarla. Actualiza regla 5, `configs/target.yaml` y la plantilla de informe.
