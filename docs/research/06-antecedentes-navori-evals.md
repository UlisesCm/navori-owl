# 06 — Antecedentes: lo que dejó el prototipo navori-evals

> Fecha: 2026-09-23. Auditoría de solo lectura de `../navori-evals` (prototipo A/B de 2 brazos, sin commits,
> 1 sola corrida ejecutada) y `../harness-test` (experimento manual). navori-owl **absorbe** navori-evals: lo
> reutilizable se generaliza a N variantes y el prototipo se archiva (roadmap F1).

---

## 1. Qué hacía navori-evals

- **Ejecución:** `run.sh <task> <variant> <run> [model]` hacía todo esto:
  1. Copiaba `fixture/` a un sandbox fuera del repo (`$TMPDIR/navori-evals-sandboxes/...`).
  2. Hacía `git init` y un commit "fixture".
  3. Corría `variants/<v>.sh <sandbox> <version-file>`.
  4. Hacía un commit "variant installed", que sirve de línea base del diff.
  5. Invocaba `claude -p` con `--setting-sources project,local --strict-mcp-config --permission-prompts none --output-format stream-json --verbose --settings <merged.json>`.
- **Permisos:** un spike demostró que en `-p` sobre un repo no confiable **se ignora el `permissions.allow` del repo, pero los `deny` y los hooks sí aplican**. Por eso la allow-list se pasa por `--settings`, sumando deny explícitos al directorio del laboratorio, `WebSearch` y `WebFetch`.
- **Captura:**
  - `transcript.jsonl`, `stderr.log`, `settings.json`, `diff.patch`, `diff.stat.txt`.
  - `result.json` con el evento `system/init`, el evento `result` (`total_cost_usd`, `duration_ms`, `num_turns`, `permission_denials`), la salida del grader y el `exit_code`.
- **Calificación:** `tasks/<t>/grader/check.sh <sandbox>` corre desde fuera y emite `{success, hidden_tests[], out_of_scope_files[], forbidden_actions[]}`.
- **Reporte:** `report.mjs` excluye las corridas con error (exit ≠ 0, sin evento `result`, `is_error`, grader roto) y muestra, por tarea, corridas, éxitos, tasa, costo por éxito y duración.
- **Regla pre-registrada:** +20 pp de diferencia sin perder por 2 o más en ninguna tarea; aplicada a mano.

## 2. Qué se reutiliza en owl (generalizado)

| Pieza | En owl |
|---|---|
| Contrato `variants/<x>.sh <sandbox> <version-file>` | Se convierte en el **manifiesto de variante** con una sección `install` (comando o script) y `version` fijada |
| Commit "variant installed" como línea base del diff | Igual: el diff del agente se mide contra el estado *después* de instalar la variante, no contra el fixture |
| Guardar `system/init` en el resultado | Pasa a ser el **gate de contaminación** automático |
| `isErrored` (bucket de errores separado de los fracasos) | Igual, con un informe aparte de errores de infraestructura |
| Salida JSON del grader | Se mapea a `reward.json` multi-dimensional de Harbor |
| `RULES.md` pre-registrado | Plantilla para N variantes con estadística pareada (reemplaza el umbral fijo de 20 pp) |

## 3. Qué hay que cambiar (y por qué)

1. **Aislamiento incompleto:** `--setting-sources` no es confiable (issue #87590) y el README ya avisaba que plugins del operador sobrevivían. → `HOME` + `CLAUDE_CONFIG_DIR` efímeros en contenedor.
2. **`--strict-mcp-config` sin `--mcp-config`:** según la doc oficial, descarta todos los MCP que no vengan por `--mcp-config`. Una variante con MCP propios (navori con engram y codegraph, gentle-ai con engram y Context7) **corría sin ellos**. → El manifiesto declara sus MCP y se pasan explícitamente.
3. **Versión del harness sin fijar:** `navori@latest`. → Versión o SHA fijados en el manifiesto y registrados en el resultado.
4. **Veredicto manual:** → automatizado con la estadística de doc 02.
5. **Efectos colaterales en el HOME:** `navori init` se registra en `~/.navori`; gentle-ai y los plugins escriben en `~/.claude`. → HOME desechable.

## 4. Hallazgos del review del prototipo (ya corregidos allí; owl los hereda como requisitos)

- **CRÍTICO — grader alcanzable desde el sandbox:** el sandbox vivía dentro del repo del laboratorio y el agente podía hacer `cat ../../../../tasks/.../check.sh`, además de leer transcripts de otras corridas. → En owl, los tests y graders **nunca** están en el sistema de archivos del agente durante la corrida (Harbor los monta al verificar).
- **ALTO — fallos de infraestructura contados como derrotas.** → Bucket de errores separado.
- **MEDIO — versión no fijada.** → Manifiesto con versión.

## 5. navori-harness como variante (datos para su manifiesto)

- Instalación: `npx navori init --yes --cwd <dir>`. `--recommended` activa gh (si hay remote); `--full` suma tgrep, codegraph, semgrep, jscpd y acli. **Corrección 2026-09-24**: en 0.10.0 `engram` es always-on (se registra con cualquier flag, sin opt-out) — ya no depende de `--recommended`; ver §7 y [upstream #1023](https://github.com/UlisesCm/navori-harness/issues/1023).
- Genera `navori.config.json`, `CLAUDE.md` con bloques gestionados, `.claude/` (8 agentes, 14 skills, 15 hooks, settings) y `.mcp.json`. También genera `AGENTS.md` y config para otros CLIs, que es **un riesgo de contaminación cruzada** si se reutiliza el fixture.
- Registro en `~/.navori` (`packages/cli/.../registry.ts`).
- Métricas propias útiles como proceso: `navori audit` (atribución de tokens y huecos de adherencia).
- Su propia doc ya declara el principio "nunca evaluar el harness sobre sí mismo" (`navori-harness/docs/inspiration.md`), coherente con que owl sea neutral.

## 6. harness-test

La misma app ("IncidentHub": gestión de incidentes multi-tenant, Fastify + Postgres + React) construida dos veces: `con-harness/` (navori 0.8.7) y `sin-harness/`. Cada una tiene un `IMPLEMENTATION_REPORT.md` y ADRs. **No hay documento comparativo ni conclusiones.** Sirve como materia prima para un repo paciente o como ejemplo de tarea greenfield larga con calificación cualitativa.

## 7. Estado de la absorción (F1, 2026-09-24)

| Ítem (§2–§5) | Estado | Detalle |
|---|---|---|
| Contrato `variants/<x>.sh` → manifiesto de variante | **Migrado** | `variants/*.yaml` + `owl/variants.py` (`Variant.load`); `variants/navori.yaml` nuevo, con `harness.init` pineado a `navori@0.10.0` |
| Commit "variant installed" como línea base del diff | **Migrado** | `ClaudeCodeHarness.run` (`owl/agents/claude_code_harness.py`) commitea tras `init_command`; `tasks/00-smoke/tests/test.sh` ya no excluye `.claude/`/`CLAUDE.md`/`AGENTS.md`/`.mcp.json` del scope (esos archivos ya están en HEAD antes de que el agente empiece) |
| Guardar `system/init` → gate de contaminación | **Migrado** (ya existía) | `owl/gate.py::_check_claude_code` |
| `isErrored` (bucket de errores aparte) | **Migrado** | `owl/gate.py::TrialGate.category` (`ok`/`infra`/`contamination`, contamination gana empates), impreso por `owl gate` e incluido en `owl-gate.json` |
| Salida JSON del grader → `reward.json` multi-dimensional | **Migrado** (ya existía) | `tasks/*/tests/test.sh` |
| `RULES.md` pre-registrado (umbral fijo de 20 pp) | **Diferido a F3** | Reemplazo por estadística pareada (doc 02 §3.4); hasta entonces no hay veredicto automático multi-variante |
| Informe de buckets de error (`report.mjs` con `isErrored`) | **Diferido a F4** | El bucket ya existe (`category` arriba); falta la vista agregada tipo `report.mjs` sobre N jobs |
| Fixture `00-smoke` (`hello.txt`) | **Descartado** | El `00-smoke` de owl (`tasks/00-smoke`) es un bugfix real con F2P/P2P ocultos (`node --test`), estrictamente más fuerte que el smoke test original — no hay nada que migrar |
| Workaround `--settings` con allow-list (`variants/base-allow.json`) | **Descartado — moot** | Harbor's `ClaudeCode` agent corre con `--permission-mode=bypassPermissions` por default (confirmado en `harbor/agents/installed/claude_code.py:88`). Bajo `bypassPermissions`, las **allow rules no tienen efecto** y las **deny rules sí bloquean en todo modo, incluido bypassPermissions**; los hooks `PreToolUse` también corren en todo modo, incluido bypassPermissions, y un hook que devuelve `deny` bloquea la tool igual (verificado en docs.claude.com/en/docs/claude-code/permission-modes y .../hooks-guide, 2026-09-24). Es decir: el problema que resolvía el allow-list (que se ignorara `permissions.allow`) no existe bajo `bypassPermissions` porque el allow-list nunca se usa ahí; lo que sí sigue aplicando son los `deny` y los hooks, igual que en el spike original de navori-evals (§1) |
| Docs 01–03 (benchmarks, metodología, behavior evals) + `power.py` | **Migrado** (ya existía) | `docs/research/01-benchmarks-publicos.md`, `02-metodologia.md`, `03-evals-de-comportamiento.md` son reescrituras en español, más cortas, del contenido de navori-evals; `docs/research/power.py` es el mismo simulador (misma semilla, misma lógica de `signflip_p`/`power`) con JSDoc-equivalente y crédito de origen agregado en el docstring (diff rápido 2026-09-24 contra `navori-evals/docs/research/{01,02,03,power.py}` confirma que es una migración, no una copia pendiente) |
| navori-harness como variante (datos de manifiesto, §5) | **Migrado, con hallazgo nuevo — resuelto 2026-09-24** | `variants/navori.yaml`; el `--recommended activa engram` de §5 estaba desactualizado — en 0.10.0 `engram` se registra siempre (`--yes` alcanza), sin flag para desactivarlo (§5 corregido). El binario no está en `node:22-bookworm-slim`, y `navori init` **nunca corre el install del `externalTool`** por sí mismo: `packages/cli/src/commands/init.ts:372` solo advierte binarios faltantes bajo `--full` (y ni ahí instala; `--yes` no advierte nada) — confirmado leyendo la fuente de `navori-harness`, no asumido. Corrección de una nota previa de esta misma sección: el script Linux que sí publica `navori@0.10.0` en su `plugin.json` (verificado con `npm pack navori@0.10.0`, `externalTool.install.linux`) resuelve el asset vía `releases/latest` de la API de GitHub y verifica `checksums.txt` — **funciona** (confirmado resolviendo `engram_2.1.0_linux_arm64.tar.gz` con él); la URL `raw.githubusercontent.com/.../scripts/install.sh` que se reportó como 404 pertenece a una versión vieja cacheada del plugin (`engram` plugin.json v0.0.2) y no es la que usa navori 0.10.0. `variants/navori.yaml#harness.init` **no reutiliza ese script**: pinea `v2.1.0` de `Gentleman-Programming/engram` en vez de `releases/latest`, por reproducibilidad (un release nuevo no debe poder mover silenciosamente qué corre el trial) — mismo mecanismo (tarball `linux_${arch}` + `checksums.txt`, `sha256sum -c` obligatorio), extraído a `$HOME/.local/bin` (mismo directorio que Harbor antepone al PATH para `claude`, sin root). Verificado gratis en un contenedor `node:22-bookworm-slim` igual al Dockerfile de `00-smoke`: `engram --version` → `engram 2.1.0`, `engram mcp --tools=mem_search` arranca y sale limpio. También se confirmó (cita en `variants/navori.yaml`) que `claude -p` headless carga los servidores de `.mcp.json` del proyecto **sin pedir aprobación**, así que la ausencia de `enableAllProjectMcpServers`/`enabledMcpjsonServers` en el `.claude/settings.json` que genera navori no es un problema aparte. Seguimiento upstream: [navori-harness#1023](https://github.com/UlisesCm/navori-harness/issues/1023) (que `init` instale el `externalTool` de plugins always-on, no solo advierta bajo `--full`). Ver comentarios completos de `variants/navori.yaml` |
| `harness-test` (IncidentHub, §6) | **Diferido, sin fecha** | Sigue sin documento comparativo; se deja como materia prima para una tarea greenfield larga, no hay owner en el roadmap actual |
