# Solution — f2 (suite v1)
**Verdict:** pendiente. Lo emite el orchestrator; el challenge ya corrió
(`.claude/progress/challenge_f2.md`: 0 BLOCKER, 3 CONCERN, 7 NOTE) y las decisiones del usuario están
incorporadas.

**Signals:**
- Abstracciones compartidas nuevas: imagen base del paciente, `owl/verifier/lib.sh`, `CheatAgent`.
- Contratos compartidos: `reward.json`, `task.toml [metadata]`, `/var/lib/owl/*`.
- Área crítica: la integridad del grader, de la que depende la validez de todo resultado.
- Decisiones caras de revertir: el repo paciente y la suite, que se congelan antes del pre-registro de
  F3.
- ≥2 enfoques genuinos: el paciente y el canal de R12.

Diseño completo: `specs/f2-suite-v1/design.md`. Este artefacto guarda el razonamiento, las opciones, la
resolución del challenge y lo que queda abierto. Las afirmaciones de "ya existe" están verificadas
contra `origin/main` (`5dbacf0`, igual a HEAD de `feat/f2-suite-v1`).

## Decisiones del usuario (2026-09-24)
1. F3 y el piloto corren en Haiku 4.5.
2. El holdout lo escribe un subagente aislado (sin navori, sin tareas dev; solo el dominio del paciente
   y la categoría). Vive en `holdout/` y nadie lo lee hasta F3. Se elimina el emparejamiento con
   tareas dev y se conserva el reparto en 3 categorías.
3. R2: el canary va en todo archivo de tarea salvo `instruction.md`. El orchestrator ajusta
   `requirements.md`.
4. 15 tareas; la `20` sale primero.
5. navori: la ruta preferida es `init --yes` + `render --apply` (la que el propio navori documenta),
   pendiente del spike. Apartar `CLAUDE.md` queda como fallback. F3 divulga qué ruta se usó.
6. No-root se justifica solo por la integridad del baseline y la separación de privilegios. Los fixes
   de los hallazgos 2 y 3 y R12/R13 son el primer lote después del spike.

## Hallazgos que cambian qué construir

1. **navori no instala su harness sobre un repo con `CLAUDE.md`.**
   - `navori-harness/packages/cli/src/lib/assets/claude-infra.ts::detectClaudeInfra` marca `present`
     si hay `CLAUDE.md`.
   - `packages/cli/src/commands/init.ts::chooseAdoptionMode` con `--yes` devuelve `coexist`, e `init`
     sale con `doneExistingUntouched` antes de `renderInline`.
   - Confirmado sobre `navori@0.10.0` publicado por el challenge (C1).
   - El mismo mensaje (`packages/cli/src/lib/i18n.ts`) indica `navori render --apply` como el paso
     siguiente. De ahí sale la ruta preferida (design D13).
2. **El scope de hoy se puede burlar** (`tasks/00-smoke/tests/test.sh`, bloque "Scope"; confirmado
   por el challenge, N5):
   - Los patrones de `runtime_state` se leen de `/app/.git/info/exclude`, que el agente puede escribir.
   - `ls-files --exclude-standard` respeta cualquier `.gitignore` nuevo del agente.
   - Se corrige con el registro root `/var/lib/owl/ignore` (design D6.3).
3. **El agente puede plantar el reward.**
   - `/logs/verifier` está montado con permisos 0777 durante la fase del agente
     (`harbor/trial/trial.py::Trial._agent_env_mounts`, `harbor/models/trial/paths.py::TrialPaths.chmod_dir`).
   - En tareas de un solo paso, **Harbor nunca lo limpia**: `SingleStepTrial._run_verifier` no llama a
     `Trial._reset_shared_step_verifier_dirs`, que solo existe en el camino multi-step (challenge N1).
   - Además, el `test.sh` actual corre como root los tests de `/app/test`, que el agente puede editar.
   - Se corrige con `owl_begin`/`owl_finish` y la separación de privilegios (design D6).
4. **Harbor rechaza valores no numéricos en `reward.json`**
   (`harbor/verifier/verifier.py::Verifier._parse_reward_json`). SHAs y evidencia van en archivos
   laterales.
5. **VISION §7.1 justifica no-root con un motivo que no aplica** (challenge C2).
   `harbor/agents/installed/claude_code.py::ClaudeCode.run` fija `IS_SANDBOX=1` para que
   `bypassPermissions` funcione como root, y `00-smoke` ya corre como root. No-root se sostiene solo
   por la integridad del baseline y la separación de privilegios del verifier (design D5). La redacción
   de VISION se corrige.

## Resolución del challenge

| Hallazgo | Resolución |
|---|---|
| C1 — el workaround de D13 mide un camino que un usuario real no obtiene | Ruta preferida = el flujo documentado por navori (`init --yes` + `render --apply`). El workaround queda solo como fallback, con divulgación obligatoria en `variants/navori.yaml`, `RULES.md` y el reporte de F3. El issue upstream se abre antes del reporte de F3 (design D13) |
| C2 — motivo equivocado de no-root | Corregido en design D5; VISION §7.1 se corrige (Durable knowledge) |
| C3 — decisiones de requisito como preguntas abiertas | Respondidas por el usuario (Haiku; R2 sin `instruction.md`; ruta de navori). Ya no quedan preguntas `[human]` que cambien qué se construye |
| N1 — Harbor no limpia `/logs/verifier` en tareas de un solo paso | Incorporado a D6.1 como motivo de que `owl_begin` sea indispensable |
| N2 — patrón `exec_as_agent`/`exec_as_root` ya existe; el `init` de navori corre como `node` | D5 cita el precedente. D13 fija que todo el `init` (ruta preferida y fallback) corre como `node` dentro de `init_command`, con la verificación centinela ahí mismo |
| N3 — `FROM` de imagen local verificado | Pasa de supuesto a hecho verificado (D3); se quita de los riesgos |
| N4 — `node:sqlite` y `.ts` sin flag verificados | Sin cambios |
| N5 — el bypass de scope existe hoy | Primer lote después del spike (D15) |
| N6 — la 12 es provisional; el holdout hermano es aislamiento débil | La 12 se marca provisional en el catálogo. El holdout pasa a autoría aislada sin emparejamiento (decisión del usuario, D10) |
| N7 — aritmética de validate y del piloto consistente | Sin cambios |
| Gap: `runuser` sin verificar | Verificado: `/usr/sbin/runuser` en `node:22-bookworm-slim`. `pkill` no viene en la imagen; lo aporta `procps` en la imagen base |

## Problem

Hoy solo hay dos tareas (`00-smoke`, `01-probe`) que validan la tubería pero no discriminan entre
variantes. Además, el verifier depende de estado que el agente puede reescribir:
- `refs/owl/baseline`;
- `.git/info/exclude`;
- `/logs/verifier`;
- los tests visibles.

F2 tiene que entregar una suite de 15 tareas válida por construcción, resistente a trampas y barata de
correr, con un presupuesto chico de tokens y de tiempo. El consumidor es la ronda 1 (F3, en Haiku):
toda conclusión de owl hereda la validez de estas tareas.

## What already exists

- **Formato de tarea y sellado de git:** `tasks/00-smoke/environment/Dockerfile` hace commit único,
  `refs/owl/baseline`, `reflog expire` y `gc`. Se extiende a `patient/seal.sh`, más registro root y
  `chown`.
- **Scope contra baseline, fail-closed si falta la ref:** `tasks/00-smoke/tests/test.sh`. Se extrae a
  `owl/verifier/lib.sh` conservando la semántica. No alcanza tal cual por los hallazgos 2 y 3.
- **Baseline post-install y `runtime_state`:**
  `owl/agents/claude_code_harness.py::ClaudeCodeHarness.run`. Se extiende con la escritura root del
  registro. Hoy `runtime_state` solo se aplica dentro de la rama `init_command`.
- **Gate con buckets:** `owl/gate.py::check_trial` y `TrialGate.category`. El patrón existente
  `solution_hidden == 0` → `contamination` es el que sigue `baseline_valid` (R13).
- **Corrida intercalada y modelo default Haiku 4.5:** `owl/cli.py::cmd_run` y `DEFAULT_MODELS`, que ya
  es el modelo de F3. Falta `--suite`, `--holdout` y una tabla por tarea.
- **Agentes sin modelo como base del `CheatAgent`:** `harbor/agents/nop.py::NopAgent` y
  `harbor/agents/oracle.py::OracleAgent`.
- **Usuario por fase:** `harbor/models/task/config.py::AgentConfig.user` y `VerifierConfig.user`; se
  aplican en `Trial._prepare` y `Trial._run_agent_phase`. `ClaudeCode.install` y `Codex.install` ya
  instalan como el usuario del agente y escalan con `exec_as_root`.
- **Varios agentes por job:** `harbor/models/job/config.py::JobConfig.agents` es una lista.
- **Imagen:** `node:22-bookworm-slim` v22.23.3 trae `node:sqlite` y `.ts` sin flag, el usuario `node`
  (uid 1000) y `/usr/sbin/runuser`.
- **Costos medidos:**
  - `jobs/oracle-00-smoke`: 16 s; `jobs/nop-00-smoke`: 14 s.
  - `jobs/20260924-153003__00-smoke__vanilla-default__r1`: 60 s y $0.04 con Haiku, de los que 21.3 s
    son el install de Claude Code.
- **Materia prima del paciente:**
  - `../harness-test/sin-harness`: sin rastros de navori, 5 ADRs de invariantes.
  - `../harness-test/con-harness`: trae `.claude/` de navori 0.8.7, `CLAUDE.md` gestionado,
    `navori.config.json`, `.mcp.json` y `progress/`.

## Constraints

- **Del usuario:** presupuesto chico de tokens y de tiempo, tareas de un solo contenedor, Docker
  local (D8 de VISION §12), Haiku para el piloto y F3.
- **Privacidad:** privado (D10 de VISION §12); canary (R2, sin `instruction.md`).
- **Grader:** determinista y oculto (VISION §3.3); aislamiento verificable (§3.8); holdout escrito de
  forma independiente (§3.7, §14.6).
- **Base:** Harbor 0.23 sin forks.
- **Repo:** lo más simple y el patrón existente.

## Decision drivers

1. **Costo y tiempo por trial.** Domina: 450 trials en F3 y ~180 en cada validación.
2. **Validez del grader frente a un agente que hace reward hacking.** Si falla, invalida todo.
3. **Riesgo de contaminación:** de entrenamiento, de sesgo hacia un harness y del autor sobre el
   holdout.
4. **Realismo suficiente para que los harnesses se diferencien.**
5. **Mantenimiento** por una sola persona.
6. **Patrón existente** como un driver más, no como ganador por default.
7. **Representar cada variante como la instala un usuario real,** o declarar la diferencia (C1).

## Options

### Decisión 1 — Repo paciente

| Criterio | (a) IncidentHub tal cual | (b) RealWorld/Conduit | (c) Sintético desde cero | **(d) Híbrido `opsdesk`** |
|---|---|---|---|---|
| Costo por trial | Alto: Postgres sidecar y ~15k LOC para explorar | Medio-alto: casi todas las implementaciones usan Postgres o Mongo | Bajo | Bajo |
| Realismo para diferenciar | Alto | Medio | Medio: invariantes sin probar | Medio-alto: invariantes de los ADRs de `sin-harness` |
| Contaminación | `con-harness` carga texto de navori; `sin-harness` está limpio | **Alta y estructural** | Mínima | Mínima |
| Mantenimiento | Alto | Medio | Todo propio | Igual que c, con menos diseño |

- **(d) sobrevive.** (c) queda dominada por (d).
- **(a) descartada:** costo por trial; la variante `con-harness` además sesga.
- **(b) descartada:** la contaminación no tiene arreglo.
- **IncidentHub portado a SQLite conservando el código:** descartado; hereda ~15k LOC y el frontend.

### Decisión 2 — Integridad del baseline (R12)

**A. Agente no-root y registro root en el contenedor (recomendado).**
- No depende del agente: vale igual para oracle, nop, codex y cheat.
- Habilita la separación de privilegios del verifier. Esa, y no el modo de permisos, es su
  justificación (C2).
- Costo: el spike y un `chown` en el sellado. Reversión barata.

**B. Bind mount de solo lectura desde el host.**
- Resiste incluso a un agente root, pero solo lo escriben las clases de owl.
- **Fallback.**

Descartadas:
- Modo `separate`: no ve el commit post-install.
- `--ve` con `${VAR}` del proceso Harbor: estado global mutable.
- SHA determinista del fixture: no cubre el post-install.

### Decisión 3 — Agente tramposo (R10)
`BaseAgent` scripted, un ataque por trial, que ataca como el usuario del agente. Tabla en design D8.

Descartadas:
- Todos los ataques en un solo trial: se enmascaran entre sí.
- Agente LLM "tramposo": cuesta tokens y R11 exige correr sin modelo.

### Decisión 4 — `owl validate`, holdout
Dos `JobConfig` de Harbor: ~180 trials, ~12–15 min.

Holdout con autoría aislada (decisión del usuario), en `holdout/` más metadata, guard que falla
cerrado y revisión solo mecánica.

Descartadas:
- Un `harbor run` por trial: ~45 min.
- Holdout "hermano de tarea dev" escrito por el mismo autor: es el aislamiento débil que señaló N6.

### Decisión 5 — Piloto
`owl run --suite -v vanilla-default -k 2` en Haiku más `owl summary`, con la regla de decisión
basada en transcripts (design D12). Al ser el modelo de F3, lo observado vale para la ronda, dentro de
lo poco que dice k = 2.

Alternativa: k = 4 secuencial en las tareas marcadas. Se usa solo si los transcripts no resuelven una
marca.

### Decisión 6 — Instalación de navori sobre el paciente (R1, C1)

**A. `init --yes` + `render --apply` (preferida).**
- Es el flujo que el propio navori indica tras `coexist` (`i18n.ts`, `doneExistingUntouched`).
- No toca el `CLAUDE.md` base.
- Pendiente de que el spike confirme dos cosas: que genera `.claude/` + `.mcp.json` y que conserva el
  contenido base.

**B. Apartar `CLAUDE.md` y reinsertarlo (fallback).**
- Pegamento propio de owl. Obliga a divulgarlo en F3.

Descartadas:
- `coexist` sin render: la variante corre sin harness.
- Esperar el fix upstream antes de F2: bloquea sin necesidad. El issue se abre de todos modos antes
  del reporte de F3.

## Recommendation
- Paciente (d) e integridad A.
- `CheatAgent` scripted con 6 ataques y validate con 2 `JobConfig`.
- Holdout de autoría aislada en `holdout/`.
- Piloto k = 2 en Haiku, cuyo papel declarado es la humareda y el costo.
- navori por la ruta A, con B como fallback declarado.
- 15 tareas: 12 dev con catálogo en design y 3 slots holdout definidos solo por categoría.
- Secuencia (design D15): spike → integridad del verifier en `00-smoke` (hallazgos 2 y 3, R12, R13) →
  paciente → validate → tareas dev → holdout → piloto.

## Boundaries & contracts
Ver design "Contracts".
- **Cambian de forma:**
  - `reward.json` de `00-smoke`: `tests_touched` pasa a `tests_modified` + `tests_added`; se agregan
    `verifier_complete` y dimensiones. Ningún consumidor lee `tests_touched`.
  - `task.toml [metadata]` agrega `owl_reward`, `owl_holdout`, `owl_target_dimension` y `owl_promise`
    (vacío en el holdout).
- **Aparece un contrato nuevo:** `/var/lib/owl/{baseline,ignore}`.
- **Aparece un contrato de autoría:** `docs/task-authoring.md`, el único documento de la spec que ve
  el autor del holdout.

## Failure modes
Tabla completa en design. Las que pueden cambiar el plan:
1. Que no-root rompa algún agente: fallback B de la Decisión 2.
2. Que `render --apply` no instale o pise el `CLAUDE.md` base: fallback B de la Decisión 6, con
   divulgación.
3. Que el autor del holdout se contamine: brief cerrado y revisión solo mecánica.

## Testing strategy
Ver design. El spike T0 va primero porque decide los fallbacks de las Decisiones 2 y 6; el resto de las
pruebas responde cada una a un riesgo nombrado.

## NOT in scope
Ver design:
- allowlist de red;
- preámbulo D7;
- Claude Code preinstalado;
- caché y pool de validate;
- F3 y F4 (incluida la redacción de la divulgación de navori en el reporte);
- `AGENTS.md` para Codex;
- migrar `01-probe`;
- piloto o lectura del holdout antes de F3.

## Open questions

**[human]** Ninguna que cambie qué se construye. Las 5 anteriores quedaron respondidas.

**[repo]** Se resuelven en el spike T0 (design "Supuestos"):
- No-root para `claude-code`, `codex` y el `init` de navori.
- Qué hace `navori render --apply` con un `CLAUDE.md` existente: si genera `.claude/` y `.mcp.json`
  con engram, y si conserva el contenido base.
- `JobConfig` con el mismo `import_path` repetido y distintos `kwargs`.
- Que Harbor tolere `cheat/` en la tarea.

**[assumed]**
- El modelo de amenaza es un modelo con shell sin privilegios que hace reward hacking; no escapes del
  contenedor.
- El nombre `opsdesk` es provisional.
- El paciente se escribe sin el harness de navori activo, o al menos pasa el check "sin `navori` en
  `patient/`".
- El agente conserva red pública en F2.
- El subagente autor del holdout se puede lanzar sin el `CLAUDE.md` gestionado de owl. Si el host no
  lo permite, el orchestrator lo reporta antes de escribir el holdout.

## Durable knowledge
- **Dominio → `VISION.md` §7:**
  - Corregir §7.1: no-root por integridad del baseline y separación de privilegios, no por el modo de
    permisos (Harbor fija `IS_SANDBOX=1`).
  - Agregar el modelo de amenaza del verifier y la regla "el verifier nunca confía en estado que el
    agente puede escribir".
- **Dominio → `VISION.md` §10:** paciente híbrido, regla de reward (design D7) y protocolo de autoría
  aislada del holdout.
- **Dominio → `VISION.md` §12:** D4 pasa a Haiku (decisión del usuario).
- **`CLAUDE.md`, sección de usuario → "Autoría de tareas":**
  - `reward.json` solo numérico.
  - GUID en todo archivo de tarea salvo `instruction.md`.
  - `owl-lib.sh` se copia, nunca se edita en la tarea.
  - La cadena `navori` no aparece en `patient/`.
  - Nadie abre `holdout/` antes de F3.
- **Upstream `navori-harness`:** issue por el `coexist` de `init --yes` con un `CLAUDE.md` existente,
  antes del reporte de F3.
- **Skill:** ninguna nueva.
