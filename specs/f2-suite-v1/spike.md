# F2 — Suite v1 — Spike T0

Evidencia recogida el 2026-09-24 para decidir los fallbacks de D5 y D13, y el supuesto de
`JobConfig` de "Supuestos a verificar en el spike T0" (`design.md`). Cambios de código: spike-grade,
listados abajo; T1–T2 los endurecen o los rehacen.

## Costo real gastado

- Check 4 (2 trials Haiku, `vanilla-default` + `navori`, k=1): **$0.2659** (`$0.0528 + $0.2131`,
  `owl gate` output). Presupuesto: ~$0.40. Checks 1–3: $0 (oracle, nop, `harbor run` con agentes sin
  modelo, y un container aparte sin agente).

## Check 1 — Agente no-root (D5)

**Cambios:**
- `tasks/00-smoke/task.toml`: agrega `[agent] user = "node"`.
- `tasks/00-smoke/environment/Dockerfile`: después del commit fixture, escribe
  `/var/lib/owl/baseline` (root, 0444) con el SHA de `refs/owl/baseline`, y `chown -R node:node /app`.

**Evidencia:**
- Campo confirmado en el Harbor 0.23 instalado: `harbor/models/task/config.py:342-346`
  (`AgentConfig.user: str | int | None`, "Username or UID to run the agent as"). El equivalente en
  `VerifierConfig.user` está en la línea 565.
- `harbor run -p tasks/00-smoke -a oracle -k 1` (gratis, sin `--env-file`) con el `task.toml` ya
  editado: `reward=1, f2p=1, p2p=1` — el pipeline sigue funcionando con el agente en `node`.
- `harbor run -p tasks/00-smoke -a nop -k 1`: `reward=0` (nop no toca nada, sigue en verde como
  antes).
- Contenedor construido a partir de `tasks/00-smoke/environment/Dockerfile` (`docker build`), probado
  directo con `docker run -u node`:
  - `touch /app/testfile` → exit 0 (el agente sí puede escribir `/app`).
  - `echo x > /var/lib/owl/baseline` → **Permission denied** (el agente no puede reescribir el
    registro).
- **Hallazgo no anticipado por el diseño** (afecta baseline_valid, no a D5 en sí): con `docker run`
  (sin `-u`, root, como corre hoy el verifier de `00-smoke`) contra el mismo contenedor —
  `chown -R node:node /app` deja el árbol de trabajo de `/app` con dueño `node` — `git rev-parse` como
  root falla con `fatal: detected dubious ownership in repository at '/app'` (protección nativa de
  git desde 2.35.2, activada porque el UID que corre git difiere del dueño del árbol). Esto es
  exactamente la regla de D6.2 ("todo lo que lee o ejecuta estado del agente corre como `node`"; root
  solo agrega resultados) — el spike confirma que D6.2 no es defensivo, es **obligatorio**: el
  `test.sh` actual de `00-smoke` (sin `owl-lib.sh`/`runuser`, fuera del alcance de T0) corre como root
  y por eso el pipeline actual mide `baseline_valid=0` con el agente ya no-root; T1 lo corrige.
- `owl.agents.claude_code_harness.ClaudeCodeHarness.run` (spike): agrega, después de
  `git update-ref refs/owl/baseline HEAD` (como agente), una relectura de la ref como agente y una
  reescritura de `/var/lib/owl/baseline` **como root** (`exec_as_root`), validando hex-40 antes de
  escribir. Probado end-to-end en el trial real `navori` del check 4 (abajo): `exceptions=0`,
  `reward=1` — si el paso root hubiera fallado, `_exec` habría lanzado `RuntimeError` y el trial
  habría terminado en excepción, no en `reward=1`.

**Decisión D5: se usa el agente no-root + registro root** (la ruta preferida del diseño), **sin
fallback**. `claude-code` corre completo como `node`; el install del harness `navori`
(`init`/`render`) también corrió como `node` sin fricción (check 3). `codex` no se probó (F5, fuera
del alcance de F2 — `owl/cli.py` ya rechaza `harness.init` para `codex`).

## Check 2 — `JobConfig`: mismo `import_path`, distintos `kwargs`; directorio `cheat/`

**Evidencia:**
- `harbor/models/job/config.py:427`: `agents: list[AgentConfig]` — sin validación de unicidad de
  `import_path` en `JobConfig` ni en `AgentConfig` (`harbor/models/trial/config.py:63-66`).
- Agente descartable `probe_agent.py` (scratchpad, no viaja al repo) con `options_model` propio
  (`label: str`), y un `JobConfig` YAML con dos entradas `agents:`, mismo
  `import_path: probe_agent:ProbeAgent`, `kwargs: {label: alpha}` / `{label: beta}`.
  `harbor run -c job.yaml` (gratis, agente sin modelo) produjo **2 trials en directorios separados**
  (`00-smoke__5vHbWty`, `00-smoke__M39DerB`), cada uno con su `config.json` reflejando el kwarg
  correcto (`label: beta` / `label: alpha` respectivamente) — Harbor no colapsa ni confunde las dos
  entradas.
- `harbor run -p tasks/00-smoke -a nop -k 1` con un directorio extra `tasks/00-smoke/cheat/` (con
  `hardcode.sh` de prueba, canary incluido) corrió sin error: `reward=0` como cualquier nop — Harbor
  ignora el directorio fuera de su contrato (`instruction.md`, `task.toml`, `environment/`, `tests/`,
  `solution/`).

**Decisión JobConfig: un solo job**, con una entrada `agents:` por ataque de `CheatAgent` (mismo
`import_path`, `kwargs.attack` distinto) más una para `nop`, tal como D9/D8 ya proponían. Sin fallback
necesario. El directorio `cheat/` de D8 coexiste con el resto de la tarea sin que `owl validate` deba
excluirlo de nada.

## Check 3 — `navori init --yes` + `render --apply` sobre un `CLAUDE.md` base (D13)

**Evidencia (gratis, dentro de un container `node:22-bookworm-slim` + `git ca-certificates curl
procps`, como usuario `node`, sin Docker de Harbor):**
- Fixture de prueba: `/app/CLAUDE.md` con una línea centinela única
  (`OWL_T0_SENTINEL_MARKER_9f3a1c`) + `package.json` + `git init` con un commit.
- `npx --yes navori@0.10.0 init --yes --cwd /app`:
  - Detecta `CLAUDE.md: presente` → **"uso modo 'coexist' (seguro)"**.
  - Termina con *"archivos existentes intactos. Corre 'navori render --apply' cuando quieras."*
    (mensaje `doneExistingUntouched`, igual a lo que `design.md` cita de
    `packages/cli/src/lib/i18n.ts`).
- `npx --yes navori@0.10.0 render --apply --cwd /app`:
  - Escribe `.claude/` completo (agentes, skills, hooks, `settings.json`), `.mcp.json`,
    `navori.config.json`, `progress/`.
  - `CLAUDE.md` pasa de 78 a 9824 bytes, y `OWL_T0_SENTINEL_MARKER_9f3a1c` **sigue presente**
    (`grep` la encuentra en la línea 2, sin modificar).
  - `.mcp.json` registra `engram` (`"engram": {"command": "engram", "args": [...]}`).
  - Todo el árbol queda con dueño `node` (corrió como `node` de punta a punta, sin `exec_as_root`).

**Decisión D13: se usa la ruta preferida** (`init --yes` + `render --apply`, sin mover `CLAUDE.md`).
No hace falta el fallback. `variants/navori.yaml#harness.init` se actualiza con `render --apply
--cwd /app` y una verificación centinela mínima de spike (`test -d /app/.claude/agents`, `grep -q
'"engram"' /app/.mcp.json`) que corta con exit 1 si el install no deja el harness — el tercer check de
D13 (línea centinela del `CLAUDE.md` base) queda para T5, cuando exista un `CLAUDE.md` base real del
paciente `opsdesk` contra el que verificarla; este check 3 ya prueba que el contenido sobrevive.

## Check 4 — Trials reales (Haiku, k=1)

- `uv run owl run -v vanilla-default -t tasks/00-smoke -k 1` → job
  `20260924-180552__00-smoke__vanilla-default__r1`: `reward=1, f2p=1, p2p=1`, `exceptions=0`,
  `cost_usd=0.0528`.
- `uv run owl run -v navori -t tasks/00-smoke -k 1` (con `variants/navori.yaml` ya actualizado, init
  + render + sentinel) → job `20260924-180702__00-smoke__navori__r1`: `reward=1, f2p=1, p2p=1`,
  `exceptions=0`, `cost_usd=0.2131`. El agente corrió como `node` de punta a punta: instaló engram,
  corrió `navori init`/`render` (sentinel en verde, si no el `exec_as_agent` del `init_command`
  hubiera lanzado `RuntimeError` y el trial habría terminado en excepción, no en `reward=1`), movió
  `refs/owl/baseline` y reescribió `/var/lib/owl/baseline` como root sin error.
- `uv run owl gate` sobre un directorio temporal con symlinks a esos dos jobs (no se tocó `jobs/`
  real, que ya los tiene): ambos `PASS`, `navori` reporta `mcp=['engram']`.
- No hubo fallas de infraestructura; no hizo falta ningún reintento.
- `baseline_valid=0` en ambos (esperado, ver el hallazgo del check 1 — corregido en T1, no en T0).
- Costo total: **$0.2659**, dentro del presupuesto de ~$0.40 de `tasks.md`.

## Contradicciones con `design.md`

- Ninguna en D5, D13 ni el supuesto de `JobConfig` — las tres rutas preferidas funcionan tal como el
  diseño las planteaba, sin necesitar ningún fallback.
- Un hallazgo nuevo, no anticipado por `design.md`/el challenge: la protección "dubious ownership" de
  git (root operando sobre un árbol `chown`eado a `node`) es la razón mecánica exacta por la que D6.2
  es obligatorio, no solo prudente — vale la pena citarlo en la justificación de D6 cuando T1 lo
  implemente (ahora mismo D6 ya lo exige, pero sin este mecanismo concreto).

## Decisiones (resumen)

- **D5: se usa el agente no-root (`[agent] user = "node"`) + registro root en
  `/var/lib/owl/baseline`, reescrito por `ClaudeCodeHarness.run` con `exec_as_root`. Sin fallback**
  (el bind mount de solo lectura no hizo falta).
- **D13: se usa la ruta que documenta navori (`init --yes` + `render --apply`), sin mover
  `CLAUDE.md`. Sin fallback.**
- **JobConfig: un solo job**, con una entrada `agents:` por ataque de `CheatAgent` (mismo
  `import_path`, kwargs distintos) — Harbor lo soporta nativamente. El directorio `cheat/` de una
  tarea no rompe nada.

## Archivos tocados (spike-grade, se revisan/rehacen en T1–T5)

- `tasks/00-smoke/task.toml` — `[agent] user = "node"`.
- `tasks/00-smoke/environment/Dockerfile` — registro root del baseline.
- `owl/agents/claude_code_harness.py` — reescritura root de `/var/lib/owl/baseline` tras mover la ref.
- `variants/navori.yaml` — `render --apply` + verificación centinela mínima.
- `specs/f2-suite-v1/spike.md` (este archivo).
- Descartables, no viajan al repo (vivieron en el scratchpad de la sesión): `probe_agent.py`,
  `job.yaml`, el fixture de `CLAUDE.md` del check 3, y las imágenes Docker locales usadas para probar
  (`owl-t0-debug`, `owl-t0-navori-base`, eliminadas al cerrar el spike).
