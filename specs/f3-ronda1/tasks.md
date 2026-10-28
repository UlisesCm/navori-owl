# F3 — Ronda 1 — Tasks

Revisión 4 (2026-10-28), formato E/M/A/T. Secuencia en `design.md` §D21. Cada hito se implementa con
`implementer` → `reviewer` y cierra con `ruff check .` y `uv run pytest -m 'not docker'` en verde; las
pruebas llevan `# Covers: R<n>`. La entrega E2 requiere `specs/round-protocol/` y `specs/r1-refresco/`
mergeados.

Presupuesto de modelo de este spec: el smoke (T38) y la ronda (T24, tope de $250 equivalente API por la
regla de presupuesto). El piloto con Haiku 5.5 está en `specs/r1-refresco/`. Todo lo demás es gratis.

## E1 — Infraestructura de la ronda (revisiones 1–3, hecho)
Estimated LOC: 0

Mergeado en los PRs #17 a #28. El texto completo de cada tarea está en `tasks-rev3.md`; los números de
T se conservan.

### M1 — Piloto aplicado, ronda, esquema y verifier (lotes 0 y 1)
- **A1** — Los ajustes del piloto, `Round.load`, los campos nuevos de variante, `install()` en setup y `changes.tsv` están en `main` · `uv run pytest tests/test_round.py tests/test_variants.py -q` → todas pasan
- [x] **T1** (R38) — Ajustes del piloto de F2 aplicados sin cambiar rewards · effect: tests · test: specs/f2-suite-v1/pilot.md::Ajustes a aplicar
- [x] **T2** (R2, R30, R31) — Auditoría de indicadores de comportamiento · effect: docs · test: specs/f3-ronda1/indicators.md::Tabla de indicadores
- [x] **T3** (R1, R3, R4, R5) — `Round.load`, árbol limpio y registro de la ronda · effect: behavior · test: tests/test_round.py::test_load_rejects_mismatched_agent_version
- [x] **T4** (R7, R8, R9) — `append_system_prompt` y `artifacts` en `Variant` · effect: schema · test: tests/test_variants.py::test_append_system_prompt_field_loads
- [x] **T5** (R8, R12) — Instalación del harness en la fase de setup · effect: behavior · test: tests/test_claude_code_harness.py::test_install_runs_harness_steps_not_run
- [x] **T6** (R31, R32) — `changes.tsv` del verifier · effect: behavior · test: tests/test_validate_docker.py::test_changes_tsv

### M2 — Condiciones, gate, costo y variantes (lotes 2 y 3)
- **A2** — Flags de ronda uniformes, gate con la tabla de D10, costo estimado, gentle-ai v3.7.0, placebo y auditoría de prefijos en `main` · `uv run pytest tests/test_gate.py tests/test_cli_round.py -q` → todas pasan
- [x] **T7** (R8, R10, R11) — Flags de ronda uniformes en `_harbor_command` · effect: behavior · test: tests/test_cli_round.py::test_round_flags_identical_across_variants
- [x] **T8** (R13, R17, R20, R21) — Clasificación del gate por la tabla de D10 · effect: behavior · test: tests/test_gate.py::test_timeout_waiting_model_is_api_stall
- [x] **T9** (R25) — Costo reportado o estimado en el gate · effect: behavior · test: tests/test_gate.py::test_cost_reported_first
- [x] **T10** (R25) — Validación del estimador contra el piloto de F2 (Haiku 4.5) · effect: docs · test: tests/test_gate.py::test_owl_estimate_groups_by_message_id
- [x] **T11** (R6) — Spike de gentle-ai v3.7.0 · effect: docs · test: specs/f3-ronda1/spike-gentle-ai.md::Resumen de decisiones para T12
- [x] **T12** (R6, R9) — Variante `gentle-ai` v3.7.0 · effect: behavior · test: tests/test_validate_docker.py::test_gentle_ai_install_on_patient
- [x] **T13** (R7) — Variante `placebo` · effect: behavior · test: tests/test_variants.py::test_placebo_command_appends_system_prompt
- [x] **T14** (R9) — Auditoría de prefijos de artefactos · effect: docs · test: tests/test_variants.py::test_artifacts_audit_has_one_row_per_declared_prefix

### M3 — Planificador, análisis, reporte y smoke (lotes 4 a 6)
- **A3** — Planificador por bloques, cortacircuito, presupuesto, análisis, reporte y smoke de Haiku 4.5 en `main` · `uv run pytest tests/test_round.py tests/test_analysis.py tests/test_report.py -q` → todas pasan
- [x] **T15** (R14, R35) — Plan en k bloques con semilla · effect: behavior · test: tests/test_round.py::test_plan_blocks_balanced
- [x] **T16** (R15, R16) — Ejecutor con concurrencia y barrera entre bloques · effect: behavior · test: tests/test_round.py::test_never_exceeds_concurrency
- [x] **T17** (R17, R18, R19) — Cortacircuito, regla de presupuesto y reanudación · effect: behavior · test: tests/test_round.py::test_usage_limit_stops_and_exits_3
- [x] **T18** (R26, R27, R28, R29) — Funciones de análisis estadístico · effect: behavior · test: tests/test_analysis.py::test_sign_flip_hand_computed
- [x] **T19** (R22, R23, R24, R29, R30, R31, R33, R38) — Política de exclusión y `owl report` · effect: behavior · test: tests/test_report.py::test_unfinished_block_is_apart_and_out_of_the_primary
- [x] **T20** (R34, R36) — Lista de fallas y sección holdout · effect: behavior · test: tests/test_report.py::test_failure_checklist
- [x] **T21** (R6, R7, R10, R11, R13, R17, R20, R21, R25) — Smoke con Haiku 4.5 (se repite en T38) · effect: docs · test: specs/f3-ronda1/smoke.md::Checks asked by T21

### M4 — Endurecimiento previo al pre-registro
- **A4** — RH3 y los extras B, C, E y F del reporte en `main` · `uv run pytest tests/test_cheat.py tests/test_report.py -q` → todas pasan
- [x] **T27** (R3, R8, R9, R10, R12, R32) — RH3: aislamiento del verifier y prefijos de navori y superpowers · effect: behavior · test: tests/test_validate_docker.py::test_peek_tests_cannot_read_verifier_mount
- [x] **T28** (R29, R33, R34, R36) — Extras B, C, E y F del reporte · effect: behavior · test: tests/test_report.py::test_sensitivity_exclusion_policies_are_descriptive

## E2 — Conformidad y pre-registro
Estimated LOC: 600

### M5 — Conformidad
- **A5** [observable] — Telemetría de Harbor apagada; multiplicadores de timeout leídos de `lock.json`; recursos fijos; esfuerzo, permisos y herramientas registrados por trial; chequeo `net_pinning` en `owl validate` · `uv run pytest tests/test_gate.py tests/test_round.py tests/test_cli_round.py tests/test_validate.py -q` → todas pasan
- [ ] **T29** (R6, R7, R10, R11, R17, R20, R21) — Workplan `f3-conformity` revisado contra `origin/main`: H1 `HARBOR_TELEMETRY=0` en todo subproceso `harbor`; H2 multiplicadores de timeout desde `lock.json` (la versión y `exception_type` ya se leen); A `cpus` y `memory_mb` en `limits`; D esfuerzo, modo de permisos y herramientas efectivas por trial; G chequeo estático `net_pinning` · effect: behavior · test: tests/test_gate.py::test_conformity_reads_lock_multipliers

### M6 — Smoke al corte
- **A6** [observable] — Las seis variantes salen `ok` con conformidad sobre los pins finales y los forzados registran su límite y `cost_source` · `uv run owl gate jobs/smoke-r1` → 6 `ok` y forzados con `limit_hit` correcto
- [ ] **T38** (R6, R7, R10, R11, R13, R17, R20, R21, R25, R40) — Repetir el smoke de T21 con Haiku 5.5 y los pins del corte (mismos forzados y confirmaciones); resultado en `smoke.md` §"Revisión 4" con la concurrencia definitiva · effect: docs · test: tests/test_gate.py::test_round_conformance_ok

### M7 — Holdout y pre-registro
- **A7** [observable] — Suite y holdout validan con el `lib.sh` y los prefijos finales, y `rounds/r1/` carga con corte y pins · `uv run owl validate --suite --holdout` → 15 tareas `ok`; `uv run pytest tests/test_rules.py -q` → pasa
- [ ] **T22** (R8, R32, R40) — Copiar `owl/verifier/lib.sh` con `cp` a cada `tasks/*/tests/owl-lib.sh` y `holdout/*/tests/owl-lib.sh` (sin `cat`, `grep`, `diff` ni listados de `holdout/`) y correr `owl validate --suite --holdout`; `git diff --stat -- holdout/` muestra solo los tres `tests/owl-lib.sh` · effect: tests · test: tests/test_validate.py::test_static_check_lib_identity_fails_on_drift
- [ ] **T23** (R1, R2, R37, R40) — `rounds/r1/RULES.md`, `round.yaml` (modelo, corte, pins, tareas, concurrencia de T38, precios de `specs/r1-refresco/`) y `preamble.md` (D5); `RULES.md` con lo que pide R2, la sensibilidad del piloto de `specs/r1-refresco/`, las declaraciones de riesgo residual RH5 y RH1 y la justificación de todo pin anterior al corte; VISION D4 a Haiku 5.5; el usuario aprueba `RULES.md` antes del commit · effect: docs · test: tests/test_rules.py::test_rules_has_required_sections

## E3 — Ronda y cierre
Estimated LOC: 0

### M8 — Ronda
- **A8** [observable] — Cada (tarea, variante, bloque) tiene un trial conservado o figura como celda faltante, con el motivo del fin en el log · `uv run owl run --round rounds/r1 --holdout` → exit 0 (k completo) o 4 (regla de presupuesto), con `owl-plan.json` y `owl-gate.json` en `jobs/r1`
- [ ] **T24** (R14, R15, R16, R17, R18, R19, R35) — Correr la ronda sobre el commit de T23, reanudando tras cada corte con exit 3 · effect: behavior · test: tests/test_round.py::test_resume_launches_only_missing

### M9 — Reporte y revisión de fallas
- **A9** [observable] — `report.md` y `report.json` commiteados antes de cualquier fila holdout de `failures.md`, y `failures.md` clasifica cada ítem de R34 · `uv run owl report --round rounds/r1 --holdout` → reporte que pasa su conformidad
- [ ] **T25** (R33, R34, R36) — Reporte de la ronda y commit de congelamiento · effect: docs · test: tests/test_report.py::test_failure_checklist
- [ ] **T26** (R37, R39) — Revisión de fallas dev; con el OK del usuario después de T25, revelación registrada (fecha, SHA del congelamiento, quién dio el OK), revisión holdout, `failures.md` y alta de las tareas reveladas en `holdout/burned.yaml`; VISION §13: F3 cerrada · effect: docs · test: tests/test_report.py::test_holdout_section_descriptive_only
