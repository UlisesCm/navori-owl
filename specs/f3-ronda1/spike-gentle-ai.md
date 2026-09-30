# Spike de gentle-ai v3.7.0 en `owl-patient:local` (T11, R6)

Spike gratis y sin modelo: sin token OAuth, sin `claude` real, sin llamadas a la API de Anthropic. Todo corrió
en un contenedor local desechable (`docker run -d --name owl-t11 --entrypoint sleep owl-patient:local infinity`,
imagen `86c1d3ff0504`, arm64) como el usuario `node` (uid 1000, sin `sudo`), el mismo lanzamiento que usa
`tests/test_validate_docker.py`. Fecha: 2026-09-30. El contenedor se borró al terminar.

## Resumen de decisiones para T12

| Punto | Resultado |
|---|---|
| Binario | `v3.7.0`, checksum `sha256sum -c` OK (§1) |
| Hooks | quedan en `/app/.claude/settings.json` (§4) |
| Tabla tal cual / puente B / HOME | §5: proyecto (`/app`) tal cual; `~/.claude/settings.json` (permisos) por puente B; plugin y MCP de engram por `CLAUDE_CONFIG_DIR` + puente, **pendiente de confirmar con `claude` real** (§5, §11) |
| `/logs/agent/sessions` | `node` la crea y escribe durante `install()` (emulación fiel a Harbor, §6) |
| Telemetría | `disabled (source: GENTLE_AI_TELEMETRY)`; el hook `Stop` corrido a mano sale sin enviar (con control positivo, §7) |
| Privilegios | ninguno; sin `sudo`; `go` ausente sin efecto (§8) |
| engram | `2.2.1` bajado de `releases/latest`, no fijado; un `engram` ya presente en `PATH` se respeta (§9) |
| Persona / SDD / RDD | `gentleman`; SDD `single`, store `openspec`; RDD `on` por default (§10) |
| Artefactos | `odd/` y `openspec/`; `.atl/` es estado del harness (§12) |

## Método y límites

- `/app` de la imagen base **no está sellada** (sin `.git`, propiedad de `root`): con ella el primer intento de
  instalar falló con `permission denied` al crear `/app/.mcp.json` (evidencia en §3). Un task real hereda de
  `owl-patient:local` y corre `/opt/owl/seal.sh`, que hace `chown -R node:node /app` y el commit baseline. El
  spike corrió `seal.sh` como `root` dentro del contenedor para reproducir esa condición.
- `claude` **no está instalado** en la imagen. En un trial real, `ClaudeCodeHarness.install` corre
  `super().install()` (instala Claude Code) **antes** del `init_command` (`owl/agents/claude_code_harness.py:140-156`),
  así que `claude` sí estará en `PATH` durante `gentle-ai install`. Para no bajar Claude Code ni gastar nada, el
  spike hizo dos corridas: (A) sin `claude` en `PATH` y (B) con un stub `claude` que registra sus argumentos y
  sale 0. Lo que el `claude` real escribiría en `~/.claude*` con esas llamadas **no se pudo comprobar** (causa:
  no hay binario de Claude Code en la imagen y bajarlo queda fuera de la red permitida); se declara en §5 y §11.
- Red usada por el propio instalador (no por el spike): `git clone` de `gentleman-guardian-angel` a
  `/tmp/gentleman-guardian-angel` y descarga del binario de engram desde GitHub. No se envió telemetría.
- `/logs/agent` no existe en la imagen; lo crea Harbor al levantar el trial. Se emuló (§6).
- Receta ejecutada, reutilizable en T12 (salvo el stub): `recipe.sh` del scratchpad de la sesión, transcrita en §2.

## 1. Descarga y verificación del binario

```
$ B=https://github.com/Gentleman-Programming/gentle-ai/releases/download/v3.7.0
$ curl -fsSL -O $B/gentle-ai_3.7.0_linux_arm64.tar.gz -O $B/checksums.txt
$ grep linux checksums.txt
a730a61a43758f04cc9a4ac644945cc0e8652a1e33d6997a0a3d3f0044d2fff5  gentle-ai_3.7.0_linux_amd64.tar.gz
a3a3d3a974f3d9b67d935fe9e306ae83c305da4ec1baed4a5319c10b044cd0eb  gentle-ai_3.7.0_linux_arm64.tar.gz
$ grep " gentle-ai_3.7.0_linux_arm64.tar.gz$" checksums.txt | sha256sum -c -
gentle-ai_3.7.0_linux_arm64.tar.gz: OK
$ tar -xzf gentle-ai_3.7.0_linux_arm64.tar.gz gentle-ai && install -m 0755 gentle-ai ~/.local/bin/gentle-ai
$ gentle-ai version
gentle-ai 3.7.0
```

El tarball trae `gentle-ai`, `LICENSE`, `README.md`, `contracts/` y `docs/review-integration.md`; no trae
`docs/telemetry.md`. La firma `checksums.txt.minisig` no se verificó (D3: exigiría `minisign` en la imagen).

## 2. Receta usada

```bash
export PATH="$HOME/.local/bin:$PATH"; mkdir -p "$HOME/.local/bin"
# (corrida B) stub claude: registra "claude $*" en /tmp/claude-calls.log y sale 0
B=https://github.com/Gentleman-Programming/gentle-ai/releases/download/v3.7.0
case "$(uname -m)" in x86_64) A=amd64;; aarch64|arm64) A=arm64;; esac
curl -fsSL -O "$B/gentle-ai_3.7.0_linux_$A.tar.gz" -O "$B/checksums.txt"
grep " gentle-ai_3.7.0_linux_$A.tar.gz\$" checksums.txt | sha256sum -c -
tar -xzf "gentle-ai_3.7.0_linux_$A.tar.gz" gentle-ai
install -m 0755 gentle-ai "$HOME/.local/bin/gentle-ai"
cd /app
export GENTLE_AI_TELEMETRY=0
gentle-ai install --agent claude-code --preset full-gentleman --scope workspace
```

## 3. `--dry-run` y la instalación real

Sin sellar `/app` (imagen base tal cual), la instalación real falla:

```
$ cd /app && GENTLE_AI_TELEMETRY=0 gentle-ai install --agent claude-code --preset full-gentleman --scope workspace
Error: execute install pipeline: inject context7 for "claude-code": merge context7 into "/app/.mcp.json": create temp file for "/app/.mcp.json": open /app/.gentle-ai-1840838034.tmp: permission denied
EXIT=1
```

Con `/app` sellada (`docker exec -u root owl-t11 /opt/owl/seal.sh`), `--dry-run` desde `/app`:

```
$ gentle-ai install --agent claude-code --preset full-gentleman --scope workspace --dry-run
AI Gentle Stack dry-run
Agents: claude-code
Unsupported agents: none
Persona: gentleman
Preset: full-gentleman
Components order: claude-theme,context7,persona,engram,gga,opencode-gentle-logo,permissions,sdd,skills
Auto-added dependencies: none
Platform decision: os=linux distro=debian package-manager=apt status=supported
Prepare steps: 2
Apply steps: 10
Dependencies: git v2.39.5, curl v7.88.1, node v22.23.3, npm v10.9.9, go NOT FOUND (optional)
EXIT=0
```

El dry-run **no** deja nada en `/app` (`git status --short --ignored` sin cambios) pero **sí** escribe en `$HOME`
(`~/.gentle-ai/state.json`, `state.json.lock`) y npm deja `~/.npm/_logs/*` y `_update-notifier-last-checked`
(`npm --version` interno).

Instalación real (corrida A, sin `claude`; corrida B con stub arrojó el mismo `EXIT=0`, 5 s):

```
$ GENTLE_AI_TELEMETRY=0 gentle-ai install --agent claude-code --preset full-gentleman --scope workspace
engram: claude CLI not found in PATH — install Claude Code first: https://docs.anthropic.com/en/docs/claude-code   (solo corrida A)
... (git clone de gentleman-guardian-angel v2.10.1 -> /tmp/gentleman-guardian-angel; gga instalado en ~/.local/bin)
Verification checks: 82 passed, 0 failed, 0 warnings, 0 skipped
You're ready. Run `claude` and start building.
The engram binary was installed to /home/node/go/bin via `go install`.     (mensaje engañoso: el binario quedó en ~/.local/bin, ver §9)
EXIT=0
```

## 4. Archivos escritos en `/app` y hooks

`git status --short` tras instalar: `?? .claude/` y `?? .mcp.json` (más `.atl/`, ver abajo). `git diff --stat` vacío:
**`/app/CLAUDE.md` y `/app/AGENTS.md` no se tocan** (`grep -c opsdesk-conventions-sentinel` = 1 en ambos; la
línea centinela sigue intacta).

76 archivos nuevos (476 709 bytes) en `/app`:

| Ruta | Archivos |
|---|---|
| `.claude/CLAUDE.md` | 1 (bloque `gentle-ai:persona`, contrato SDD, RDD) |
| `.claude/settings.json` | 1 (hooks y `outputStyle`) |
| `.claude/output-styles/gentleman.md` | 1 |
| `.claude/agents/` | 19 (`sdd-*`, `review-*`, `jd-*`) |
| `.claude/commands/` | 11 (`gentle-sdd-*.md`) |
| `.claude/skills/` | 41 (`_shared/`, `sdd-*`, `skill-registry`, `chained-pr`, `judgment-day`, `go-testing`, …) |
| `.claude/mcp/engram.json` | 1 (`{"command":"engram","args":["mcp","--tools=agent"]}`; **no es una ubicación que Claude Code cargue**) |
| `.mcp.json` | 1 (solo `context7`: `npx -y --package=@upstash/context7-mcp@2.2.5 -- context7-mcp`) |

Hooks, confirmados en `/app/.claude/settings.json` (Claude Code lo carga como settings del proyecto):

```
$ cat /app/.claude/settings.json   (resumen; salida completa: PreToolUse, SessionStart, Stop, SubagentStop, UserPromptSubmit)
PreToolUse[Agent]        gentle-ai sdd-preflight-hook --agent claude-code
SessionStart             gentle-ai review stop-hook --agent claude-code
Stop                     gentle-ai review stop-hook --agent claude-code ;  (async) gentle-ai telemetry runtime claude --json
SubagentStop  (async)    gentle-ai telemetry runtime claude --json
UserPromptSubmit         gentle-ai skill-registry refresh --quiet --no-gitignore --cwd "${CLAUDE_PROJECT_DIR:-$PWD}" || true
"outputStyle": "Gentleman"
```

Los hooks invocan `gentle-ai` por nombre: en el run debe estar en `PATH` (`~/.local/bin`, que Harbor antepone,
`claude_code.py:139-141`).

Escrituras posteriores a la instalación (hooks corridos a mano desde `/app`):

```
$ gentle-ai skill-registry refresh --quiet --no-gitignore --cwd /app          # hook UserPromptSubmit
new: .atl/.skill-registry.cache.json  .atl/skill-registry.md                  # git status: ?? .atl/  (no ignorado)
$ echo '{"hook_event_name":"SessionStart","cwd":"/app","session_id":"x"}' | gentle-ai review stop-hook --agent claude-code
new: /home/node/.gentle-ai/review-stop-hook/v1/x.json                         # en $HOME, no en /app
$ echo '{"tool_name":"Agent","cwd":"/app"}' | gentle-ai sdd-preflight-hook --agent claude-code    # exit 0, sin escrituras
```

## 5. Archivos escritos en `$HOME` y tabla {tal cual | puente B | HOME}

`find $HOME -type f` antes/después de la instalación (sin `.npm/`), corrida B:

```
/home/node/.claude/settings.json          /home/node/.claude/themes/gentleman.json   /home/node/.claude/themes/gentleman-cute.json
/home/node/.config/gga/{config,AGENTS.md} /home/node/.local/share/gga/lib/{cache,pr_mode,providers}.sh
/home/node/.local/bin/{engram,gga}        /home/node/.engram/protocol-mode.json  ({"claude-code":"slim"})
/home/node/.gentle-ai/{state.json,state.json.lock,backups/<id>/manifest.json}
```

`~/.claude.json` **no existe** tras la instalación (corridas A y B). `~/.gentle-ai/telemetry.json` **no** se
crea con `GENTLE_AI_TELEMETRY=0` en la instalación (aparece solo al correr `telemetry status`).

`~/.claude/settings.json` contiene solo `permissions`: `defaultMode: "bypassPermissions"` más 24 reglas `deny`
(`Bash(rm -rf /)`, `Read(.env)`, `Read(.ssh/*)`, `Edit(**/*.pem)`, …).

Llamadas que gentle-ai hace al `claude` (stub, `/tmp/claude-calls.log`):

```
claude plugin marketplace add Gentleman-Programming/engram
claude plugin install engram
claude mcp add --transport stdio --scope user engram -- /home/node/.local/bin/engram mcp --tools=agent
claude mcp remove engram --scope user
claude plugin list --json
warning: could not register Claude Code user MCP server (/home/node/.claude.json): verify ... mcpServers.engram is absent
```

Prueba con `CLAUDE_CONFIG_DIR=/tmp/cfg_c HOME=/tmp/hm_c` (`gentle-ai install` en un workspace de scratch):

```
warning: could not register Claude Code user MCP server (/tmp/cfg_c/.claude.json): ...
hm_c/.claude/settings.json  hm_c/.claude/themes/*.json      # los escritos por gentle-ai siguen en $HOME/.claude
cfg_c/                                                      # vacío (el stub no escribe)
```

Corrige la afirmación "gentle-ai nunca lee `CLAUDE_CONFIG_DIR`" (design.md D3, challenge C1) solo en parte: el
**verificador del registro MCP** sí resuelve la ruta con `CLAUDE_CONFIG_DIR`, y el `claude` que él invoca lo
heredaría; lo que gentle-ai escribe por sí mismo (`settings.json`, temas) sigue yendo a `$HOME/.claude`.

**Decisión** (evidencia arriba; lo marcado "no comprobado" depende de un `claude` real):

| Qué | Dónde queda | Decisión |
|---|---|---|
| `/app/.claude/**`, `/app/.mcp.json` (hooks, persona, agentes, comandos, skills, output style, context7) | proyecto | **tal cual** (Claude Code los carga como proyecto; `-p` carga los MCP de proyecto sin pedir, nota de `variants/navori.yaml`) |
| `/app/.claude/mcp/engram.json` | proyecto, ubicación no cargada | **tal cual**, sin efecto; no cuenta como MCP activo |
| `~/.claude/settings.json` (`permissions`: `deny` de `.env`, `.ssh`, claves; `defaultMode`) | `$HOME/.claude` | **puente B**: fusionar en `$OWL_CLAUDE_CONFIG_DIR/settings.json` (`defaultMode` ya es `bypassPermissions` por default de Harbor, `claude_code.py:84-88`; lo que aporta son las reglas `deny`) |
| plugin `engram` y MCP de usuario de engram (`claude plugin install`, `claude mcp add --scope user`) | `$CLAUDE_CONFIG_DIR` o `~/.claude*` según el entorno del `init`; **no comprobado** (stub) | exportar `CLAUDE_CONFIG_DIR=$OWL_CLAUDE_CONFIG_DIR` al `gentle-ai install` para que el `claude` real escriba ahí; si el `claude` real escribiera en `~/.claude*`, puente B para `mcpServers` de `~/.claude.json` y `~/.claude/plugins/` (D3 solo cubría `settings.json` y `.claude.json`). Confirmar en T12/T21 |
| `~/.claude/themes/*.json` | `$HOME/.claude` | **no se puentea**: la config no los referencia (solo `outputStyle`, que va en proyecto); no cambian el comportamiento sin TUI |
| `~/.gentle-ai/` (estado, backups, `review-stop-hook/v1/*.json`) | `$HOME` | **HOME**: se queda; los hooks del run usan el mismo `HOME` real, por eso H (correr con `HOME` remapeado) queda descartado |
| `~/.config/gga`, `~/.local/share/gga`, `~/.local/bin/{gga,engram}`, `~/.engram/` | `$HOME` | **HOME**: herramientas, no configuración cargable por Claude |

## 6. `/logs/agent/sessions` escribible por `node` durante `install()`

`/logs/agent` no existe en la imagen. Harbor lo crea y le hace `chmod 777` al levantar el trial
(`environments/docker/docker.py:1011-1018` → `ensure_dirs(...)`, `environments/base.py:554` `chmod 777`). Emulado
como Harbor y probado como `node`:

```
$ docker exec -u root owl-t11 bash -c 'mkdir -p /logs/agent /logs/verifier && chmod 777 /logs/agent'
$ docker exec -u node owl-t11 bash -c 'ls -ld /logs/agent; mkdir -p /logs/agent/sessions && echo ok-mkdir; echo x > /logs/agent/sessions/probe && echo ok-write; ls -ld /logs/agent/sessions; id -un'
drwxrwxrwx 1 root root 0 Sep 30 15:54 /logs/agent
ok-mkdir
ok-write
drwxr-xr-x 1 node node 10 Sep 30 15:55 /logs/agent/sessions
node
```

`/logs/agent/sessions` **no** existe hasta que alguien la crea (`run()` la crea en `setup_command`,
`claude_code.py:1838`); durante `install()` el `init` debe hacer `mkdir -p "$OWL_CLAUDE_CONFIG_DIR"` antes del
puente. No comprobado: el montaje real de Harbor (se emuló; su confirmación va en el smoke T21).

## 7. Telemetría

Con la variable en el entorno:

```
$ GENTLE_AI_TELEMETRY=0 gentle-ai telemetry status
telemetry: disabled (source: GENTLE_AI_TELEMETRY)
$ env -u GENTLE_AI_TELEMETRY gentle-ai telemetry status        # control
telemetry: enabled (source: default)
```

Hook `Stop` (`gentle-ai telemetry runtime claude --json`) corrido a mano con un payload sintético
(`{"session_id":"s1","transcript_path":"/tmp/fake/t.jsonl","cwd":"/app","hook_event_name":"Stop"}` por stdin;
transcript de una línea, sin modelo). Para probar que "sale sin enviar" se apuntó
`telemetry.gentlemanprogramming.com` a `127.0.0.1` (`/etc/hosts` del contenedor) con un listener TCP en `:443`
que registra conexiones; nada sale a Internet. `HOME=/tmp/h2` es un `HOME` de scratch ya enrolado (`trigger` x2):

```
control positivo  (trigger, sin variable):  telemetry trigger: sent_install  -> listener conns: 1
Stop hook, HOME=/tmp/h2, sin variable:      {"decision":"discarded"}         -> listener conns: 1
Stop hook, HOME=/tmp/h2, GENTLE_AI_TELEMETRY=0:  {"decision":"disabled"} exit=0  -> listener conns: 0
Stop hook, HOME real,    GENTLE_AI_TELEMETRY=0:  {"decision":"disabled"} exit=0  -> listener conns: 0
trigger x2, GENTLE_AI_TELEMETRY=0:          telemetry trigger: disabled (source: GENTLE_AI_TELEMETRY) -> listener conns: 0
review stop-hook, GENTLE_AI_TELEMETRY=0:    exit=0, listener conns: 0
```

Un intento previo con `HTTPS_PROXY` sobre un listener local no capturó ni el control (gentle-ai no usa el proxy del
entorno), por eso se cambió a la técnica de `/etc/hosts`. Sin la variable y con un `HOME` limpio el estado es
`enrollment_pending` (`telemetry policy --json`): la primera ejecución solo muestra el aviso, no envía.

## 8. Privilegios pedidos

Ninguno. `id` = `uid=1000(node)`, `which sudo` vacío, y la instalación terminó `EXIT=0` con 82 verificaciones en
verde. El instalador reporta la plataforma como `apt` soportada pero no intentó instalar paquetes del sistema
(no hay `sudo`; sin efecto observable). `go` no está en la imagen y es opcional: el mensaje "installed via
`go install`" es solo texto; el binario de engram llegó por descarga (§9). Escribe solo bajo `/app`, `$HOME`
y `/tmp` (`/tmp/gentleman-guardian-angel`, clon de `gga` v2.10.1).

## 9. Versión de engram

```
$ engram version
engram 2.2.1
$ ls -la ~/.local/bin
-rwxr-xr-x 1 node node 19464376 engram   (bajado por el instalador; el binario de gentle-ai contiene "releases/latest")
```

- Se instala `engram 2.2.1` de `releases/latest` (no fijado; `variants/navori.yaml` fija `2.1.0`): entre corridas
  de la ronda puede cambiar. Un `engram` ya presente en `PATH` se respeta: con un stub `engram` que imprime
  `engram 2.1.0` en `~/.local/bin`, `gentle-ai install` terminó `EXIT=0` y no lo sobrescribió (tamaño 78 bytes).
  T12 puede fijar la versión preinstalando engram como hace `navori.yaml`.
- No se pudo determinar qué versión "espera" `v3.7.0`: hay un aviso `unable to verify the Claude Code Engram plugin
  supports --protocol=slim (requires plugin 0.1.1+)` (corrida B; con el stub `claude plugin list` devuelve vacío),
  y `~/.engram/protocol-mode.json` = `{"claude-code":"slim"}`. Si `2.1.0` cumple `slim` no se comprobó.

## 10. Persona, modo SDD y RDD resultantes

- **Persona:** `gentleman` (`~/.gentle-ai/state.json`: `"persona": "gentleman"`; `outputStyle: "Gentleman"` en
  `/app/.claude/settings.json`; bloque `<!-- gentle-ai:persona -->` en `/app/.claude/CLAUDE.md:1-33`). Efecto sobre
  el paciente: la persona ordena "Never use cat/grep/find/sed/ls. Use bat/rg/fd/sd/eza instead" y esas
  herramientas **no existen** en la imagen (`which bat rg fd sd eza` → rc=1); se declara como parte de medir
  gentle-ai con sus defaults.
- **Modo SDD:** `single`. No se pasó `--sdd-mode`; `install`, `--sdd-mode single` y `--sdd-mode multi` producen
  árboles idénticos para `claude-code` (`diff -r /tmp/ws_default /tmp/ws_single` y `/tmp/ws_multi`: sin
  diferencias). `gentle-ai sdd-status`: `store: openspec`, `planning_home: /app/openspec`, `next: sdd-new`.
- **RDD:** `on` por default. `gentle-ai review mode status --cwd /app` →
  `receipt-driven development: on (decided by default)`, `global: unset`, `clone-local: unset`. El contrato en
  `/app/.claude/CLAUDE.md:425-430` lo describe "on by default and opt-out" y prohíbe apagarlo/encenderlo solo.
- **Seguimiento:** para trabajo sustancial la persona/orquestador ordena crear `odd/tasks/<feature>.md` antes del
  primer write (`.claude/CLAUDE.md:370,411`).

## 11. No comprobado

- Lo que el `claude` real escribe con `plugin install engram` / `mcp add --scope user` (y si lo hace bajo
  `CLAUDE_CONFIG_DIR`): en este spike solo hubo stub, porque no había Claude Code en la imagen. La
  comprobación con `claude` real se difirió y se hizo en el smoke de T21 (`specs/f3-ronda1/smoke.md`): la
  instalación real carga el plugin `engram` y el MCP de usuario `engram`, y `.mcp.json` agrega `context7`
  (ver `expect` en `variants/gentle-ai.yaml`). El test Docker
  `tests/test_validate_docker.py::test_gentle_ai_install_on_patient` cubre la instalación sobre el paciente.
- El montaje real de `/logs/agent` por Harbor (emulado con las llamadas de `environments/base.py`).
- La firma minisign del release (no verificada por diseño, D3).
- Compatibilidad de `engram 2.1.0` con `--protocol=slim`.

## 12. Rutas de artefactos más estrechas (insumo de T14)

| Prefijo | Quién lo escribe | Evidencia | Propuesta |
|---|---|---|---|
| `odd/` (estrecho: `odd/tasks/`) | orquestador, antes del primer write | `/app/.claude/CLAUDE.md:370,411` (`odd/tasks/<feature-name>.md`; espejo en engram `odd/<feature-name>/tasks`) | `artifacts`: `odd/` según D3 (T14 decide si basta `odd/tasks/`) |
| `openspec/` | fases SDD (`sdd-init` → `openspec/config.yaml`; `sdd-propose/spec/design/tasks/verify/archive` → `openspec/changes/<change>/…`, `openspec/specs/…`) | store por default `openspec` (`gentle-ai sdd-status`); rutas en `.claude/skills/sdd-*/SKILL.md` | `artifacts`: `openspec/` (no está en el manifiesto de D3: **agregar**) |
| `.atl/` | hook `UserPromptSubmit` (`skill-registry refresh`) en cada prompt: `.atl/skill-registry.md`, `.atl/.skill-registry.cache.json` | corrida de §4; aparece como `?? .atl/` tras el baseline | `runtime_state` (estado propio del harness), **no** `artifacts` (R9) |

`docs/`, `.claude/` y la raíz no aparecen como destino del flujo por default. Nota de riesgo: las skills
`sdd-*` mencionan `specs/…` en algunos pasajes (p. ej. `specs/{capability}/spec.md`); el store por default es
`openspec`, así que no se declara.
