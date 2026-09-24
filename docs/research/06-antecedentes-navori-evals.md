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

- Instalación: `npx navori init --yes --cwd <dir>`. `--recommended` activa engram (y gh si hay remote); `--full` suma tgrep, codegraph, semgrep, jscpd y acli.
- Genera `navori.config.json`, `CLAUDE.md` con bloques gestionados, `.claude/` (8 agentes, 14 skills, 15 hooks, settings) y `.mcp.json`. También genera `AGENTS.md` y config para otros CLIs, que es **un riesgo de contaminación cruzada** si se reutiliza el fixture.
- Registro en `~/.navori` (`packages/cli/.../registry.ts`).
- Métricas propias útiles como proceso: `navori audit` (atribución de tokens y huecos de adherencia).
- Su propia doc ya declara el principio "nunca evaluar el harness sobre sí mismo" (`navori-harness/docs/inspiration.md`), coherente con que owl sea neutral.

## 6. harness-test

La misma app ("IncidentHub": gestión de incidentes multi-tenant, Fastify + Postgres + React) construida dos veces: `con-harness/` (navori 0.8.7) y `sin-harness/`. Cada una tiene un `IMPLEMENTATION_REPORT.md` y ADRs. **No hay documento comparativo ni conclusiones.** Sirve como materia prima para un repo paciente o como ejemplo de tarea greenfield larga con calificación cualitativa.
