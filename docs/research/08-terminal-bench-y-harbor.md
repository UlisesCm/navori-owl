# 08 — Terminal-Bench y Harbor: qué hacen y qué podemos aprender

> Fecha de corte: 2026-09-29. Investigación de solo lectura sobre el sitio https://www.tbench.ai/, su repo
> (https://github.com/harbor-framework/terminal-bench), el paper de Terminal-Bench 2.0
> (https://arxiv.org/abs/2601.11868) y trabajo adyacente. Cada afirmación lleva una etiqueta:
> **[VERIFIED]** = leída en la fuente primaria (archivo, página o paper); **[VERIFIED-SUMMARY]** = obtenida
> con un lector que resume la página, sin leerla completa (las cifras pueden perder matiz);
> **[INFERRED]** = deducción o dato de segunda mano. Ninguna [INFERRED] sostiene una recomendación por sí sola.
>
> Estado de este documento: §1 a §4 (calidad de tareas y metodología) y §6 (funciones de Harbor) completos.
> **Pendiente de agregar:** §5 (reward hacking y seguridad del verifier). Ver §7.

---

## 0. En una página

- Terminal-Bench es un benchmark de tareas en terminal alojado por Stanford, Harbor Framework y el Laude
  Institute. El sitio está en la versión **4.0** (66 tareas); existen la 2.0 (89), la 2.1 (89 con 28
  corregidas) y la 3.0 (74). [VERIFIED-SUMMARY]
- **Harbor** es el runner que `owl` ya usa. Su equipo también mantiene Terminal-Bench, así que los formatos
  (`task.toml`, `tests/`, `reward`) son los mismos.
- La diferencia de fondo: Terminal-Bench compara **modelos y agentes**, sobre un repositorio público. `owl`
  compara **harnesses con el modelo fijo**, con un paciente privado, holdout y pre-registro. En esas tres cosas
  `owl` ya va por delante de Terminal-Bench.
- Lo que sí conviene copiar es su **control de calidad de tareas** (revisión por capas, etiquetas
  estructuradas de falla, política de versionado y retiro) y algunos **controles de metodología** (recursos de
  contenedor fijos, análisis de sensibilidad sobre exclusiones, revisión de trials aprobados).
- Lo que **no** conviene copiar: su intervalo de confianza, el multiplicador de timeout 1.0, quitar tareas
  saturadas a mitad de camino, elegir el mejor scaffold por modelo, y calibrar las tareas a "máximo 30 % de
  resolución".

## 1. Qué es Terminal-Bench y cómo construye sus tareas

### 1.1 Formato y pipeline de contribución

- Una tarea trae `README.md` (para revisores), `instruction.md`, `task.toml`, `environment/Dockerfile`,
  `solution/solve.sh` y `tests/test.sh`. Desde la 3.0 el verifier corre en un **contenedor separado** con su
  propia imagen (`tests/Dockerfile`) y solo ve los `artifacts` declarados. [VERIFIED CONTRIBUTING.md; 3.0
  VERIFIED-SUMMARY]
- El `task.toml` exige metadatos (autor, categoría, subcategoría, etiquetas, `expert_time_estimate_hours`) y el
  README exige cuatro secciones escritas por una persona: dificultad, solución, verificación y experiencia
  relevante. Un CI las comprueba. [VERIFIED]
- Pipeline: propuesta → juez LLM de propuestas (Strong Reject … Strong Accept) → pre-aprobación de un
  mantenedor → PR → checks estáticos + rúbrica LLM + oracle/nop en cada push → revisión humana → merge.
  [VERIFIED]
- La rúbrica de propuestas tiene 6 criterios (verificable, bien especificada, resoluble, difícil, realista,
  verificada por resultado). Reglas notables: "correr el verifier cientos de veces no debe dar fallas";
  usar un juez LLM como verifier solo en circunstancias extraordinarias; rechazar tareas difíciles solo por
  tener muchos casos de esquina. [VERIFIED docs/prompts/task-proposal.md]

### 1.2 Revisión automática de tareas

- **~25 checks estáticos** de CI. Los que tocan lo que nos importa: `check-canary`, `check-no-cheat-dir` (una
  carpeta `cheat/` no puede viajar con la tarea), `check-dockerfile-references` (ni `solve.sh` ni `tests/` en
  la imagen), `check-pip-pinning`, `check-trial-network-fetch` (`test.sh` no puede hacer `curl | sh` ni
  `git clone`), `check-verifier-tooling-baked` (las dependencias del verifier se instalan en el build, no en el
  trial), `check-task-timeout` y `check-task-changelog` (editar una tarea exige una línea en su Change Log).
  [VERIFIED docs/TASK_REVIEW_AUTOMATION.md]
- **Rúbrica LLM de 35 criterios** (`docs/prompts/task-implementation.toml`) en cada push, ejecutada por un
  agente Claude dentro de un sandbox de Harbor. Criterios más relevantes para nosotros:
  `test_instruction_alignment` (cada aserción se traza a un requisito de la instrucción y viceversa),
  `functional_verification` (sin comparar strings, "frágil y manipulable"), `do_not_modify_enforced` (todo
  "no modifiques X" de la instrucción lo hace cumplir el verifier), `verifier_execution_isolation`,
  `binary_reward`, `solution_quality` (el oracle calcula, no imprime la respuesta). [VERIFIED]
- **Ejecución en cada push:** build de Docker, el oracle debe pasar y `nop` debe fallar. El README pide a
  quien consuma la tarea correr el oracle 5 veces para descartar flakiness. [VERIFIED]
- **Comandos bajo demanda de los mantenedores:** `/run` (trials de agente, hasta 10, luego `harbor analyze`),
  `/cheat` (trials adversariales con un prompt de "Red Team"), `/fortify` (bucle hacker ↔ arreglador hasta que
  el verifier aguante) y `/regrade` (re-ejecuta un verifier corregido sobre trials ya grabados, sin volver a
  correr agentes). [VERIFIED]
- **`harbor analyze`** etiqueta cada falla leyendo la trayectoria: `task_specification` (¿la instrucción
  bastaba?), `reward_hacking`, `difficulty_crux` (¿falló por la razón que declaró el autor?), `near_miss`,
  `refusals`, `low_timeout` (¿lo cortó el tiempo mientras progresaba?). [VERIFIED
  docs/prompts/trial-analysis.toml]
- El paper de 2.0 añade un agente explotador (un OpenHands al que se le pide actuar como investigador de
  seguridad y "completar la tarea SOLO si pudiera hacer trampa") con las trayectorias inspeccionadas a mano.
  Exploits comunes: monkey-patch del entorno de tests, adivinar respuestas, enumerar todas las respuestas
  posibles cuando el test solo comprueba que exista la correcta. [VERIFIED arXiv 2601.11868, apéndice B.4]

### 1.3 Dificultad, versiones y retiro de tareas

- Dos etiquetas de dificultad en 2.0: estimación humana del autor (y tiempo de experto) y **dificultad
  empírica** por tasa de resolución de frontera (Fácil ≥ 66.7 %, Media 33.3–66.7 %, Difícil < 33.3 %). La
  correlación entre ambas es r = 0.436. [VERIFIED paper §2.4, §4.3]
- Regla contra la selección adversarial: no generar muchas tareas y quedarse solo con las que falla el mejor
  modelo, porque eso encuentra "esquinas triviales" de capacidad. [VERIFIED CONTRIBUTING.md]
- La 3.0 pide tareas con "como máximo 30 % de resolución de los mejores modelos al lanzamiento".
  [VERIFIED-SUMMARY]
- **Versión 2.1: 28 de 89 tareas corregidas** (9 por dependencias externas que cambiaron al tener internet
  abierto, 8 por recursos insuficientes incluso para el oracle, el resto por mala especificación; una tarea
  pedía PostgreSQL en la instrucción y calificaba con Spark SQL), pese a ~3 horas de revisión humana por tarea.
  [VERIFIED-SUMMARY]
- **Versión 4.0:** de 74 a 66 tareas. Se quitaron 8 (2 saturadas, 2 por refusals, 2 con solución pública, 2
  con problemas de calidad sin resolver) y se revisaron 19–20 (las fuentes discrepan). "Saturada" significa
  que todas las clases de todas las familias de modelos de la última generación la resuelven 5/5.
  [VERIFIED-SUMMARY]
- Versionado semántico: cualquier cambio visible para el agente exige volver a correr los trials.
  [VERIFIED-SUMMARY]
- Una auditoría de terceros con LLM (LessWrong) y la de Epoch AI (30 de 66 tareas de la 4.0 con defectos de
  calificación anotados públicamente) muestran que el problema persiste. [VERIFIED-SUMMARY; fuentes de tercera
  mano, evidencia más débil]

## 2. Metodología, leaderboard y reporte

### 2.1 Cómo calculan la tasa de resolución

- Cada combinación agente + modelo se corre **al menos 5 veces** (32 155 trials, 6 agentes × 16 modelos).
  [VERIFIED paper §3]
- El IC 95 % es pass@1 ± 1.96·SE sobre las corridas. El paper de DeepSWE (arXiv 2607.07946, §5.5) dice
  seguir esta convención y advierte que **solo captura la varianza de volver a correr las mismas tareas**, no el
  muestreo de tareas, y que con ~4 corridas "parece muy preciso aunque la incertidumbre real sea grande". Que
  Terminal-Bench use exactamente esa fórmula es [INFERRED] por esa cita: el paper de TB solo dice "IC 95 %".
- Distintos operadores reportan distinto: Vals AI usa avg@3 con error estándar entre las tres corridas.
  [VERIFIED]
- La Figura 1 del paper muestra, por modelo, el scaffold elegido para maximizar su rendimiento: es la mejor
  opción de varios agentes sin corrección. [VERIFIED]
- Costo y tokens del leaderboard 4.0 son totales de la corrida completa y "no están normalizados por nivel de
  esfuerzo". [VERIFIED]

### 2.2 Verificación de envíos

- Un envío exige `timeout_multiplier == 1.0`, sin overrides de CPU, memoria ni disco, mínimo 5 trials por
  tarea y que el agente no acceda al sitio ni al repo de Terminal-Bench. [VERIFIED]
- Para la 2.1 las contribuciones de la comunidad están cerradas: solo se agregan corridas de los mantenedores.
  [VERIFIED]

### 2.3 Timeouts, recursos, errores de infraestructura

- Anthropic (ya citado en `02-metodologia.md`) midió: un cap estricto de 1× da 5.8 % de errores de infra contra
  0.5 % sin cap, y entre 1× y 3× el puntaje queda dentro del ruido. [VERIFIED]
- DeepSWE excluye del numerador y del denominador los rollouts con error de proveedor, verifier o red, **sin
  re-muestrear**, y cuenta como fallo genuino el agotar contexto o el timeout. Lo excluido va de 0 % a 5.3 % y
  "el orden del leaderboard no es sensible a la regla". [VERIFIED]
- Un `reward` ausente o ilegible es un error de trial en Harbor, y algunos adaptadores ajenos lo convierten en
  0.0 silencioso. [VERIFIED de títulos de issues]

### 2.4 Análisis de fallas y estudios que comparan harness con el modelo fijo

- El paper de TB clasifica fallas con una taxonomía de 3 clases y 9 subclases; el acuerdo entre dos humanos fue
  κ = 0.93 y un juez GPT-5 coincidió 90 % con las trazas humanas. [VERIFIED paper §4.4–4.5]
- HAL inspeccionó 1 634 transcripts con Docent y encontró agentes que buscaron respuestas en HuggingFace.
  [VERIFIED]
- "Harness or Model?" (arXiv 2609.11987): suite privada de 256 tareas, contrastes pareados con el mismo modelo,
  hipótesis pre-comprometidas con fecha y bootstrap por tarea de 10 000 remuestreos. Halló diferencias
  promedio no resueltas pero una interacción por tipo de carga. Dos hallazgos operativos útiles: 22 de 81
  corridas canceladas por reloj ya tenían un parche válido, y un defecto en la telemetría de costo. [VERIFIED-
  SUMMARY]
- "Stop Comparing LLM Agents Without Disclosing the Harness" (arXiv 2605.23950): en Terminal-Bench, cambiar el
  harness con el modelo fijo mueve el pass@1 **8.5–13.0 puntos**, y cambiar el modelo con el harness fijo mueve
  2.5–5.0. Propone una tarjeta de divulgación de 7 capas (ETCSOVG). [VERIFIED-SUMMARY]

## 3. Contraste con `owl`

### 3.1 Dónde `owl` ya iguala o supera a Terminal-Bench

| Tema | Terminal-Bench | `owl` |
|---|---|---|
| Contaminación | Canary GUID; sin conjunto privado (el propio paper lo llama "largely symbolic") | Paciente privado, canary en todo menos `instruction.md`, holdout con reporte redactado, quemado tras revelar |
| Repetibilidad del oracle | Una corrida en CI | 5 de 5 corridas deben dar reward 1 (`owl/validate.py`) |
| Ataques al verifier | Manual y por LLM bajo demanda | Seis ataques con script (`read-hidden`, `tamper-fail`, `tamper-pass`, `hardcode`, `move-baseline`, `plant-reward`) validados en `owl validate` |
| Historia de git | "Se quitan commits futuros" | Un solo commit de fixture, sin remotos ni reflog, verificado por `read-hidden` |
| Estadística | IC entre corridas | Bootstrap por tarea, sign-flip exacto y Holm (D12) |
| Orden de trials | No documentado | Bloques intercalados con permutación sembrada |
| Costo | Totales por corrida | Precios fijos con caché 5 min y 1 h, validados contra 24 trials |
| Pre-registro | No | `RULES.md` antes del primer trial, la ronda se niega con árbol sucio |
| No quitar tareas viendo datos | Regla contra selección adversarial | R23 |

### 3.2 Brechas encontradas

Tareas y calidad:

| # | Práctica de Terminal-Bench | Brecha en `owl` |
|---|---|---|
| 1 | Etiquetas estructuradas de falla (`harbor analyze`) | `failures.md` clasifica atribución, no modo de falla |
| 2 | Lint de red y de dependencias sin fijar en `tests/` y `solution/` | No existe; `owl validate` tiene 8 checks estáticos |
| 3 | Lockfile de dependencias | `patient/Dockerfile:49` hace `npm install` sin lockfile |
| 4 | Alineación instrucción ↔ test en ambas direcciones | Solo disciplina del autor |
| 5 | Rúbrica LLM para revisar una tarea al crearla | No existe; `design.md:892` difiere el juez LLM |
| 6 | Verifier repetido también del lado negativo | `nop` y los ataques no se repiten 5 veces |
| 7 | `/regrade` | No hay forma de recalificar trials terminados |
| 8 | Versión y changelog por tarea, y criterios de retiro | Solo la regla "nunca quitar tareas viendo resultados" |
| 9 | Campos de dificultad, solución y verificación por tarea | Solo `owl_promise` y `owl_notes` |

Metodología:

| # | Práctica o riesgo | Brecha en `owl` |
|---|---|---|
| 10 | Recursos de contenedor fijos (piso y techo) | Ningún `task.toml` declara `cpus` ni `memory_mb`, y `round.yaml` no los fija; la ronda corre a concurrencia 2 en Docker Desktop |
| 11 | Sensibilidad ante exclusiones | D11/R16 excluyen y **reintentan**; no hay análisis pre-registrado (ver C1) |
| 12 | Puntaje por corrida como diagnóstico de deriva | Falta la tabla por bloque y variante |
| 13 | Esfuerzo/thinking normalizado | No se fija ni se registra |
| 14 | Tokens totales independientes del precio | R29 no los lista |
| 15 | Revisión de trials **aprobados** | R34/R39 solo revisan fallas |
| 16 | Tarjeta de divulgación del harness | Parcial: falta volcar herramientas, hooks y permisos efectivos |
| 17 | Verificación por terceros | Ninguna; falta definir qué se publica al cerrar r1 |

### 3.3 Contradicciones y riesgos en la spec de F3

- **C1. Reintento tras exclusión vs. "no re-muestrear" (DeepSWE).** [INFERRED] D11/R16 excluyen `api_stall` y
  re-corren dentro del bloque. Un estancamiento de 5 minutos es más probable cuanto más llamadas hace el
  harness, así que el trial de reemplazo es el subconjunto que no se estancó. Eso puede sesgar el costo hacia
  abajo justo para los harnesses pesados. DeepSWE evita el problema excluyendo sin re-muestrear. La decisión de
  `owl` se sostiene solo si se agrega el análisis de sensibilidad.
- **C2. Timeout ×3.0 (D7) vs. `timeout_multiplier == 1.0` de TB.** No es error: TB necesita 1.0 para comparar
  envíos entre sí y `owl` compara variantes entre sí. Pero `RULES.md` debe decir que las cifras de `owl` **no
  son comparables** con el leaderboard de Terminal-Bench.
- **C3. IC de TB vs. bootstrap por tarea.** `owl` está mejor justificado; no se copia el de TB.
- **C4. Tareas saturadas.** TB 4.0 las quita; `owl` las conserva (R23), que es lo correcto para un set
  pre-registrado. El riesgo real ya está en la spec: en el piloto 8 de 12 tareas salieron 2/2 y 3 salieron 0/2.
- **C6. Costo reportado no es factura.** [INFERRED] La ronda corre con OAuth. "Harness or Model?" halló residuos
  de 25–29 % entre telemetría y gasto facturado en Anthropic. El costo debe declararse como "equivalente API a
  precios de lista".
- **C7. Recursos sin fijar.** Anthropic midió 6 puntos porcentuales de diferencia según la configuración de
  recursos. Un harness que lanza procesos (MCP, hooks, subagentes) compite más por CPU y memoria y acumula
  timeouts por contención: un sesgo que depende de la variante.
- **C8. Esfuerzo/thinking no declarado.** [INFERRED] Un prompt de harness que active más razonamiento sube los
  tokens de salida. Es un efecto legítimo del tratamiento, pero debe quedar registrado y no supuesto.
- **C10. Solo se revisan fallas.** HAL halló agentes buscando respuestas y TB tuvo vectores de hack en 28 de 89
  tareas. Con red pública, una variante puede aprobar por una vía no prevista sin que nadie lo vea.
- **Inconsistencia previa en `VISION.md`:** la línea 173 dice "Sin red externa", pero las tareas declaran
  `network_mode = "public"` (`specs/f3-ronda1/design.md:618,736`). Pendiente de corregir.

## 4. Recomendaciones consolidadas

Esfuerzo: **S** ≤ medio día, **M** 1–2 días, **L** > 2 días. "F3 ahora" significa antes de commitear
`RULES.md`, y no cambia el reward de ninguna tarea. Todo cambio en `tasks/`, `owl/` o `patient/` debe estar
commiteado antes de la ronda (la ronda se niega con árbol sucio, R3).

### 4.1 Candidatas para F3 (baratas y sin tocar rewards)

| Id | Recomendación | Esfuerzo | Riesgo |
|---|---|---|---|
| A | **Recursos de contenedor fijos y registrados**: CPU/RAM de Docker Desktop y `--override-cpus/--override-memory-mb` en `round.yaml`, `owl-variant.json` y el gate de conformidad; una corrida de humo a concurrencia 2 con `docker stats` | S | Bajo |
| B | **Análisis de sensibilidad pre-registrado** sobre exclusiones: repetir los endpoints primarios con `infra` contado como fallo, descartando el par (tarea, bloque) completo, y sin reintentos; sin nuevos p-values en la familia Holm | S–M | Bajo |
| C | **Tabla de puntaje por bloque y variante** como diagnóstico de deriva, etiquetada "entre corridas, no incluye muestreo de tareas" | S | Bajo |
| D | **Registrar esfuerzo/thinking, permisos y herramientas efectivas** por variante; declarar en `RULES.md` que no se fija el esfuerzo | S | Bajo |
| E | **Tokens totales** por variante y tarea como descriptivas | S | Bajo |
| F | **Etiquetas de modo de falla** en `failures.md` (agente, instrucción insuficiente, verifier estrecho o amplio, casi acierto, corte por tiempo, infra), con segunda lectura de una muestra | S | Bajo |
| G | **Lint estático de red y pinning** en `tests/`, `solution/` y `cheat/` como noveno check de `owl validate` (correr primero `owl validate --checks static` para confirmar que hoy pasan) | S | Bajo |
| H | **Texto en `RULES.md`**: cifras no comparables con Terminal-Bench, k = 3 bajo el mínimo de 5 de TB, costo = equivalente API, versionado de tareas y criterios de retiro evaluados solo entre rondas | S | Nulo |
| I | **Escaneo mecánico de trials aprobados** (solo dev, nunca holdout): lecturas de rutas de tests u oráculo, ediciones a configs de test, URLs consultadas, procesos de fondo | M | Medio: falsos positivos |

### 4.2 Después de la ronda 1

| Id | Recomendación | Esfuerzo |
|---|---|---|
| J | Lockfile del paciente (`package-lock.json` + `npm ci`); cambia la imagen, así que se hace entre rondas | S |
| K | Checklist de alineación instrucción ↔ test por tarea, obligatorio en tareas holdout nuevas | M |
| L | Rúbrica LLM de revisión de tareas al crearlas (no al calificar; compatible con el principio 3 de `VISION.md`) | M |
| M | `nop` y ataques repetidos 5 veces en `owl validate` | S–M |
| N | `owl regrade`: guardar el estado final del trial y recalificar con un verifier corregido | L |
| Ñ | Campos de dificultad, solución y verificación por tarea | S por tarea |
| O | Pase de red-team con LLM sobre verifiers nuevos, como comando aparte (`owl red-team`) | M |
| P | Definir qué se publica al cerrar r1 para que un tercero pueda recalificar | M |
| Q | Contraste puntual de costo contra facturación con API key | S–M |
| R | Regla de saturación pre-registrada para r2 | S |
| S | Brazo de referencia neutral y segundo modelo (diseño factorial) | L |
| T | Juez LLM calibrado con humanos como clasificador secundario de fallas | M–L |

### 4.3 Lo que no se recomienda copiar

- **IC entre corridas de TB** como intervalo principal (C3).
- **`timeout_multiplier` 1.0** (C2): sirve para comparar con un leaderboard que `owl` no persigue.
- **Verifier en contenedor separado**: rompe el diseño de `owl`, donde el baseline vive en el contenedor. Se
  revisa solo si se implementa `owl regrade`.
- **Calibrar las tareas al objetivo de "máximo 30 % resuelto"**: choca con `specs/f3-ronda1/design.md:238`.
  Al comparar harnesses, las tareas de techo y de piso siguen siendo válidas.
- **Quitar tareas 0/k o k/k a mitad de ronda** (C4) y **elegir el mejor scaffold por modelo** (Figura 1 de TB).
- **Decir al agente "no busques soluciones en línea"**: sería un tratamiento que se solaparía con el placebo, y
  D5 exige que el preámbulo no mencione conducta.

## 5. Reward hacking y seguridad del verifier — pendiente

Se agregará con la investigación de los vectores V1–V9 del issue
https://github.com/harbor-framework/terminal-bench/issues/2086 y del paper Hack-Verifiable Terminal Bench
(https://arxiv.org/abs/2608.22103), cruzados contra los seis ataques de `owl validate`.

## 6. Funciones de Harbor que `owl` no usa o reimplementa

Etiquetas de esta sección: **[VERIFIED]** = leído en el código instalado (`harbor==0.23.0`, `H/` = el paquete en
`.venv`) o en un artefacto real de un trial de este repo; **[DOCS]** = documentación oficial leída en la web;
**[INFERRED]** = deducción. No se corrió Docker ni Harbor para esta sección.

### 6.1 Estado de versión

- `owl` fija `harbor==0.23.0` (`pyproject.toml:7`, `uv.lock:708`), que es también la última estable en PyPI.
  Nada de lo de abajo necesita una versión más nueva. [VERIFIED]
- Harbor trata un salto menor (0.22 → 0.23) como cambio mayor o rompedor y no promete estabilidad de esquema.
  Conviene mantener el pin exacto y subir solo entre rondas. [DOCS]
- El adaptador de Claude Code de Harbor sigue **sin** opciones de plugins, `--bare`, `--setting-sources` ni
  `--mcp-config`, ni en 0.23.0 ni en `main`. Por eso `ClaudeCodeHarness` sigue siendo necesario.
  (`H/agents/installed/claude_code.py:52-95`) [VERIFIED]

### 6.2 Código propio que está justificado

| Pieza de `owl` | Por qué se queda |
|---|---|
| `pass^k` (`owl/analysis.py`) | El `pass_at_k` de Harbor devuelve `{}` cuando el reward tiene más de una clave (`H/utils/pass_at_k.py:44`), y el `result.json` del piloto lo muestra. [VERIFIED] |
| Estimador de costo | La estimación de Harbor sale ~15 % baja: en un trial del piloto `model_usage` da 0.0709 contra 0.0839 reportado (razón 0.845). [VERIFIED] |
| Reintentos propios | El reintento de Harbor borra el directorio del trial fallido (`H/trial/queue.py:222`), así que los fallos de infra reintentados desaparecerían del registro. **Nunca pasar `--max-retries` a Harbor.** [VERIFIED] |
| Gate de contaminación | Harbor no expone los plugins ni los servidores MCP del evento `system/init`, así que esa mitad de `gate.py` es valor exclusivo de `owl`. [VERIFIED] |
| Plugins en la subclase | Upstream no los tiene (ver 6.1). |
| Sign-flip, Holm y bootstrap | No existen en Harbor; los leaderboards del Hub no calculan estadística. |

### 6.3 Duplicación real y simplificaciones posibles

- **`owl run` lanza un `harbor run -k 1` por trial, en serie** (`owl/cli.py:45-47,123-132`). Un job de Harbor con
  varios agentes ya da la matriz tareas × agentes × intentos, la concurrencia `-n`, un tope por agente
  (`n_concurrent`) y reanudación nativa. `owl validate` ya usa esa ruta (`owl/validate.py:354-382`). El diseño de
  F3 lista un único `JobConfig` como descartado, pero **la razón no quedó escrita** en los archivos revisados. La
  única restricción concreta que se puede inferir es la ventana de uso de la suscripción. [INFERRED]
- **Atribución de trials:** `result.json` ya trae `task_name`, `task_checksum` y `agent_info`, y `config.json`
  lleva el `variant_id` que `owl` le pasa. El parseo del nombre del job y la búsqueda de `owl-variant.json`
  pueden quedar como respaldo y no como clave primaria (`owl/gate.py:168-174`, `owl/summary.py:34-40`).
- **Conformidad:** `lock.json` (digest de la tarea, configuración completa del agente, versión de Harbor) y
  `result.json.agent_info.version` (era `2.1.281` en el piloto) permiten verificar uniformidad sin volver a
  calcular lo que Harbor ya registró. `owl` conserva solo lo que Harbor no puede saber: los hashes de
  `RULES.md`, `round.yaml` y `preamble.md`, y el commit. [VERIFIED]
- **Potencialmente grande, no ahora:** toda la maquinaria de scope dentro del contenedor (`lib.sh`, snapshot,
  baseline, manifiesto, `refs/owl/baseline` y sus tres copias idénticas) existe porque el verifier corre
  `shared` con el contenedor del agente. Un verifier separado más `artifacts` permitiría calcular el scope en el
  host, en Python, a prueba de manipulación por construcción y con una sola copia del algoritmo. [INFERRED,
  rediseño]

### 6.4 Funciones de Harbor que `owl` ignora

| Función | Qué hace | Valor para `owl` |
|---|---|---|
| Verifier separado (`[verifier] environment_mode = "separate"`) + `artifacts` | Solo lo declarado cruza al verifier; aísla al grader del sistema de archivos del agente | Alto, costoso (ver 6.5) |
| **`harbor job regrade`** | Recalifica trials grabados con un verifier corregido: cero costo de agente, sin credenciales de agente. Requiere verifier separado y artefactos ya recolectados [DOCS] | Alto, para después. Responde a "corregí el verifier después de correr": `git status` muestra que `owl/verifier/lib.sh` y todos los `tasks/*/tests/owl-lib.sh` se editaron tras el piloto |
| Política de red (`no-network`, `public`, `allowlist` con control de egreso; Docker lo soporta) | Haría cumplir "solo la API del modelo" (VISION §7.5) y volvería obligatorio, no de palabra, `GENTLE_AI_TELEMETRY=0` | Medio, para la ronda 2. Puede romper harnesses que usan `npx` o WebFetch, y cambiar el tratamiento |
| Usuario simulado sobre ACP (`--user-agent`, persona) | Un agente-usuario conversa con el agente evaluado; el ejemplo de la documentación tarda ~50 min | Medio, F6. Sustituye la idea de "usuario simulado como fase 2" de `VISION.md` D7 |
| Tareas de varios pasos y `--resume-trajectory` | Reanuda la misma sesión nativa entre pasos | Medio, F6: es exactamente la tarea "multisesión que depende de una decisión previa" para harnesses de memoria |
| Trayectorias ATIF (`agent/trajectory.json`, ATIF-v1.7) | Registro portable del proceso con llamadas de herramientas estructuradas | Medio: los indicadores de proceso podrían leer un esquema en vez de las rarezas del stream-json. La separación de subagentes es solo inferida (el piloto no tuvo subagentes) |
| `harbor view DIR` | Visor web de jobs, trials, trayectorias, salida del verifier y logs; cuadrícula de comparación | Medio y gratis. Como `owl` crea un job por trial, la cuadrícula sería un muro de jobs de un trial; con un job por variante y bloque se vería como tarea × variante [INFERRED] |
| `harbor analyze --failing` | Un agente Claude analiza cada trial y devuelve un resumen más una rúbrica (`reward_hacking`, `task_specification`, o una propia) | Medio, solo como triage (ver 6.5) |
| `harbor check TASK` | Revisión de una tarea con rúbrica LLM de 11 criterios | Bajo: `owl validate` cubre lo determinista y gratis |
| Entornos remotos (Daytona, Modal, E2B, Runloop y ~30 más) | Concurrencia alta en infraestructura remota | Condicional (ver 6.5) |
| Adaptadores públicos (87: SWE-bench, aider_polyglot, featbench, …) | Corren benchmarks públicos en formato Harbor | Medio, F6: validar el pipeline contra una cifra publicada y armar suites de perfil; nunca como suite decisiva por riesgo de contaminación |
| Rewardkit | Criterios como funciones Python o jueces LLM en TOML | Medio, F4+, para dimensiones juzgadas. No documenta ceguera a la variante ni calibración humana, que `VISION.md` D9 exige |
| Recursos por tarea (`cpus`, `memory_mb`) y `--override-*` | Recursos uniformes | Bajo en apariencia, pero conecta con la recomendación A de §4 |
| `--print-config` | Imprime el `JobConfig` resuelto | Pequeño: un artefacto gratis de pre-registro con exactamente lo que correrá la ronda |
| Telemetría (PostHog) | Estadísticas agregadas por job: nombres de modelo, media de reward, costo, duraciones | **Higiene de privacidad:** `owl` nunca la desactiva, así que la media de reward de corridas holdout sale de la máquina. Se apaga con `HARBOR_TELEMETRY=0`. [VERIFIED `H/telemetry.py`] |

### 6.5 Matices que cambian la lectura

- **Los sandboxes remotos no ayudan a las corridas con suscripción.** El límite real es la ventana de uso de 5
  horas: más paralelismo solo la alcanza antes, no sube la cuota de la cuenta. Además hoy están bloqueados por
  `FROM owl-patient:local`, una etiqueta local que ningún builder remoto resuelve. Solo tendrían sentido con
  corridas por API key, un cambio grande. Tampoco se verificó si usar un token de suscripción desde una nube
  de terceros contradice los términos del proveedor. [INFERRED salvo lo verificado en el Dockerfile]
- **Todo lo que corre un modelo** (`harbor analyze`, `harbor check`, jueces de Rewardkit, usuario simulado,
  conversar con `harbor trial handoff`) consume de la misma ventana. `regrade`, `view`, `--print-config` y la
  lectura de ATIF no gastan tokens de modelo.
- **`harbor analyze` copia el `tests/` y el `solution/` de cada tarea a su sandbox de análisis**, así que **nunca
  debe apuntarse a tareas holdout** (violaría R15). Tampoco es ciego a la variante (el `config.json` del trial
  lleva `variant_id`): sirve para ordenar la cola de lectura, no para dictar veredictos. Su bandera
  `reward_hacking` debe validarse contra los `tampered` de `owl` antes de confiar en ella.
- **El Hub** (subir, publicar, jobs alojados, leaderboards) no se recomienda: copiaría tareas y trayectorias a un
  tercero (posiblemente el holdout) y sus leaderboards son filas que uno calcula, sin estadística. No se
  encontró documentación sobre jobs alojados con tokens de suscripción.

### 6.6 Recomendaciones de Harbor, ordenadas

| Id | Recomendación | Esfuerzo | Fase |
|---|---|---|---|
| H1 | Poner `HARBOR_TELEMETRY=0` en el entorno de todo subproceso `harbor` (`cli.py:_auth_env`, `validate.py:_run_harbor_job`) y probar que está | S | F3 ahora |
| H2 | Leer más de lo que Harbor ya registra: `agent_info.version` contra `variant.agent_version`, `exception_info.exception_type`, `lock.json` para uniformidad de límites y configuración, tiempos por fase; no pasar `--max-retries` | S | F3 ahora |
| H3 | Revisión de fallas con `harbor view` y `trajectory.json` (gratis). `harbor analyze --failing` con rúbrica propia solo como triage, en dev, después de la ronda | S (view) / M (analyze) | F3 ahora (view); después (analyze) |
| H4 | Agrupar trials en jobs de Harbor (uno por variante y bloque, con `n_concurrent: 2` por agente) y usar SIGTERM + `harbor job resume` como cortacircuito | M–L | Ronda 2; no reabrir D9 de F3 |
| H5 | Lista de permitidos de red nativa | M | Ronda 2 |
| H6 | Spike de verifier separado + `artifacts` + `regrade`, con prueba de éxito: recalificar los 24 trials del piloto y reproducir `reward.json` exactamente | L | F4/F6; invalida la calibración del piloto |
| H7 | Tareas de varios pasos y usuario simulado para harnesses de memoria | M | F6 |
| H8 | Sandboxes remotos con corridas por API key | L | Solo si se pasa a API key |
| H9 | Adaptadores públicos como sanity check y suites de perfil | M | F6 |
| H10 | Rewardkit para dimensiones juzgadas, con envoltorio que oculte la variante | M | F4+ |
| — | No adoptar: subir al Hub, publicar, jobs alojados, `harbor sweeps`, el estimador de costo de Harbor ni su `pass_at_k` | — | — |

Paquete sugerido para F3: **H1 + H2 + la parte de `harbor view` de H3**, en medio día, sin cambio de diseño y sin
tokens extra.

### 6.7 Incertidumbres de esta sección

- No está confirmado que un plugin de job pueda cancelar un job en curso; el camino verificado para detenerlo es
  SIGTERM y luego `harbor job resume`.
- La división de costo por subagentes desde ATIF no se pudo confirmar con datos reales.
- No se encontró precio de sandboxes ni los términos de privacidad del Hub.

## 7. Límites de esta investigación

- Varias cifras de las versiones 2.1, 3.0 y 4.0 provienen de un lector que resume ([VERIFIED-SUMMARY]) y dos
  páginas discrepan en "19 vs 20 tareas revisadas". Tomar los conteos como aproximados.
- El paper de Terminal-Bench no da la fórmula exacta del IC; se dedujo de DeepSWE.
- No se pudo leer la documentación de Harbor sobre reintentos ni cómo trata los trials con excepción.
- Los papers 2609.11987, 2605.23950, 2608.26218 y 2512.21326 se leyeron por resumen de página. **Abrir
  2609.11987 completo antes de citarlo en `RULES.md`.**
- No se auditaron los `hardcode.sh` por tarea ni se abrió `holdout/`.

## 8. Fuentes

- Terminal-Bench: https://www.tbench.ai/ · repo https://github.com/harbor-framework/terminal-bench ·
  `CONTRIBUTING.md`, `docs/TASK_REVIEW_AUTOMATION.md`, `docs/prompts/task-proposal.md`,
  `docs/prompts/task-implementation.toml`, `docs/prompts/trial-analysis.toml`, `docs/prompts/hack-trial-prompt.md`
- Paper de Terminal-Bench 2.0: https://arxiv.org/abs/2601.11868
- Noticias de versión: https://www.tbench.ai/news/terminal-bench-2-1 · /terminal-bench-3-0 · /terminal-bench-4-0
- Snorkel (QA continuo): https://snorkel.ai/blog/terminal-bench-4-continuous-qa/ · leaderboard
  https://snorkel.ai/leaderboard/terminal-bench-4-0/
- Issue de mitigaciones: https://github.com/harbor-framework/terminal-bench/issues/2086
- Hack-Verifiable Terminal Bench: https://arxiv.org/abs/2608.22103
- DeepSWE: https://arxiv.org/pdf/2607.07946
- Anthropic, ruido de infraestructura: https://www.anthropic.com/engineering/infrastructure-noise
- HAL: https://arxiv.org/html/2510.11977
- Comparaciones de harness: https://arxiv.org/html/2609.11987 · https://arxiv.org/html/2605.23950v1 ·
  https://arxiv.org/html/2607.22585v1 · https://arxiv.org/abs/2512.21326 · https://arxiv.org/html/2608.26218
- LangChain, Deep Agents CLI en TB 2.0: https://www.langchain.com/blog/evaluating-deepagents-cli-on-terminal-bench-2-0
- HARBOR (optimización de harness; otro proyecto con el mismo nombre): https://arxiv.org/abs/2604.20938
- Epoch AI, revisión de TB 4.0: https://epoch.ai/benchmarks/terminal-bench-4/review
- LessWrong, auditoría de terceros: https://www.lesswrong.com/posts/HzjssjeQqhf3kRw9r/every-benchmark-is-broken
