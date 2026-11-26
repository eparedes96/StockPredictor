# Informe P1-0: potencia del IBEX solo con precios
**Resultados con sesgo de supervivencia (sin deslistadas).** Precios: Yahoo `adj_close`, instantánea `2026-11-26` (sha256 `d7e2fb40aee2…`). Datos desde 2000-01-03 hasta 2026-11-26. Commit: `f7c73d1f36f577b6d5fcddecbceca5a001fe9795`. Generado con `stockpredictor report-p1-0` (parámetros, versiones y semilla en `run.json`).

## 1. Resultado por horizonte
Efecto de interés: RankIC medio de 0,05 (ADR 0019). Train mínimo principal: 8 años. MDE con α = 0,05 bilateral y potencia 0,80, t de Student no central; cifra titular = mediana de los tres baselines. La etiqueta es "detectable" si MDE ≤ efecto y "no concluyente por diseño" si no.

| Horizonte | N_eff | Viabilidad (ADR 0007) | MDE titular | MDE por baseline | N necesarias p/ 0,05 | Etiqueta (ADR 0019) |
|---|---|---|---|---|---|---|
| h90 | 62 | viable | 0,116 | 0,091 a 0,128 | 322 | **no concluyente por diseño** |
| h365 | 13 | viable | 0,258 | 0,234 a 0,283 | 304 | **no concluyente por diseño** |

N_eff = ventanas disjuntas de etiqueta fuera de muestra (mediana entre desfases), tras el train mínimo, la purga, el embargo de 5 sesiones y el bloque reservado de 3 años (ADR 0008, 0021). "N necesarias" = observaciones independientes que harían falta para detectar 0,05 con la σ medida (aproximación normal).

## 2. N_eff y ventanas evaluables
Sensibilidad al train mínimo. Con bloque reservado = cifra de decisión; sin él = solo informativa (no se calcula ningún retorno con ese bloque). `Ventanas (tramo/N)` es la cota ideal sin rejilla de fechas. h1500 es descriptivo (ADR 0030).

| Horizonte | Train (años) | Reserva | Primera fecha OOS | Última etiqueta | Fechas | N_eff (mín-máx) | Ventanas (tramo/N) | Viabilidad |
|---|---|---|---|---|---|---|---|---|
| h90 | 5 | sí | 2005-04-15 | 2023-11-17 | 958 | 74 (73-74) | 75 | viable |
| h90 | 8 | sí | 2008-04-11 | 2023-11-17 | 802 | 62 (61-62) | 63 | viable |
| h90 | 10 | sí | 2010-04-16 | 2023-11-17 | 697 | 54 (53-54) | 55 | viable |
| h90 | 5 | no | 2005-04-15 | 2026-11-20 | 1115 | 86 (85-86) | 87 | viable |
| h90 | 8 | no | 2008-04-11 | 2026-11-20 | 959 | 74 (73-74) | 75 | viable |
| h90 | 10 | no | 2010-04-16 | 2026-11-20 | 854 | 66 (65-66) | 67 | viable |
| h365 | 5 | sí | 2006-01-31 | 2023-11-01 | 202 | 16 (16-17) | 17 | viable |
| h365 | 8 | sí | 2009-01-30 | 2023-11-01 | 166 | 13 (13-14) | 14 | viable |
| h365 | 10 | sí | 2011-01-31 | 2023-11-01 | 142 | 12 (11-12) | 12 | viable |
| h365 | 5 | no | 2006-01-31 | 2026-11-03 | 238 | 19 (19-20) | 20 | viable |
| h365 | 8 | no | 2009-01-30 | 2026-11-03 | 202 | 16 (16-17) | 17 | viable |
| h365 | 10 | no | 2011-01-31 | 2026-11-03 | 178 | 15 (14-15) | 15 | viable |
| h1500 (desc.) | 5 | sí | 2009-02-27 | 2023-11-09 | 128 | 3 (2-3) | 3 | no evaluable con rigor |
| h1500 (desc.) | 8 | sí | 2012-02-29 | 2023-11-09 | 92 | 2 (1-2) | 2 | no evaluable con rigor |
| h1500 (desc.) | 10 | sí | 2014-02-28 | 2023-11-09 | 68 | 1 (1-2) | 2 | no evaluable con rigor |
| h1500 (desc.) | 5 | no | 2009-02-27 | 2026-11-11 | 164 | 3 (3-4) | 4 | no evaluable con rigor |
| h1500 (desc.) | 8 | no | 2012-02-29 | 2026-11-11 | 128 | 3 (2-3) | 3 | no evaluable con rigor |
| h1500 (desc.) | 10 | no | 2014-02-28 | 2026-11-11 | 104 | 2 (2-3) | 3 | no evaluable con rigor |

## 3. RankIC, error típico y MDE por baseline (train 8 años)
Spearman por fecha entre la señal y `y_cs`. Error típico = media entre desfases del error típico de la media en submuestras de etiquetas disjuntas (ADR 0022). σ = desviación típica del RankIC entre fechas de la submuestra. `t medio` y `% |t|>1,96` son sobre las submuestras (una por desfase). Señales: momentum 12-1 (ln P[t-21] − ln P[t-252]), baja volatilidad 60 (−σ de retornos diarios de 60 sesiones, mínimo 48) y reversión a 1 mes (−ln P[t]/P[t-21]). Son diagnósticos de potencia: no hay ajuste ni se presentan como evidencia de señal (tres señales y dos horizontes sin corrección por comparaciones múltiples).

| H | Señal | Fechas | n sub. | RankIC medio (todas) | RankIC medio (sub.) | Rango entre desfases | σ | Error típico | t medio | % |t|>1,96 | MDE (t) | MDE (normal) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h90 | low_vol_60 | 802 | 62 | 0,0293 | 0,0303 | 0,018 a 0,047 | 0,353 | 0,0449 | 0,67 | 0 | 0,128 | 0,125 |
| h90 | momentum_12_1 | 802 | 62 | 0,0118 | 0,0133 | -0,004 a 0,035 | 0,320 | 0,0408 | 0,33 | 0 | 0,116 | 0,114 |
| h90 | reversal_1m | 802 | 62 | -0,0243 | -0,0236 | -0,081 a 0,028 | 0,252 | 0,0321 | -0,69 | 15 | 0,091 | 0,090 |
| h365 | low_vol_60 | 166 | 13 | 0,0441 | 0,0484 | -0,010 a 0,108 | 0,341 | 0,0929 | 0,59 | 0 | 0,283 | 0,265 |
| h365 | momentum_12_1 | 166 | 13 | -0,0219 | -0,0151 | -0,059 a 0,044 | 0,311 | 0,0847 | -0,19 | 0 | 0,258 | 0,242 |
| h365 | reversal_1m | 166 | 13 | -0,0246 | -0,0091 | -0,079 a 0,045 | 0,283 | 0,0770 | -0,15 | 0 | 0,234 | 0,220 |

## 4. Sensibilidad del MDE al train mínimo

| H | Train (años) | n sub. (mediana) | σ (mediana) | MDE titular | MDE mín | MDE máx |
|---|---|---|---|---|---|---|
| h90 | 5 | 74 | 0,314 | 0,104 | 0,082 | 0,111 |
| h90 | 8 | 62 | 0,320 | 0,116 | 0,091 | 0,128 |
| h90 | 10 | 54 | 0,322 | 0,125 | 0,098 | 0,136 |
| h365 | 5 | 16 | 0,301 | 0,222 | 0,202 | 0,249 |
| h365 | 8 | 13 | 0,311 | 0,258 | 0,234 | 0,283 |
| h365 | 10 | 12 | 0,316 | 0,286 | 0,263 | 0,311 |

## 5. Permutación (1000 repeticiones, semilla 20261126, train 8 años)
Se baraja `y_cs` entre nombres dentro de cada fecha: contrasta la nula fuerte (ninguna relación señal-retorno en ninguna fecha). `p (todas)`: media sobre todas las fechas de la rejilla; barajar por fecha rompe la dependencia entre etiquetas solapadas, así que subestima la varianza real y su p-valor es liberal. `p (sub., mediana)`: p-valor de la media de cada submuestra disjunta, mediana entre desfases. Aun así la permutación es liberal si el RankIC varía en el tiempo con media cero: `σ nula` es la desviación del RankIC por fecha que daría el azar y `σ empírica` la medida (sección 3). La σ empírica es mayor porque el RankIC de estas señales cambia de signo con el régimen; el contraste principal y el MDE titular usan la empírica (ADR 0022). `MDE (σ nula)` es el MDE optimista que saldría de suponer solo ruido de muestreo; no sirve para etiquetar.

| H | Señal | RankIC obs. (todas) | σ nula (todas) | p (todas) | σ nula media (sub.) | p (sub., mediana) | p (sub., mín) | σ nula | σ empírica | MDE (σ nula) |
|---|---|---|---|---|---|---|---|---|---|---|
| h90 | low_vol_60 | 0,0293 | 0,0069 | 0,001 | 0,0242 | 0,226 | 0,058 | 0,190 | 0,353 | 0,069 |
| h90 | momentum_12_1 | 0,0118 | 0,0070 | 0,088 | 0,0242 | 0,684 | 0,152 | 0,190 | 0,320 | 0,069 |
| h90 | reversal_1m | -0,0243 | 0,0069 | 0,001 | 0,0244 | 0,241 | 0,001 | 0,192 | 0,252 | 0,069 |
| h365 | low_vol_60 | 0,0441 | 0,0142 | 0,003 | 0,0521 | 0,317 | 0,051 | 0,188 | 0,341 | 0,159 |
| h365 | momentum_12_1 | -0,0219 | 0,0147 | 0,135 | 0,0514 | 0,736 | 0,252 | 0,185 | 0,311 | 0,157 |
| h365 | reversal_1m | -0,0246 | 0,0146 | 0,085 | 0,0526 | 0,606 | 0,139 | 0,190 | 0,283 | 0,161 |

## 6. Correlación transversal de los targets (train 8 años)
Correlación media por pares entre nombres sobre fechas no solapadas (≥ 10 fechas en común), media entre desfases. Con `y_cs` la media está sesgada a −1/(N−1) por construcción (se resta la mediana), así que solo `y` tiene Deff interpretable: con ρ ≈ 0,4 el retorno absoluto de ~29 nombres equivale a pocos nombres independientes, el motivo del target transversal (ADR 0029). `Deff = 1 + (N−1)ρ`; nombres equivalentes = N/Deff.

| H | Target | ρ medio | Nombres por fecha | Deff | Nombres equiv. |
|---|---|---|---|---|---|
| h90 | y | 0,410 | 29,3 | 12,58 | 2,3 |
| h90 | y_cs | -0,019 | 29,3 | 0,46 | - |
| h365 | y | 0,389 | 29,1 | 11,92 | 2,4 |
| h365 | y_cs | -0,017 | 29,1 | 0,53 | - |

## 7. Cobertura de miembros con target válido (fechas de decisión por año)

| Año | Fechas | Miembros (media) | Con target válido | % con target |
|---|---|---|---|---|
| 2000 | 52 | 35,0 | 11,0 | 31 |
| 2001 | 52 | 35,0 | 14,9 | 43 |
| 2002 | 52 | 35,0 | 17,3 | 49 |
| 2003 | 52 | 34,9 | 18,6 | 53 |
| 2004 | 53 | 35,0 | 20,0 | 57 |
| 2005 | 52 | 35,0 | 20,5 | 59 |
| 2006 | 52 | 34,9 | 20,4 | 59 |
| 2007 | 52 | 35,0 | 20,8 | 59 |
| 2008 | 52 | 34,9 | 23,4 | 67 |
| 2009 | 53 | 34,9 | 24,7 | 71 |
| 2010 | 52 | 35,0 | 26,0 | 74 |
| 2011 | 52 | 34,6 | 27,8 | 80 |
| 2012 | 52 | 35,3 | 27,8 | 79 |
| 2013 | 52 | 34,7 | 28,8 | 83 |
| 2014 | 52 | 35,0 | 26,9 | 77 |
| 2015 | 53 | 34,8 | 27,3 | 78 |
| 2016 | 52 | 34,9 | 29,4 | 84 |
| 2017 | 52 | 35,0 | 29,8 | 85 |
| 2018 | 52 | 34,9 | 31,0 | 89 |
| 2019 | 52 | 35,0 | 31,5 | 90 |
| 2020 | 53 | 34,9 | 31,7 | 91 |
| 2021 | 52 | 35,0 | 33,8 | 96 |
| 2022 | 52 | 35,0 | 34,0 | 97 |
| 2023 | 52 | 35,0 | 35,0 | 100 |
| 2024 | 52 | 35,0 | 35,0 | 100 |
| 2025 | 52 | 35,0 | 35,0 | 100 |
| 2026 | 34 | 35,0 | 35,0 | 100 |

(Cobertura de h90; las demás en `cobertura_por_anio.csv`.) Miembros sin target: sin ticker en Yahoo (34 de 83 tickers dan 404, en su mayoría empresas ya desaparecidas) o sin precio en t, entrada o salida.

## 8. Lectura y limitaciones
- Todo es con sesgo de supervivencia (sin deslistadas): las empresas que salieron del IBEX y Yahoo no cotiza no entran. Eso reduce los nombres por fecha, puede sesgar el nivel del RankIC (más en momentum y reversión) y no se corrige con este informe; Bolsamanía se integrará después.
- El MDE usa la σ del RankIC medida en las fechas fuera de muestra con estos tres baselines. Un modelo con otra σ tendría otro MDE; es una cifra de diseño, no una garantía.
- El bloque final reservado (ADR 0021) no entra en ninguna cifra de retornos.
- `adj_close` de Yahoo incorpora dividendos y splits tal como están hoy; el ruido de redondeo entre descargas llega a 1,9e-6 (ADR 0033). Sesión faltante global: Yahoo no trae 2018-09-20 (`docs/limitaciones.md`).
- Calendario de sesiones = unión de fechas con precio de alguna empresa; N en días naturales, entrada al cierre de t+1, salida en la última sesión ≤ entrada + N (ADR 0005).
- Fechas de decisión: última sesión de cada semana ISO (h90) o mes (h365) (ADR 0026).
- Una persona con experiencia en factores debería revisar el análisis de potencia (ADR 0019).
