# 04 — Catálogo inicial de harnesses (variantes candidatas)

> Fecha de corte: 2026-09-23. Estrellas y última actividad verificadas con `gh repo view` ese día; métodos de
> instalación tomados de los README/docs oficiales de cada repo. **UNVERIFIED** = no confirmado en fuente primaria.

**Esto es un catálogo abierto, no una lista cerrada de rivales.** navori-owl mide *cualquier* harness o
agente. Entra una variante nueva cuando alguien escribe su manifiesto (ver `VISION.md` §5). Este documento
lista los candidatos que motivaron el proyecto y otros populares en 2026, con lo necesario para instalarlos
de forma aislada y reproducible, y para diseñar tareas que pongan a prueba lo que cada uno promete.

---

## 1. Cómo identificar a qué se refiere cada nombre

| Nombre coloquial | Proyecto real | Confianza |
|---|---|---|
| "Gentleman Programming harness" | **Gentleman-Programming/gentle-ai**. Su antecesor `agent-teams-lite` está archivado y redirige a gentle-ai. `engram` es solo su capa de memoria | Alta |
| "superpower(s)" | **obra/superpowers** (Jesse Vincent / Prime Radiant) | Muy alta |
| "ponytails" | **DietrichGebert/ponytail** (singular) | Alta |
| "navori" | **navori-harness** (CLI `navori`, v0.9.0) https://github.com/UlisesCm/navori-harness | — |

## 2. Tabla principal

| Harness | ★ (2026-09-23) | Qué es | Instalación headless | Dónde escribe |
|---|---|---|---|---|
| **Claude Code vanilla** | — | El producto sin nada agregado | — | — |
| **navori-harness** https://github.com/UlisesCm/navori-harness | 1 | Agentes (orchestrator, architect, implementer, reviewer, scout, auditor…), 14 skills, 15 hooks, bloques gestionados de CLAUDE.md, MCPs opcionales (engram, codegraph) | `npx navori init --yes --cwd <dir>` (`--recommended` / `--full` agregan plugins). Para fijar versión: `NAVORI_SPEC=<tarball>` | Proyecto (`.claude/`, `CLAUDE.md`, `.mcp.json`, `navori.config.json`) **+ registro en `~/.navori`** |
| **gentle-ai** https://github.com/Gentleman-Programming/gentle-ai | 7,206 | Binario Go que configura el agente: orquestador SDD con subagentes, skills, Engram (MCP), Context7 (MCP), persona | `go install github.com/gentleman-programming/gentle-ai/v3/cmd/gentle-ai@vX.Y.Z` y luego `gentle-ai install --agent claude-code --preset full-gentleman --persona gentleman --scope workspace` ([usage](https://github.com/Gentleman-Programming/gentle-ai/blob/main/docs/usage.md), [non-interactive](https://github.com/Gentleman-Programming/gentle-ai/blob/main/docs/non-interactive.md)) | Por defecto `~/.claude`; con `--scope workspace` escribe en el proyecto, pero las integraciones "global-only" siguen siendo globales. Engram usa `~/.engram/engram.db` |
| **superpowers** https://github.com/obra/superpowers | 290,784 | Plugin de skills: brainstorming, writing-plans, TDD, subagent-driven-development, systematic-debugging, code review + hook SessionStart | Clonar en un SHA fijo y pasar `--plugin-dir`. Alternativa: `/plugin install superpowers@claude-plugins-official` | Plugin (scope user por defecto) |
| **ponytail** https://github.com/DietrichGebert/ponytail | 145,104 | Skill de minimalismo (escalera YAGNI → reusar → stdlib → nativo) + 2 hooks Node + `ponytail-mcp` | Clonar en un SHA fijo y pasar `--plugin-dir`. Alternativa: `/plugin marketplace add DietrichGebert/ponytail` + `/plugin install ponytail@ponytail`. Requiere `node` | Plugin |
| **oh-my-claudecode** https://github.com/Yeachan-Heo/oh-my-claudecode | 39,326 | Orquestación multi-agente (`/autopilot`, `/ralph`, `/team`), workers en tmux con Codex/Gemini | Plugin + `/omc-setup`, o `npm i -g oh-my-claude-sisyphus` + `omc setup` | `.claude/omc.jsonc` o `~/.config/claude-omc/` |
| **Ruflo** (ex claude-flow) https://github.com/ruvnet/ruflo | 73,163 | Enjambres de agentes, MCP con ~300 herramientas, daemon, memoria vectorial | `npx ruflo init` (el camino por plugin no instala hooks) | UNVERIFIED |
| **SuperClaude** https://github.com/SuperClaude-Org/SuperClaude_Framework | 23,904 | ~30 slash commands `/sc:*`, agentes, "modes", MCP opcionales | `pipx install superclaude && superclaude install` | UNVERIFIED (probablemente `~/.claude`) |
| **BMAD Method** https://github.com/bmad-code-org/BMAD-METHOD | 53,400 | Metodología ágil con agentes-rol | `npx skills add bmad-code-org/BMAD-METHOD …` o el plugin; requiere `uv` | UNVERIFIED |
| **GitHub Spec Kit** https://github.com/github/spec-kit | 138,612 | Spec-driven development: constitution → specify → plan → tasks → implement | `uv tool install specify-cli && specify init <dir>` (el flag exacto para Claude es UNVERIFIED) | Proyecto |
| **GSD Core** https://github.com/open-gsd/gsd-core | 9,800 | Ciclo Discuss → Plan → Execute con subagentes (sucesor de get-shit-done) | `npx @opengsd/gsd-core@latest`, con instalador interactivo global/local | Se elige |
| **claude-mem** https://github.com/thedotmack/claude-mem | 94,568 | Memoria persistente entre sesiones (rival de Engram) | Plugin | UNVERIFIED |
| **caveman** https://github.com/JuliusBrussee/caveman | 107,589 | Estilo terso. ponytail lo usa como **placebo de estilo** | Plugin | Plugin |

## 3. Riesgos para la ejecución automática (headless, `claude -p`)

| Harness | Riesgo | Mitigación recomendada |
|---|---|---|
| superpowers | brainstorming pregunta "qué quieres hacer" y espera que el humano apruebe el diseño y diga "go" | Preámbulo estándar **igual para todas las variantes**: "el diseño está aprobado; procede sin pedir confirmación". También cabe una tarea multi-paso donde un "usuario simulado" responda (patrón Quorum, doc 05) |
| gentle-ai | Sin flags abre un TUI; su fase de revisión pide un "acknowledgement" humano | Instalar con flags (en non-TTY "auto-declines — never hangs"); fijar el modo SDD; mismo preámbulo |
| oh-my-claudecode | Su README pide no usar `/autopilot`, `/ralph` ni `/team` en CI | Usar sus comandos `omc ...` o evaluarlo solo en modo normal |
| BMAD / Spec Kit / GSD | Metodologías por fases con revisión humana entre fases | Tareas multi-paso de Harbor, una invocación por fase, o documentar que se evalúa "fase implement con spec dada" |
| Memorias (engram, claude-mem, Ruflo) | El estado persiste entre corridas y contamina las repeticiones | HOME/DB desechable por trial. Aparte, **tareas multi-sesión a propósito** para medir el valor real de la memoria |
| Instaladores que tocan `~/.claude` | Contaminan al baseline y a otras variantes | Contenedor con HOME y `CLAUDE_CONFIG_DIR` efímeros por trial (doc 05 §4) |

## 4. Lo que afirma cada uno → qué tarea lo pone a prueba

| Harness | Afirma | Evidencia propia publicada | Tarea que lo pone a prueba |
|---|---|---|---|
| ponytail | −54% LOC, −22% tokens, −20% costo, −27% tiempo, 100% "safe" | Sí: 18 tareas, Haiku 4.5, n=4, 4 brazos incluido el placebo caveman ([resultados](https://github.com/DietrichGebert/ponytail/blob/main/benchmarks/results/2026-06-18-agentic.md)). Solo un modelo | Trampas de sobre-ingeniería; seguridad por exploits |
| superpowers | TDD real, trabajo autónomo de horas, verificación antes de declarar éxito | Tiene lab de evals ([superpowers-evals / Quorum](https://github.com/prime-radiant-inc/superpowers-evals)); resultados en reportes autenticados, no públicos | Bug con causa raíz oculta; exigir test que falle primero; reward hacking |
| gentle-ai | Memoria entre sesiones, "keep small work small", trabajo verificable | E2E deterministas del CLI, no de calidad ([doc](https://github.com/Gentleman-Programming/gentle-ai/blob/main/docs/testing-agents-deterministically.md)) | Feature multi-sesión que depende de una decisión previa; tarea trivial (sobrecosto) |
| navori-harness | Orquestación con reviewer, guards contra acciones destructivas, quality gates | No publicada (`navori bench` solo mide latencia de render; `navori audit` da atribución de tokens) | Acciones destructivas, scope, convenciones, review |
| SDD (Spec Kit, BMAD, GSD, gentle-ai SDD) | Mejor resultado en features grandes con spec | No encontrada | Feature grande cross-package con spec |
| Todos | — | — | **Tarea trivial de una línea**: mide el costo fijo del proceso |

## 5. Notas de aislamiento específicas de plugins (docs oficiales)

- `--plugin-dir <path>` carga un plugin **solo para esa sesión**, sin instalarlo; se puede repetir. Es la vía más limpia para variantes basadas en plugins. https://code.claude.com/docs/en/cli-reference
- `claude plugin install --scope user|project|local`: el scope user (el default) escribe en `~/.claude/settings.json`. El caché de plugins vive bajo el directorio de configuración. https://code.claude.com/docs/en/plugins-reference
- `system/init` en stream-json lista `plugins` cargados y `plugin_errors`: sirve para **verificar que la variante cargó lo que decía** y que el baseline no cargó nada. https://code.claude.com/docs/en/headless
- **Contaminación cruzada:** navori genera `AGENTS.md`; otro harness o CLI podría leerlo. Cada variante parte del mismo fixture limpio y solo agrega lo suyo.
