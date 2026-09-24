# 05 — Herramientas y proyectos paralelos: qué existe y sobre qué construir

> Fecha de corte: 2026-09-23. Las afirmaciones sobre Claude Code y Harbor se revisaron ese día contra la
> documentación oficial y el código fuente (URLs abajo). Estrellas verificadas con `gh`. **UNVERIFIED** = no
> confirmado en fuente primaria; no sostiene recomendaciones.

---

## 1. Proyectos que ya hacen "harness contra harness" (o "config contra vanilla")

| Proyecto | ★ | Cómo aísla las variantes | Cómo califica | Qué reporta | Lección para owl |
|---|---|---|---|---|---|
| **superpowers-evals / Quorum** https://github.com/prime-radiant-inc/superpowers-evals | 118 | "quorum pins each Coding-Agent's `HOME` (plus the XDG base dirs and `TMPDIR`) to a throwaway per-run home". Maneja varios CLIs: Claude, Codex, Gemini, OpenCode, Copilot… | Un **agente QA ("Gauntlet") conversa con el agente evaluado como si fuera usuario**; los criterios de aceptación quedan privados y un "assessor" fresco califica después. Veredicto pass/fail + post-checks | Campañas en reportes autenticados; no en CI público | HOME desechable por corrida. **Usuario simulado** para harnesses que preguntan. No correr agentes con API keys en CI público |
| **ponytail benchmarks** https://github.com/DietrichGebert/ponytail/tree/main/benchmarks | (repo 145k) | Copia fresca del repo y proceso nuevo por corrida; Claude Code 2.1.177 headless | Features: LOC por `git diff`. Seguridad: ejecución adversarial determinista (path traversal, SQLi, tokens forjados, CSV malformado, cuota) | LOC, tokens, costo, tiempo, % seguro | **4 brazos con placebo** (baseline, caveman = "solo ser breve", ponytail, prompt de una línea): separa el efecto real del efecto estilo. Limitaciones que ellos mismos declaran: un solo modelo, n=4 |
| **langchain-ai/skills-benchmarks** https://github.com/langchain-ai/skills-benchmarks | 117 | "Treatments" (CONTROL sin skills vs ALL_MAIN_SKILLS…) que arman un directorio temporal; Claude Code en Docker | Scripts de validación por tarea (`task.toml` + `validation/`) | Pass rate, duración, turnos, skills usadas; en LangSmith | Tratamiento CONTROL explícito; medir si el skill **se activó** |
| **Qihoo360/harness-bench** (código de Harness-Bench, arXiv 2605.27922) https://github.com/Qihoo360/harness-bench | 110 | Workspace sandbox con fixtures copiadas; **usage-proxy** que captura todas las llamadas al LLM, igual para cualquier harness | `oracle_grade.py` (outcome) × media de 3 dimensiones de proceso × **gate binario de seguridad** | `combined_score = outcome × process × security` | Proxy de uso: contabilidad de tokens uniforme entre CLIs distintos. En su issue #10, un HOME aislado sin credenciales **puntuaba 0.0 en silencio** → owl necesita un gate "¿llegó al modelo?". No incluye Claude Code |
| **intent-as-a-service/harness-bench** https://github.com/intent-as-a-service/harness-bench | 0 | Congela prompt, snapshot, modelo y hash de config; rechaza checkouts con cambios sin commitear; **corre los brazos intercalados** para equilibrar el prompt cache | Verificación ejecutable + proceso + juez LLM ciego opcional | Wilson, Fisher exacto, Mann-Whitney | Intercalar brazos; hash de configuración |
| **roboco-io/coding-agent-benchmark** https://github.com/roboco-io/coding-agent-benchmark | 2 | Modelo × harness sobre una tarea greenfield (backend RealWorld); sin Docker | Suite Hurl oficial (154 requests) + revisión humana | Éxito con presupuesto, costo, tiempo, iteraciones | Su EXP-008 encontró que **quitar hooks y el CLAUDE.md global** fue decisivo para terminar la tarea: la config del usuario contamina |
| **skillgrade** https://github.com/mgechev/skillgrade | 716 | Docker; Claude, Codex, Gemini, agentes custom | Graders deterministas (JSON 0–1) + rúbricas LLM, ponderados | Pass rate con presets de 5/15/30 trials | Formato simple de graders mixtos |
| **Terminal-Bench 2.0** https://www.tbench.ai | — | Harbor | Estado final del contenedor | Leaderboard por par modelo+agente | El mismo modelo aparece con varios harnesses → el patrón que owl generaliza |
| Factory Agent Arena / arena.ai | — | Mismo prompt a dos agentes | Voto humano, Bradley-Terry | Ranking | Solo para calidad percibida; código no público |

## 2. Harbor: la base recomendada

**Qué es:** el runner oficial de Terminal-Bench 2.0 (harbor-framework/harbor, 5,555★, activo: último push 2026-09-24).

**Formato de tarea** (https://docs.harborframework.com/core-concepts/tasks/overview.md):
```
my-task/
├── instruction.md        # lo que ve el agente
├── task.toml             # configuración (timeouts, recursos…)
├── environment/          # Dockerfile o docker-compose
├── solution/solve.sh     # oráculo
└── tests/test.sh         # verificador → /logs/verifier/reward.txt o reward.json
```
- `reward.json` admite **recompensas multi-dimensionales**, así cada criterio de owl sale como un campo.
- Hay tareas multi-step (`steps/`, cada una con su instrucción y sus tests), útiles para metodologías por fases.
- La doc no dice explícitamente si los tests quedan ocultos al agente (**UNVERIFIED**). owl debe comprobarlo en el spike F0; Terminal-Bench prohíbe por regla meter tests u oráculo en la imagen.

**Agentes custom** (https://docs.harborframework.com/core-concepts/agents/custom-agents.md):
- `BaseInstalledAgent`: Harbor instala y corre el CLI **dentro** del entorno. Métodos: `name()`, `install(environment)`, `run(instruction, environment, context)`.
- `BaseAgent`: el loop del agente corre **fuera** y controla el entorno. Métodos: `name()`, `setup()`, `run()`, `version()`. Sirve para "agentes custom" propios.
- Invocación sin registro: `harbor run -t <task> -a modulo:Clase --ak clave=valor --ae VAR=valor -m <modelo>`.

**Qué hace hoy el adaptador `claude-code`** (código fuente revisado: https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/claude_code.py):
- Pone `CLAUDE_CONFIG_DIR={logs}/sessions`, un directorio limpio por trial. ✅ bueno para el baseline.
- Comando: `claude --verbose --output-format=stream-json [--settings <path>] --print`.
- **No usa `--bare`, `--setting-sources` ni `--plugin-dir`.** Un `.claude/` o `CLAUDE.md` dentro del repo de la tarea **sí se carga**.
- Inyecta skills en `$CLAUDE_CONFIG_DIR/skills/` y MCP en `$CLAUDE_CONFIG_DIR/.claude.json`; opcionalmente un directorio de memoria.
- Opciones: `max_turns`, `reasoning_effort`, `max_budget_usd`, `permission_mode` (default `bypassPermissions`), `allowed_tools`/`disallowed_tools`, `append_system_prompt`, `memory_dir`…
- Métricas: tokens (in/out/cache) y costo (usa `total_cost_usd` del stream, con LiteLLM como respaldo) en `FinalMetrics`.
- **Falta, y owl lo agrega:** una subclase que suba el directorio del harness y añada `--plugin-dir`, un comando de init por variante y `--bare` opcional.

**Otros puntos a favor:**
- 40+ agentes integrados (codex, opencode, gemini-cli, cursor-cli, aider, cline-cli, copilot-cli, goose, openhands…).
- 25+ backends de sandbox (docker, podman, daytona, e2b, modal…).
- Trayectorias en formato ATIF con subagentes.
- Visor `harbor view`.

**Qué le falta a Harbor** (el aporte de owl):
1. Variantes declarativas de harness.
2. Gate de contaminación.
3. Estadística pareada para N variantes.
4. Reporte comparativo.

No vi un reporte comparativo entre N brazos: **UNVERIFIED**, el visor está organizado por job y trial.

## 3. Alternativas descartadas como base (y por qué)

| Opción | Por qué no como base | Cuándo sí |
|---|---|---|
| **Inspect AI + inspect_swe** https://meridianlabs-ai.github.io/inspect_swe/claude_code.html | `claude_code()` no tiene parámetros de settings, plugins ni `.claude/`, y sobrescribe `~/.claude/settings.json` para su bridge | Si hiciera falta contabilidad uniforme vía su bridge de modelo, o sus scorers |
| **`claude plugin eval`** https://code.claude.com/docs/en/plugin-evals | No carga `CLAUDE.md` ni `.claude/` del proyecto; sin graders de código propio; solo plugins | Para tests unitarios de activación de un skill concreto |
| **promptfoo** https://www.promptfoo.dev/docs/guides/evaluate-coding-agents/ | Usa el Agent SDK, no la CLI completa. Que cargue los mismos hooks, skills y settings que la CLI es UNVERIFIED | Evals de prompts o skills sueltos |
| **Runner propio desde cero** | Reimplementa sandbox, adaptadores y trayectorias ya resueltos (roboco quedó sin Docker; skills-benchmarks solo cubre Claude Code) | Solo si Harbor bloqueara algo crítico en el spike F0 |

## 4. Aislamiento de Claude Code según la documentación oficial

| Mecanismo | Qué hace (cita o resumen de la doc) | Fuente |
|---|---|---|
| `--bare` | "skip auto-discovery of hooks, skills, custom commands, subagents, plugins, MCP servers, auto memory, and CLAUDE.md". Lo que haga falta se re-agrega con flags: `--settings`, `--mcp-config`, `--agents`, `--plugin-dir`, `--append-system-prompt`. "`--bare` is the recommended mode for scripted and SDK calls, and will become the default for `-p` in a future release." **Requiere `ANTHROPIC_API_KEY`**: no lee OAuth ni keychain | https://code.claude.com/docs/en/headless · https://code.claude.com/docs/en/cli-reference |
| Sin `--bare` | "`-p` loads the same context an interactive session would, including anything configured in the working directory or `~/.claude`". Corre hooks y MCP del proyecto **sin diálogo de confianza** | https://code.claude.com/docs/en/headless |
| `CLAUDE_CONFIG_DIR` | "Override the configuration directory (default: `~/.claude`). All settings, session history, and plugins are stored under this path." | https://code.claude.com/docs/en/env-vars |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | Desactiva la auto memory | https://code.claude.com/docs/en/env-vars |
| `DISABLE_AUTOUPDATER=1` + instalar versión fija | Recomendado para builds reproducibles (`npm install -g @anthropic-ai/claude-code@X.Y.Z`) | https://code.claude.com/docs/en/devcontainer |
| `--strict-mcp-config` | "Only use MCP servers from `--mcp-config`, ignoring all other MCP configurations" → si se usa sin `--mcp-config`, **la variante corre sin sus MCP** | https://code.claude.com/docs/en/cli-reference |
| `--setting-sources` | Documentado (user, project, local), pero el issue abierto **#87590** reporta que con `project` igual se cargan `~/.claude/CLAUDE.md` y `rules/`. **No confiar en él para aislar** | https://github.com/anthropics/claude-code/issues/87590 |
| Managed settings | `/etc/claude-code/managed-settings.json` tiene **la precedencia más alta**: hay que auditar que la imagen no lo traiga | https://code.claude.com/docs/en/devcontainer · https://code.claude.com/docs/en/settings |
| Sandbox | Para correr sin supervisión (`--dangerously-skip-permissions`): contenedor, VM o sandbox runtime; **se niega a correr como root** | https://code.claude.com/docs/en/sandbox-environments |
| `--permission-prompts none` | En corridas desatendidas deniega lo que pediría aprobación y quita `AskUserQuestion` (v2.1.259+) | https://code.claude.com/docs/en/headless |
| `CLAUDE_CODE_DISABLE_PLUGINS` | **No aparece** en la doc oficial de variables de entorno → no usar | https://code.claude.com/docs/en/env-vars |

**Receta recomendada:**
1. Contenedor efímero, usuario no-root, versión de Claude Code fijada y `DISABLE_AUTOUPDATER=1`.
2. `HOME` y `CLAUDE_CONFIG_DIR` vacíos y nuevos por trial (lo que ya hacen Harbor y Quorum).
3. Fixture sin `.claude/` ni `CLAUDE.md` salvo el `CLAUDE.md` base del paciente, idéntico para todas las variantes.
4. Cada variante agrega lo suyo **solo por su manifiesto**.
5. **Gate automático** sobre `system/init`: plugins, `plugin_errors`, `mcp_servers`, `mcp_server_errors`.
6. Gate de "¿hubo al menos una llamada exitosa al modelo?".

## 5. Observabilidad por corrida

**stream-json** (https://code.claude.com/docs/en/headless):
- `system/init`: modelo, herramientas, MCP, plugins cargados y errores.
- Mensajes de subagentes identificados por `parent_tool_use_id`; con `--forward-subagent-text` también su texto.
- `system/api_retry`: reintentos, con categoría de error.
- Mensaje final `result`: `total_cost_usd` con desglose por modelo (estimación del cliente), `permission_denials`.

**OpenTelemetry** (https://code.claude.com/docs/en/monitoring-usage):
- Se activa con `CLAUDE_CODE_ENABLE_TELEMETRY=1` más los exporters OTLP.
- `claude_code.token.usage` y `claude_code.cost.usage` traen `type` (input/output/cacheRead/cacheCreation), `model`, `query_source` (main/subagent/auxiliary), `agent.name`, `skill.name`, `plugin.name`, `mcp_server.name`.
- **Ojo:** los plugins, skills y MCP de terceros aparecen como `"third-party"`/`"custom"`. **No se puede atribuir el costo a un harness por nombre de plugin**; se atribuye por brazo con `OTEL_RESOURCE_ATTRIBUTES=arm=<id>,task=<id>,trial=<n>`, que se agrega a todas las métricas.
- Evento `claude_code.tool_result`: `tool_name`, `success`, `duration_ms`, `error_type`.

**Uniformidad entre CLIs distintos:** el patrón del usage-proxy de Qihoo (§1) o ccusage (https://github.com/ryoppippi/ccusage, lee logs de varios CLIs; que respete `CLAUDE_CONFIG_DIR` es UNVERIFIED).

## 6. Cómo reportar N variantes

- **Por defecto:** tasa de éxito con **estadística pareada**, cuando todas las variantes corren las mismas tareas con un verificador absoluto. Holm para comparaciones múltiples. Pasarlo a un ranking tipo Elo desperdicia información, porque descarta los empates.
- **Bradley-Terry** (el modelo de Chatbot Arena https://arxiv.org/abs/2403.04132 y Copilot Arena https://arxiv.org/abs/2502.09328) **solo** para señales de preferencia (juez que compara dos diffs por calidad) o diseños incompletos. Inferencia propia a partir de esas fuentes.
- **Vistas:**
  1. Heatmap tarea × variante.
  2. Frontera de Pareto costo/éxito con intervalos en ambos ejes (AI Agents That Matter).
  3. Matriz de diferencias pareadas con p ajustado.
  4. Desglose de costo por `query_source` (main/subagent).
  5. Radar solo como resumen visual.
