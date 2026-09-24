# 01 — Cómo se construyen los benchmarks públicos de agentes de código

> Fecha de corte: 2026-09-23. Síntesis neutral (no ligada a ningún harness) de la investigación original de
> `navori-evals/docs/research/01-coding-benchmarks.md`. Cada afirmación lleva su fuente. **UNVERIFIED** =
> no confirmado en fuente primaria; no se usa para sostener recomendaciones.

**Para qué sirve este documento en navori-owl:** no vamos a correr SWE-bench. Lo usamos para copiar
*cómo* están hechos los benchmarks serios (formato de tarea, calificación, anti-trampa) y para no
repetir sus errores documentados.

---

## 1. Fichas resumidas

| Benchmark | Qué contiene | Cómo califica | Lección para owl | Fuente |
|---|---|---|---|---|
| **SWE-bench** (2023) | 2,294 issues reales de 12 repos Python | Aplica el patch y corre tests ocultos: FAIL_TO_PASS (el bug queda arreglado) + PASS_TO_PASS (no se rompió nada) | El par F2P+P2P es el estándar de "resuelto" | https://arxiv.org/html/2310.06770 |
| **SWE-bench Verified** (2024) → **retirado** (feb-2026) | 500 tareas filtradas por 93 devs; se descartó el 68.3% por mal especificadas o tests injustos | Igual | Incluso con revisión humana, OpenAI encontró después que ≥59.4% de las tareas difíciles auditadas tenían tests defectuosos, y hubo contaminación: modelos que reproducían los patches de memoria | https://openai.com/index/introducing-swe-bench-verified/ · https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ |
| **SWE-bench Pro** (Scale, 2025) | 1,865 tareas; repos GPL y comerciales privados para evitar contaminación | F2P/P2P revisados por humanos, tests flaky eliminados | Enunciado en 3 partes: problema, requisitos verificables e interfaces nuevas, sin dictar la implementación | https://arxiv.org/html/2509.16941 |
| **Terminal-Bench 2.0** (2025-26) | 89 tareas escritas a mano (SWE, sysadmin, seguridad, ML) | **Solo el estado final del contenedor**; el agente resuelve como quiera | Formato de tarea que owl adopta (vía Harbor): instrucción, Dockerfile, tests, solución oráculo, timeout. QA: ~3 h de revisor por tarea, **agente adversarial que intenta hacer trampa**, ≥5 corridas por combinación | https://arxiv.org/html/2601.11868v1 |
| **SWE-Lancer** (2025) | 1,488 tareas freelance reales (USD 1M) | Tests E2E con Playwright (comportamiento de usuario, no unit tests) | Para frontend, calificar comportamiento observable | https://arxiv.org/html/2502.12115 |
| **SWE-smith** (2025) | 50k tareas con bugs **inyectados** (AST, LM, revertir PRs) | Solo se conserva un bug si rompe al menos un test que antes pasaba | Validar mecánicamente cada bug sembrado | https://arxiv.org/html/2504.21798 |
| **BugPilot** (2025) | Bugs "accidentales": se le pide una feature al agente y lo que rompe se vuelve tarea | Tests | Los bugs inyectados a mano son poco realistas; combinarlos con bugs accidentales | https://arxiv.org/abs/2510.19898 |
| **FeatBench** (2025) | 157 features en repos reales, pedidas sin pistas de código | F2P + P2P | **El 73.6% de las fallas son regresiones por implementación agresiva o scope creep** → medir P2P siempre | https://arxiv.org/html/2509.22237 |
| **BaxBench** (2025) | 392 tareas backend (incluye Express, Nest, Fastify) | Tests funcionales + **exploits reales** (13 CWEs) | ~50% del código correcto era explotable: la seguridad se mide con exploits, no con opiniones | https://arxiv.org/html/2502.11844 |
| **FullStack-Bench** (2026) | 101 instrucciones sobre Next.js + NestJS + Postgres | Jueces agentes (GUI + API) + snapshot de DB; 90–97% de acuerdo con humanos | Si se usa un juez LLM, publicar su acuerdo con humanos | https://arxiv.org/html/2602.03798v1 |
| **DeepSWE** (2026) | 113 tareas **originales, nunca publicadas** | Verificadores a mano que aceptan cualquier implementación + juez LLM de auditoría | Tareas privadas y originales = poco riesgo de contaminación | https://arxiv.org/html/2607.07946 |
| **METR HCAST / RE-Bench** | 189 tareas + 7 entornos de I+D | Función de scoring que corre como root; el agente corre como usuario sin privilegios | El grader debe ser inalcanzable para el agente | https://arxiv.org/html/2503.17354v1 |
| **Aider Polyglot** | 225 ejercicios Exercism en 6 lenguajes | Tests, 2 intentos | Simple y barato, pero público → contaminado (inferencia) | https://aider.chat/2024/12/21/polyglot.html |

## 2. Qué se considera robusto y qué frágil

**Robusto (con evidencia):**
1. Evaluar el **resultado**, no el camino: estado final, HTTP de caja negra, E2E de navegador (Terminal-Bench, SWE-Lancer, [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
2. **F2P + P2P**; P2P detecta regresiones, que son la falla dominante (FeatBench).
3. **Solución oráculo** por tarea que pase los tests: prueba que la tarea es resoluble (Terminal-Bench).
4. **Agente tramposo** antes de congelar la tarea (Terminal-Bench).
5. **Varias corridas por tarea** (≥5 en Terminal-Bench, ~4 en DeepSWE).
6. **Seguridad como exploit ejecutable** (BaxBench).

**Frágil (errores documentados):**
1. Tests *narrow* que rechazan soluciones válidas: 35.5% de las fallas auditadas en Verified.
2. Tests *wide* que exigen algo que no se pidió.
3. Tests débiles que aceptan patches incorrectos ([SWE-Bench+](https://arxiv.org/abs/2410.06992), [PatchDiff](https://arxiv.org/abs/2503.15223), [UTBoost](https://arxiv.org/abs/2506.09289)).
4. La solución filtrada en el issue o en **el historial de git**: agentes que usaron `git log --all` o `reflog` para encontrar el fix futuro ([SWE-bench #465](https://github.com/SWE-bench/SWE-bench/issues/465)).
5. Dependencias de red inestables (`download-youtube` en Terminal-Bench 1.0).
6. Un juez LLM como única señal, sin calibrar.
7. Material público estático: se contamina.

## 3. Taxonomía de tipos de tarea (para la suite de owl)

| Tipo | Benchmarks de referencia |
|---|---|
| Bugfix desde issue | SWE-bench y variantes |
| Feature en repo existente | FeatBench, FEA-Bench, SWE-Lancer, DeepSWE |
| Greenfield / servicio desde spec | Commit0, BaxBench, BackendForge, FullStack-Bench |
| Refactor con invariante | RefactorBench |
| Escribir tests / reproducir | SWT-bench |
| Terminal, entorno, ops | Terminal-Bench |
| Seguridad | BaxBench, CWEval |
| Code review | SWE-Lancer Manager, SWR-Bench (ver doc 03) |

## 4. Recomendaciones para un benchmark privado y pequeño (lo que owl copia)

1. **Formato Terminal-Bench/Harbor** por tarea, con tests fuera de la vista del agente.
2. **Mezcla de tipos**, no solo bugfix.
3. **Calificación por capas:** F2P ocultos, suite existente como P2P, HTTP de caja negra en backend, Playwright en frontend y typecheck/lint como gates.
4. **Enunciado estilo Pro/FeatBench:** problema, requisitos verificables e interfaces nuevas nombradas.
5. **Checklist por tarea:** *specificity* (los tests pasan si y solo si el resultado es aceptable), *solvability* (el oráculo pasa y la base falla), *integrity* (sin atajos).
6. **Git limpio:** un commit base sin tags, remotes ni reflog.
7. **Sin red externa;** lockfiles fijados.
8. **Canary string** en los archivos de tareas y repo privado.
9. **Correr el oráculo N veces** para descartar tests flaky.
10. **Leer los transcripts de las fallas** para separar "tarea rota" de "agente incapaz".
