# Auditoría de `artifacts` (T14, R9) — contexto fresco

Auditor: agente `auditor` que no escribió los manifiestos. Commit del repo: `e9dd395` (árbol con `variants/gentle-ai.yaml` sin commitear).
Solo lectura de código y manifiestos; solo se escribe este documento y el handoff.

## Método y fuentes

- **navori**: tag `v0.10.0` de `~/Documents/dev-docs/navori-harness` (`git show`/`git grep v0.10.0 -- …`). No corrí `npx navori@0.10.0 init`: la evidencia es el código fuente del tag y el golden de render (`packages/cli/src/engines/__tests__/__golden__/claude.snap`), no un render nuevo.
- **superpowers**: clon de `https://github.com/obra/superpowers` en el `ref` pineado `5bf4e78011075bcfc0dc295f0724994cd123ee71` (`git describe` → `v6.4.1`).
- **gentle-ai**: clon de `https://github.com/Gentleman-Programming/gentle-ai` en el tag `v3.7.0` (commit `6dee8f83`), contrastado contra `specs/f3-ronda1/spike-gentle-ai.md` §12. Los assets del repo son los que el binario instala en `/app/.claude/`; no reinstalé el binario.
- Mecánica de exclusión (regla 5): `owl/verifier/lib.sh:249-275` compara contra `/var/lib/owl/ignore`; un patrón que termina en `/` excluye por prefijo (`case "$rel" in "$pat"*`). `owl/agents/claude_code_harness.py:229-231` une `runtime_state` y `artifacts` en ese mismo registro, así que un prefijo de `artifacts` oculta cambios igual que uno de `runtime_state`. Por eso el ancho del prefijo importa.
- Guardas existentes: `owl/variants.py:24-42` (`_check_artifact_prefix`: termina en `/`, fuera de `packages/`, sin archivos de `patient/`) y `owl/validate.py:177-205` (`artifacts_clear`). Comprobado que los tres manifiestos cargan con `Variant.load(...)` sin `SystemExit`.
- Contenido de `patient/` relevante: `patient/docs/{api.md,permissions.md,runbooks,sla.md}`, `patient/.gitignore`, sin `.claude/`, `odd/`, `openspec/`, `progress/`, `docs/superpowers/` (`ls -a patient`, `find patient -name odd -o -name openspec -o -name superpowers -o -path '*progress*'` → vacío).

## Tabla de veredictos

Criterios: (1) el flujo documentado escribe ahí; (2) directorio más estrecho; (3) no es estado propio del harness; (4) no es raíz compartida; (5) no oculta archivos del paciente ni `owl/verifier/lib.sh`.

| Prefijo | Variante | Evidencia | Veredicto |
|---|---|---|---|
| `.claude/progress/` | navori | (1) Handoffs escritos por los agentes: `.claude/agents/auditor.md:75,96,98,129` (`audit_deep_*`, `plan_*`, `audit_ticket_*`, `solution_review_*`), `.claude/agents/implementer.md:81` (`impl_<feature>.json`), `.claude/agents/architect.md:29` (`solution_<scope>.md`), `.claude/agents/orchestrator.md:110-120` (lista completa) y `:122` ("`.claude/progress/` is ONLY for ephemeral agent handoffs"); todo en `v0.10.0`, mismo texto en el golden `claude.snap:575`. (2) Ya es el directorio dedicado; no hay subdirectorio más estrecho (los archivos son `<tipo>_<scope>.*` en la raíz del directorio). (3) Lo escriben los agentes; los hooks solo lo leen (`.claude/hooks/subagent-stop-handoff.sh:420-431` recorre `.claude/progress`; `session-start-context.sh:624` lee `current.md`). Excepciones menores: `receipt.txt` y `workplan_*.gate.jsonl` los produce la CLI `navori` a pedido del agente (`orchestrator.md:116,119`), no un hook autónomo. (4) `.claude/` es raíz compartida, pero el prefijo es un subdirectorio propio, no `.claude/`. (5) `patient/` no tiene `.claude/`; el prefijo no toca `owl/`, `tests/` ni `packages/`. | ACEPTADO |
| `progress/` | navori | (1) `orchestrator.md:122` documenta `progress/current.md` e `history.md` en la raíz como estado versionado que escribe el agente; `ephemeral-paths.ts` los distingue del directorio efímero `.claude/progress/`. (2) Ambos archivos comparten `progress/` y no hay prefijo de directorio más estrecho. (3) Los escribe el orquestador, no un hook autónomo. (4) Es un directorio propio, no la raíz compartida. (5) `patient/` no contiene `progress/`; no oculta archivos del paciente ni `packages/`. | ACEPTADO |
| `docs/superpowers/` | superpowers | (1) `skills/brainstorming/SKILL.md:135,241` (specs → `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`); `skills/writing-plans/SKILL.md:18,177,186` (planes → `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`). El manifiesto cita `skills/executing-plans/SKILL.md:329`, que es una línea de un transcript de ejemplo, no la regla de escritura; la cita correcta es `writing-plans/SKILL.md:18`. (2) `git grep -n "docs/superpowers"` (sin tests ni RELEASE-NOTES) solo produce `specs/` y `plans/`: existe un prefijo más estrecho por cada destino documentado. (3) Los escribe el agente (documentos de diseño/plan), no el plugin por sí solo. (4) `docs/` es raíz compartida; `docs/superpowers/` es un namespace del plugin, pero es más ancho de lo necesario. (5) `patient/docs/` no contiene `superpowers/`; sin efecto sobre `packages/`. | ESTRECHAR → `docs/superpowers/specs/` y `docs/superpowers/plans/` |
| `odd/` | gentle-ai | (1) `internal/components/agentguidance/routing.go:49` ("create `odd/tasks/<feature-name>.md` … before the first source write") y `:97`; `docs/usage.md:23`; `docs/intended-usage.md:46`; en el paciente instalado, `/app/.claude/CLAUDE.md:370,411` (spike §12). Aplica a "trabajo sustancial autorizado", no a toda tarea. (2) El único destino documentado en el filesystem es `odd/tasks/<feature>.md`; el espejo `odd/<feature>/tasks` es un tópico de Engram, no una ruta (`routing.go:97`, `usage.md:23`). (3) Lo escribe el orquestador; no es estado del harness. (4) No es raíz compartida. (5) `patient/` no tiene `odd/`; sin efecto sobre `packages/`. | ESTRECHAR → `odd/tasks/` |
| `openspec/` | gentle-ai | (1) `internal/assets/skills/_shared/openspec-convention.md:6-41` (tabla skill → ruta: `config.yaml`, `specs/`, `changes/<change>/{proposal,design,tasks,verify-report}.md`, `specs/<domain>/spec.md`, archivo en `changes/archive/`); `internal/assets/claude/agents/review-*.md:57-58` y `jd-judge-*.md:50` escriben `openspec/changes/{change}/review-ledger.md`; `sdd-archive/SKILL.md:111-127` compone `openspec/specs/<domain>/spec.md`. Store por default `openspec`: `gentle-ai sdd-status` en spike §10 y `internal/sddstatus/status.go:24,278`. (2) El árbol completo lo posee el flujo SDD y mezcla `config.yaml` (archivo), `specs/` y `changes/`: estrechar a `openspec/changes/` + `openspec/specs/` dejaría `openspec/config.yaml` fuera del prefijo (los prefijos son directorios con `/`, `variants.py:29`) y sería un falso positivo de alcance. `openspec/` es el más estrecho que cubre el flujo. (3) Lo escriben las fases SDD (agentes), no el harness por sí solo. (4) No es raíz compartida. (5) `patient/` no tiene `openspec/`; sin efecto sobre `packages/`. Nota: los skills mencionan `specs/{capability}/spec.md` en algunos pasajes (spike §12); no se declara (ver notas). | ACEPTADO |

### Revisión de `runtime_state` (no son prefijos de `artifacts`, pedido explícito)

| Ruta | Variante | Evidencia | Veredicto |
|---|---|---|---|
| `.atl/` en `runtime_state` | gentle-ai | Lo escribe el hook `UserPromptSubmit` `gentle-ai skill-registry refresh --quiet --no-gitignore --cwd "${CLAUDE_PROJECT_DIR:-$PWD}"` (`internal/components/sdd/inject.go:1856,1951,1955`), a `.atl/skill-registry.md` y `.atl/.skill-registry.cache.json` (`internal/skillregistry/registry.go:19-20`); spike §4 (`?? .atl/` tras el baseline). El registro es generado (índice de skills), no una nota del agente: correcto en `runtime_state`, no en `artifacts`. `--no-gitignore` evita que `EnsureATLIgnored` edite `patient/.gitignore` (`registry.go:191-214`, `app.go:424`). | CORRECTO (no pasa a `artifacts`) |
| `.superpowers/` en `runtime_state` | superpowers | Los scripts pineados escriben `.superpowers/sdd/<plan-basename>/` (`sdd-workspace:6,24`; `review-package:8`) y `.superpowers/brainstorm/` (`start-server.sh:9,117-121`). Es estado producido por el plugin, no entregable del agente. Ambos destinos comparten `.superpowers/`; `patient/` no lo contiene. | CORRECTO (no pasa a `artifacts`) |

### Ningún prefijo oculta `packages/`

Ninguno de los cuatro prefijos de `artifacts` ni de las sugerencias de estrechamiento empieza por `packages/` ni es prefijo de `packages/…`; además `_check_artifact_prefix` lo rechaza (`owl/variants.py:29-31`) y `artifacts_clear` impide que `environment/` de una tarea nombre rutas bajo esos prefijos. Los prefijos tampoco cubren `owl/`, `tests/` ni `owl/verifier/lib.sh` (viaja como `tests/owl-lib.sh`).

## Notas por prefijo no aceptado

### `docs/superpowers/` → `docs/superpowers/specs/` y `docs/superpowers/plans/`
- Es correcto y seguro tal como está (no toca `patient/docs/`), pero es más ancho que los dos destinos documentados. El único margen que abre es cualquier archivo futuro que el plugin ponga en `docs/superpowers/` fuera de `specs/` y `plans/`; hoy no hay ninguno en la fuente pineada.
- Corregir la cita del manifiesto: `skills/writing-plans/SKILL.md:18` en vez de `skills/executing-plans/SKILL.md:329` (ejemplo de transcript).
- Al ser dos prefijos, cada uno debe pasar `_check_artifact_prefix` y `artifacts_clear` (`patient/docs/` no los contiene).

### `odd/` → `odd/tasks/`
- Lo documentado solo escribe `odd/tasks/<feature>.md`; el resto de `odd/` no tiene autor en el flujo. `odd/` completo sería un margen sin evidencia.
- Actualizar la cita del manifiesto añadiendo `internal/components/agentguidance/routing.go:49,97` (fuente en el repo pineado; el spike apunta al archivo ya instalado).

## Huecos detectados fuera de los prefijos declarados

1. **navori — `progress/current.md` y `progress/history.md` (raíz, versionados)**: resuelto con `progress/` en `artifacts`, auditado arriba; `patient/` no contiene ese directorio.
2. **navori — `specs/<feature>/*.md.draft`**: el auditor puede escribir borradores SDD ahí (`auditor.md:96`), solo si SDD está habilitado; no verifiqué si `init --yes` lo habilita. Sin veredicto.
3. **superpowers — `.superpowers/sdd/<plan-basename>/` y `.superpowers/brainstorm/`**: resuelto con `.superpowers/` en `runtime_state`, auditado arriba. `brainstorm/` solo aparece si se lanza el visual companion con `--project-dir` (no verificado en modo headless).
4. **navori — comentario del manifiesto inexacto**: dice que los hooks `subagent-handoff/orchestrator` "write session progress notes"; en `v0.10.0` los hooks solo leen `.claude/progress/` (`subagent-stop-handoff.sh:420-431`); escriben los agentes. No cambia el veredicto.

## No verificado

- No corrí los tres harnesses reales en un trial: el hecho de que un agente efectivamente escriba en cada ruta con estos defaults se apoya en la documentación/fuente, no en un transcript (lo cubre T21).
- gentle-ai: no reinstalé el binario `v3.7.0`; comparé el repo en el tag contra el árbol descrito en el spike §4/§12.
- Si el flujo `odd/tasks/` y SDD se dispara en las tareas dev del piloto depende de que el orquestador clasifique la tarea como "sustancial" (`routing.go:49`); no está medido.
