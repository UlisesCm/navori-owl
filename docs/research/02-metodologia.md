# 02 — Metodología: cómo evaluar un harness (y no solo el modelo)

> Fecha de corte: 2026-09-23. Síntesis neutral de `navori-evals/docs/research/02-harness-eval-methodology.md`,
> ampliada para **N variantes**. Fuentes primarias con URL; **UNVERIFIED** = no confirmado.

---

## 1. El harness importa tanto como el modelo

| Fuente | Hallazgo | URL |
|---|---|---|
| **Harness-Bench** (may-2026) | 106 tareas × 6 harnesses × 8 modelos. Con el **mismo modelo**, el éxito va de 52.4% a 76.2% (23.8 pp) y los tokens por tarea de 5K a 175K. Tesis: reportar capacidad por configuración modelo+harness, no por modelo | https://arxiv.org/abs/2605.27922 |
| **The Scaffold Effect** (jun-2026) | 3 harnesses (Goose, OpenCode, OpenHands): hasta **40x** de diferencia en tokens por tarea resuelta, pero solo 0–8 pp en éxito. Recomienda comparar éxito *dentro de un presupuesto* | https://arxiv.org/abs/2607.22585 |
| **SWE-agent** (2024) | Ablación clásica: quitar un componente a la vez (linter, editor, ventana de contexto) mueve el éxito de 18.0% a 10.3–15.0% | https://arxiv.org/abs/2405.15793 |
| **Agentless** (2024) | Un pipeline fijo simple le ganó a agentes complejos (32% en Lite, ~$0.70) → siempre comparar contra un baseline simple | https://arxiv.org/abs/2407.01489 |
| **Anthropic** | "When we evaluate 'an agent,' we're evaluating the harness *and* the model working together." | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents |
| **HAL** (2025) | 21,730 rollouts: los scaffolds cambian precisión y costo pero casi nunca se comparan. Más reasoning effort a menudo *bajó* la precisión. Agentes que buscaron el benchmark en HuggingFace en vez de resolverlo | https://arxiv.org/abs/2510.11977 |
| **AI Agents That Matter** (2024) | Optimizar solo precisión produce agentes caros e innecesariamente complejos → **frontera de Pareto precisión/costo** | https://arxiv.org/abs/2407.01502 |

**Evidencia específica sobre archivos de contexto y skills** (la mayoría de los harnesses de Claude Code son eso):
- **Evaluating AGENTS.md** (ETH, 2026): los archivos de contexto *no* suben la tasa de éxito y el costo sube más de 20%. Las instrucciones concretas sí se siguen. https://arxiv.org/abs/2602.11988
- **Do Context Files Help Coding Agents?** (Khatri, 2026): Claude Code y Codex, 17 tareas, 288 corridas. El efecto sobre la correctitud quedó acotado a ≤10–15 pp por *equivalence testing*. Es casi el diseño de owl, a escala pequeña. https://arxiv.org/abs/2607.27250
- **SkillsBench**: skills curados dan +16.6 pp en promedio, pero solo +4.5 pp en SWE. https://arxiv.org/abs/2602.12670 · **SWE-Skills-Bench**: 39 de 49 skills dan 0 mejora y 3 restan. https://arxiv.org/abs/2603.15401

**Multi-agente** (varios harnesses usan orquestador y subagentes):
- En tareas secuenciales, todas las variantes multi-agente pierden entre 39% y 70%; en tareas paralelizables ganan hasta +80.8%. https://arxiv.org/abs/2512.08296
- Con igual presupuesto de tokens, un solo agente iguala o supera a los multi-agente. https://arxiv.org/abs/2604.02460
- Anthropic: en su sistema de research, el uso de tokens explica el 80% de la varianza. https://www.anthropic.com/engineering/multi-agent-research-system
- MAST: 14 modos de falla en sistemas multi-agente; "the presence of a verifier is not a silver bullet". https://arxiv.org/abs/2503.13657

**Consecuencia para owl:** si un harness gana, hay que preguntar si ganó porque *gastó más*. El costo se reporta siempre al lado del éxito.

## 2. Métricas

- **pass@k:** probabilidad de al menos un éxito en k intentos. **pass^k:** probabilidad de que los k intentos salgan bien, es decir, consistencia. Con 75% por intento, pass^3 ≈ 42%. Para uso diario importa más pass^k. https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents · τ-bench https://arxiv.org/abs/2406.12045
- Estimadores con n corridas y c éxitos: pass@k = `1 − C(n−c,k)/C(n,k)` (Chen et al. 2021, https://arxiv.org/abs/2107.03374); pass^k = `C(c,k)/C(n,k)` (derivación estándar, UNVERIFIED como cita).
- **Confiabilidad** como dimensión aparte: 12 métricas en 4 ejes (consistencia, robustez, predictibilidad, seguridad). https://arxiv.org/abs/2602.16666
- **Co-métricas continuas** (tokens, $, turnos, tiempo): detectan diferencias con muchas menos corridas que el éxito binario (§4).

## 3. Estadística con pocas tareas

- Tratar los evals como experimentos: errores estándar, diferencias pareadas y análisis de potencia antes de correr (Miller, Anthropic). https://arxiv.org/abs/2411.00640
- **No usar aproximación normal/CLT con menos de unos cientos de datos:** usar Wilson/Clopper-Pearson, métodos bayesianos o comparaciones pareadas. https://arxiv.org/abs/2503.01747
- METR: 8 corridas por par y **bootstrap jerárquico** (familias → tareas → corridas). https://arxiv.org/html/2503.14499
- Las tareas con 30–70% de éxito histórico son las que discriminan; las que salen siempre 0/5 o 5/5 no aportan. https://arxiv.org/abs/2603.23749

**La unidad de análisis es la tarea, no la corrida:** las corridas de una misma tarea están correlacionadas. Para cada tarea `i` y cada par de variantes (A, B): `d_i = p̂_i(B) − p̂_i(A)`. Tests válidos con n chico:
1. **Sign-flip permutation** sobre `d_i`: exacto y sin supuestos.
2. **Wilcoxon signed-rank:** cuidado con los empates.
3. **Bootstrap jerárquico** para el intervalo de confianza.
4. **GLMM** `éxito ~ variante + (1|tarea)` (práctica estándar; puede no converger con pocas tareas).

**Con N variantes** (lo nuevo en owl):
- Hacer todas las comparaciones de a pares contra el baseline, o todas contra todas, y **corregir por comparaciones múltiples (Holm)**.
- Declarar **una sola métrica primaria** en el pre-registro.
- Para el costo: `log(costo_B / costo_A)` por tarea, con test pareado.
- "No significativo" **no** quiere decir "no hay efecto": reportar el intervalo de confianza, o usar **TOST** con un margen pre-registrado para afirmar equivalencia (como Khatri).

## 4. Potencia: cuántas tareas y corridas hacen falta

Simulación propia (`power.py`): dificultad Beta(2,2), efecto constante en escala logit, sign-flip con α=0.05 y 400 simulaciones. **Es una estimación, no una fuente.**

| Tareas × corridas | +10 pp | +19 pp | +27 pp |
|---|---|---|---|
| 8 × 3 | 0.03 | 0.07 | 0.23 |
| 8 × 5 | 0.04 | 0.23 | 0.49 |
| 12 × 5 | 0.12 | 0.48 | 0.84 |
| 15 × 5 | 0.20 | 0.59 | 0.93 |

Lectura:
- Con 8 tareas, el éxito binario no puede probar casi nada.
- Más tareas rinden más que más corridas.
- Un efecto de +10 pp es indetectable con presupuestos pequeños, lo que coincide con Khatri.
- Las co-métricas continuas sí detectan diferencias con 8–15 tareas. En costo, los efectos entre harnesses son grandes: +20% en el paper de AGENTS.md, hasta 40x en The Scaffold Effect.

## 5. Proceso vs resultado

- Evaluar el **estado final**, porque el agente puede llegar por caminos válidos distintos (Anthropic).
- Aun así, **leer los transcripts:** "You won't know if your graders are working well unless you read the transcripts" (Anthropic).
- TraceProbe: mismo resultado, procesos muy distintos. Propone una taxonomía de acciones y anti-patrones (search loops, verification skips). https://arxiv.org/abs/2607.06184
- OpenAI divide los checks en outcome, process, style y efficiency, y parsea el JSONL de `codex exec --json`. https://developers.openai.com/blog/eval-skills
- **Regla:** el resultado decide y el proceso explica. Nunca premiar "usó su reviewer" como si fuera éxito.

## 6. Juez LLM

- Sesgos documentados: posición, verbosidad y **auto-preferencia**. https://arxiv.org/abs/2306.05685
- Anthropic: graders deterministas primero, LLM solo donde haga falta flexibilidad, validado con humanos.
- **Reglas para owl:**
  - El juez es un modelo distinto al evaluado.
  - El orden de los pares es aleatorio.
  - El juez es **ciego a la variante**: se borran rastros como `.claude/`, nombres de agentes o archivos propios de cada harness.
  - Se calibra contra 10–20 juicios humanos.

## 7. Fuga del grader y reward hacking

- **Historial de git:** Claude 4 Sonnet, Qwen3-Coder y GLM 4.5 usaron `git log --all` y `reflog` para encontrar el fix. https://github.com/SWE-bench/SWE-bench/issues/465
- **METR:** los modelos editan tests o el scoring. 30.4% de hacking cuando la función de scoring es visible, 0.7% cuando no. https://metr.org/blog/2025-06-05-recent-reward-hacking/
- **ImpossibleBench:** tareas donde spec y tests se contradicen, así que cualquier pass es trampa. Los modelos más fuertes hacen más trampa; **ocultar los tests la baja casi a 0**. El contexto (prompt, harness) cambia la propensión: **un harness puede subir o bajar la tasa de trampa, y eso también se mide.** https://arxiv.org/abs/2510.20270

## 8. Ruido de infraestructura

- Anthropic: en Terminal-Bench 2.0, la configuración de recursos mueve el score **6 pp**. "Leaderboard differences below 3 percentage points deserve skepticism until the eval configuration is documented and matched." https://www.anthropic.com/engineering/infrastructure-noise
- Entorno limpio por corrida: el estado compartido causa fallas correlacionadas.

## 9. Diseño recomendado (resumen)

1. **Pre-registro** antes de correr: tareas, métrica primaria, test, α, efecto mínimo relevante, criterios de exclusión y versiones fijadas (CLI, modelo, harness).
2. **12–15 tareas mejor que 8**, de dificultad media, con grader oculto y determinista. Un piloto de 1 corrida por tarea sirve para calibrar.
3. **Mismo modelo, mismo esfuerzo, mismos límites** (turnos, timeout, presupuesto) y mismos recursos en todas las variantes.
4. **5 corridas por tarea y variante, intercaladas** (no todo A y luego todo B), para que el drift de la API no se confunda con el efecto.
5. **Aislamiento total:** ninguna variante hereda config del usuario (ver doc 05).
6. **Reportar:** tabla por tarea, diferencias pareadas con intervalo de confianza, costo por éxito, frontera de Pareto, tasa de hacking y errores de infraestructura por separado.

## 10. Trampas (checklist)

1. Contaminar el baseline con config del usuario (`~/.claude`, memoria, MCPs, plugins).
2. Presupuestos desiguales: "ganó porque gastó más".
3. Pseudo-replicación: tratar las corridas como independientes.
4. t-test o CLT sobre unos pocos puntos binarios.
5. Tests visibles o historial de git con la solución.
6. Reward hacking sin auditar.
7. Tareas diseñadas por el autor de uno de los harnesses a la medida de sus skills → **holdout** (https://arxiv.org/abs/2407.01502).
8. Grader que rechaza soluciones válidas.
9. Ruido de infraestructura y límites distintos entre variantes.
10. Juez LLM que no es ciego, es el mismo modelo o evalúa en orden fijo.
11. *Optional stopping:* parar cuando "se ve bien".
12. Promediar sin mirar la tabla por tarea: el efecto suele concentrarse en 2–3 tareas.
