# ADR 0007: Regla de viabilidad por horizonte (2026-11-26)
**Estado.** Aceptado por el coordinador (2026-11-26); pendiente de revisión de Enrique. Antes ADR-P5-3, revisada a propuesta de la evaluación (P6). Umbrales **provisionales**.

**Contexto.** Con pocos años de historia, los N largos tienen pocas ventanas independientes. Contar ventanas del periodo entero sobreestima lo evaluable, porque en walk-forward hace falta un train mínimo y una purga ≥ N antes del primer test. Aritmética ilustrativa, no medida: con unos 21 años de fundamentales, un train mínimo hipotético de 8 y N=1500 días naturales, quedan unas 2 ventanas fuera de muestra frente a unas 5 del periodo entero.

**Decisión.** Los umbrales se aplican a las **ventanas disjuntas de longitud N fuera de muestra evaluables**, es decir, tras el train mínimo y la purga: **≥10 viable, 4 a 9 exploratorio** (sin afirmación de poder predictivo), **<4 no evaluable con rigor**. Las ventanas del periodo entero se reportan como dato informativo. El N_corte y la autocorrelación de features se reportan pero no entran en la regla. Los umbrales solo se revisan con justificación escrita y nunca tras mirar métricas del modelo. Los tres horizontes se construyen y entrenan igualmente, etiquetados.

**Alternativas.** Contar ventanas del periodo entero (versión inicial); fijar el umbral tras ver la tabla; solo reportar.

**Consecuencias.** El resultado depende del train mínimo, que se propone tras P5a y se fija antes de la primera ejecución real (`configs/validation.yaml`). La evaluación aplica la regla y etiqueta cada resultado. Expectativa a asumir desde ya: N=1500 probablemente quedará exploratorio o no evaluable; los horizontes serios serán 90 y 365.
