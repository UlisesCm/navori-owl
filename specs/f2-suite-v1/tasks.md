# F2 — Suite v1 — Tasks

Secuencia de `design.md` §D15. Cada lote se implementa con `implementer` → `reviewer` y cierra con
`ruff check .` + `pytest` (sin `-m docker`) en verde. Las pruebas llevan `# Covers: R<n>`.
Presupuesto de modelo: solo T0 (~$0.40) y T17 (~$1–2, Haiku). Todo lo demás es gratis (oracle, nop,
`CheatAgent`, Docker local).

## Lote 0 — Spike

- [x] **T0** (R1, R12, R13) — Spike de §"Supuestos a verificar en el spike T0": `00-smoke` como agente
  no-root (`[agent] user = "node"`) con el baseline registrado en `/var/lib/owl/baseline`; Harbor
  acepta el mismo `import_path` repetido con distintos `kwargs` en un `JobConfig`; la variante navori
  con `init --yes` + `render --apply` sobre un fixture con `CLAUDE.md` base de prueba genera `.claude/`
  y `.mcp.json` con engram y conserva el contenido base. Un trial real `vanilla-default` y uno `navori`
  con Haiku. Resultado: `specs/f2-suite-v1/spike.md` con la decisión de los fallbacks de D5 y D13,
  cada una con su evidencia (job, comando, salida) · test: evidencia en `spike.md`; los tests de
  código llegan en T1–T3.

## Lote 1 — Integridad del verifier (sobre `00-smoke`)

- [x] **T1** (R6, R7, R12) — `owl/verifier/lib.sh` (D6): `owl_begin` limpia `/logs/verifier` y mata
  procesos del agente; los excludes salen de `/var/lib/owl/ignore` y no de archivos que el agente
  controla (`.gitignore`, `.git/info/exclude`); git y tests corren como `node`; el P2P corre contra
  tests prístinos. `tasks/00-smoke` migra a `owl-lib.sh` · test: `tests/test_validate_docker.py`
  (`-m docker`) con los escenarios `.gitignore` plantado, `reward.json` plantado y baseline movido,
  con `# Covers: R6, R7, R12`.
- [x] **T2** (R12) — `ClaudeCodeHarness.run` reescribe `/var/lib/owl/baseline` y agrega
  `runtime_state` a `/var/lib/owl/ignore` como root después de mover `refs/owl/baseline`, haya o no
  `init` (D5) · test: `tests/test_validate_docker.py::baseline_record_rewritten`, `# Covers: R12`.
- [x] **T3** (R13) — `owl/gate.py::check_trial`: `baseline_valid == 0` → `contamination`;
  `verifier_complete == 0` → `infra`; `contamination` gana empates. Agrega `pytest` como dependencia
  de desarrollo y al quality gate · test: `tests/test_gate.py`, `# Covers: R13`.

## Lote 2 — Repo paciente

- [x] **T4** (R1, R2, R3) — `patient/` (`opsdesk`, D1–D3): workspaces, `CLAUDE.md`/`AGENTS.md`
  base con convenciones marcador (agent-neutrality), `docs/`, suite visible en verde,
  `patient/Dockerfile` (`owl-patient:local` fijado por digest) y `patient/seal.sh` (commit único,
  sin remotos, tags ni reflog; baseline registrado) · test:
  `tests/test_validate_docker.py::test_patient_sealed` (una sola raíz, sin reflog, canary
  presente, suite y typecheck en verde), `tests/test_patient_docs.py` (sin Docker), `# Covers: R1,
  R2, R3`.
- [x] **T5** (R1) — `variants/navori.yaml#harness.init` con la ruta que decidió T0 y su línea
  centinela; la ruta queda declarada en el manifiesto para la divulgación de F3 (D13) · test:
  `tests/test_validate_docker.py::navori_install_on_patient` (sin modelo: corre el `init` y verifica
  `.claude/`, `.mcp.json` y el `CLAUDE.md` base), `# Covers: R1`.

## Lote 3 — Herramientas de validez

- [ ] **T6** (R4, R5, R14, R15) — `owl/tasks.py` (`TaskInfo`, `is_holdout`, `refuse_holdout`,
  `suite_tasks`) y `owl run --suite/--holdout` · test: `tests/test_tasks.py`,
  `# Covers: R14, R15`; `tests/test_suite_catalog.py` (entre 12 y 15 tareas de suite, cada categoría
  de R5 cubierta), `# Covers: R4, R5`.
- [ ] **T7** (R3, R10) — `owl/agents/cheat.py::CheatAgent` con los ataques de D8 (`read-hidden`,
  `tamper-fail`, `tamper-pass`, `hardcode`, `move-baseline`, `plant-reward`) · test:
  `tests/test_validate.py` (evaluación por ataque sobre jobs sintéticos), `# Covers: R3, R10`.
- [ ] **T8** (R2, R6, R8, R9, R10, R11) — `owl validate` (D9): checks estáticos (GUID fuera de
  `instruction.md`, lib canónica, `owl_reward ⊆ owl_dimensions`), oracle ×5, nop y ataques, sin
  `--env-file`; `owl-validate.json`; salida del holdout sin contenido · test: `tests/test_validate.py`,
  `# Covers: R2, R6, R8, R9, R10, R11`.

## Lotes 4–7 — Tareas dev (catálogo de `design.md`)

Cada tarea cierra con `owl validate -t <tarea>` en verde (evidencia en `owl-validate.json`).

- [ ] **T9** (R4, R5, R6, R7) — `10-trivial-severity-case`, `11-seeded-pagination`,
  `12-accidental-combined-filters` (provisional, D14) · test: `owl validate` por tarea.
- [ ] **T10** (R4, R5, R6, R7) — `13-hidden-cause-daily-stats`, `14-feature-incident-tags`,
  `15-refactor-injected-clock` · test: `owl validate` por tarea.
- [ ] **T11** (R4, R5, R6, R7) — `16-security-comment-edit`, `17-tooling-typecheck-project`,
  `18-repro-duplicate-create` · test: `owl validate` por tarea.
- [ ] **T12** (R4, R5, R6, R7) — `19-behavior-impossible-ci`, `20-behavior-cleanup-tmp` (primera en
  salir si el tiempo aprieta), `21-overeng-csv-export` · test: `owl validate` por tarea.

## Lote 8 — Holdout

- [ ] **T13** (R2, R5, R6, R14) — `docs/task-authoring.md`: contrato de autoría sin el catálogo dev
  (formato, `owl-lib.sh`, regla de reward, canary, categorías, `owl validate`). Corrige VISION §7.1
  (no-root se justifica por la integridad del baseline, no por `bypassPermissions`) · test:
  `tests/test_validate.py` (los checks estáticos se aplican a lo que el documento prescribe).
- [ ] **T14** (R14) — Un subagente aislado, que solo recibe `patient/`, `docs/task-authoring.md`,
  `owl/verifier/lib.sh` y `tasks/00-smoke`, escribe los slots `30-*` (seguridad), `31-*`
  (comportamiento) y `32-*` (refactor) en `holdout/`. Nadie más lee su contenido hasta F3 · test:
  `owl validate --holdout` en verde (solo pasa/falla por check).
- [ ] **T15** (R2–R12) — Criterio de salida: `owl validate --suite --holdout` en verde ·
  test: `owl-validate.json` completo.

## Lote 9 — Piloto

- [ ] **T16** (R16, R17) — `owl summary`: tabla tarea × variante sobre trials `ok`, marca 0/k y k/k ·
  test: `tests/test_summary.py`, `# Covers: R16, R17`.
- [ ] **T17** (R16, R17) — Piloto `vanilla-default`, Haiku, k=2, sobre las tareas dev (sin holdout).
  `specs/f2-suite-v1/pilot.md` con una fila por tarea: resultado, marca y decisión (mantener, ajustar
  o reemplazar) con su motivo · test: `pilot.md` sin filas marcadas sin decisión.
