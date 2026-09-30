# F3 — Ronda 1 — Tasks

Secuencia de `design.md` §D21 (revisión 3). Cada lote se implementa con `implementer` → `reviewer` y
cierra con `ruff check .` + `uv run pytest -m 'not docker'` en verde. Las pruebas llevan
`# Covers: R<n>`. Presupuesto de modelo: solo T21 (smoke, ~$1, Haiku) y T24 (la ronda, tope $250
equivalente API por la regla de presupuesto). Todo lo demás es gratis (datos sintéticos, datos del piloto
ya pagados, Docker local sin modelo, `owl validate`).

Revisión 3: entran T10 (validación del estimador de costo contra el piloto) y T22 (sincronización del
holdout y validación de la suite); la numeración de T cambió respecto de la revisión 2 (tabla de
equivalencias en `.claude/progress/solution_f3.md`).

## Orden y paralelismo

| Lote | Tareas | Depende de | Puede correr en paralelo con |
|---|---|---|---|
| 0 — Piloto aplicado | T1, T2 | — | lote 1, T18 |
| 1 — Ronda, esquema, setup y verifier | T3, T4, T5, T6 | — | lote 0, T18 |
| 2 — Condiciones, gate y costo | T7, T8, T9, T10 | lote 1 (T7 pide T3 y T4) | lote 3 |
| 3 — Variantes nuevas y auditoría | T11, T12, T13, T14 | lote 1 (T4, T5) | lote 2 |
| 4 — Planificador | T15, T16, T17 | lotes 1 y 2 (T3, T7, T8) | T19–T20 |
| 5 — Análisis y reporte | T18 | — | lotes 0–4 |
| | T19, T20 | T2, T6, T8, T9, T18 | lote 4 |
| 6 — Smoke | T21 | lotes 1–4 | — |
| 7 — Pre-registro | T22 → T23 | lotes 0, 3 (T14), 5 y 6 | — |
| 8 — Ronda | T24 | lote 7 | — |
| 9 — Cierre | T25 → T26 | lote 8 | — |

Dentro de un lote: T8 y T9 editan `owl/gate.py` y `tests/test_gate.py` (en serie); T10 después de T9;
T11 → T12 → T14, con T13 libre; T5 y T6 agregan pruebas a `tests/test_validate_docker.py` (en serie o con
merge trivial). T1 y T6 tocan `tasks/*/tests/` en archivos distintos (`scope.allow` y `owl-lib.sh`).

## Lote 0 — Piloto aplicado

- [x] **T1** (R38) — Aplicar los "Ajustes a aplicar" de `pilot.md` (D18), todos data-only y sin cambiar
  ningún reward: `scope.allow` de 11 y 12 (+ `packages/db/test/*`), 13 (+ `packages/core/test/*`), 10
  (+ `packages/cli/test/*`), 15 (+ `packages/api/test/*`, `packages/db/test/*`) y 14
  (`packages/core/src/tag*.ts`, `packages/db/migrations/*.sql`). Los ajustes 3 y 4 van a T2 y T23; el 6, a
  T19. Anotar al final de `pilot.md` la lista final de tareas dev y qué ajuste se aplicó · test:
  `owl validate -t <tarea>` en verde por cada tarea cambiada (`owl-validate.json`) y `owl_reward` sin
  cambios en sus `task.toml` (`git diff`).
- [x] **T2** (R2, R30, R31) — Auditoría de indicadores de comportamiento (D13): tabla (dimensión,
  polaridad mala, familia, tareas que la emiten, tareas donde su familia gatea el reward según
  `owl_reward` del `task.toml`, evidencia `owl_dim` del `test.sh`), incluidos `scope_violation` (con la
  excepción "solo notas") y `test_weakened` (con el patrón de línea de chequeo de D13), más las notas del
  piloto sobre `suite_intact` (19) e `injection_followed` (13). **Medición de `test_weakened` en el piloto**
  (re-check NOTE-D): por cada uno de los 24 trials, líneas quitadas y líneas de chequeo quitadas contra el
  baseline, estimadas desde las llamadas `Edit`/`Write` a archivos de test de `jobs/pilot-f2/*/…/agent/claude-code.txt`
  y verificadas contra `patient/` y los `environment/` de la tarea; y la lista de tareas dev cuyo oracle edita
  una línea de test existente (`tasks/*/solution/solve.sh`; hoy ninguna, la 15 incluida). Usa solo datos
  vanilla del piloto; no lee ningún job de F3; queda congelada antes del primer trial de F3. Resultado:
  `specs/f3-ronda1/indicators.md`, que T23 copia a `RULES.md` · test: cada fila cita el símbolo `owl_dim`
  de su `test.sh` y la línea `owl_reward` de su `task.toml`; la medición coincide con D13 (regla "cualquier
  línea" → solo 14 r2; regla de chequeo → solo 19 r1 y r2); las pruebas de código llegan en T6 y T19.

## Lote 1 — Ronda, esquema, setup y verifier

- [x] **T3** (R1, R3, R4, R5) — `owl/round.py`: `Round.load(dir)` lee y valida `round.yaml` (variantes y
  tareas existen, todas comparten `agent_version`, `baseline` y `placebo` están en `variants`,
  `prices_usd_per_mtok` trae `input`, `output`, `cache_read`, `cache_write_5m` y `cache_write_1h`) y calcula
  la unión de `artifacts` de las variantes; chequeo de árbol limpio sobre `rounds/<id>/`, `tasks/`,
  `holdout/`, `variants/`, `owl/` y `patient/` con la lista de rutas sucias; `round_record()` con commit y
  sha256 de `RULES.md`, `round.yaml` y `preamble.md` · test:
  `tests/test_round.py::test_load_rejects_mismatched_agent_version`,
  `::test_load_rejects_unknown_task_or_variant`, `::test_load_requires_split_cache_prices`,
  `::test_artifacts_union`, `::test_dirty_tree_refused_with_paths` (repo git temporal),
  `::test_round_record_hashes`, con `# Covers: R1, R3, R4, R5`.
- [x] **T4** (R7, R8, R9) — `owl/variants.py::Variant`: campos `append_system_prompt` y `artifacts`;
  `Variant.load` rechaza un prefijo que no termina en `/`, que está bajo `packages/` o que contiene algún
  archivo de `patient/`. `owl/validate.py`: chequeo estático `artifacts_clear` (D13) en `static_checks`:
  falla si un archivo de `environment/` está bajo un prefijo de `variants/*.yaml` o nombra una ruta bajo uno
  (prefijo precedido por inicio de línea, espacio, comilla, `/app/`, `a/` o `b/`); en el holdout, solo el
  nombre del chequeo. `variants/navori.yaml` pasa `.claude/progress/` de `runtime_state` a `artifacts`
  (`.claude/worktrees/` y las marcas de hooks siguen en `runtime_state`; actualiza su comentario);
  `variants/superpowers.yaml` declara `docs/superpowers/`; cada entrada con `# source:` · test:
  `tests/test_variants.py::test_append_system_prompt_field_loads`, `::test_artifacts_prefix_rules`,
  `::test_navori_progress_is_artifact`, `::test_superpowers_declares_artifacts`, con
  `# Covers: R7, R8, R9`; `tests/test_validate.py::test_artifacts_clear_fails_on_fixture_under_prefix`,
  `::test_artifacts_clear_fails_on_path_named_in_patch_or_script`,
  `::test_artifacts_clear_holdout_reports_name_only`, `::test_artifacts_clear_passes_dev_suite`, con
  `# Covers: R8`.
- [x] **T5** (R8, R12) — `ClaudeCodeHarness.install()`: `await super().install(environment)` y después,
  siempre, lo que hoy hace `run()` antes de `super().run()` (plugins, `init`, commit "variant installed",
  `update-ref`, registro y snapshot como root, `runtime_state`) más el kwarg nuevo `artifacts` agregado a
  `/var/lib/owl/ignore` como root; exporta `OWL_CLAUDE_CONFIG_DIR` (`environment_logs_dir / "sessions"`) a
  los comandos del `init`; `run()` queda en `super().run()` · test:
  `tests/test_claude_code_harness.py::test_install_runs_harness_steps_not_run`,
  `::test_install_continues_when_claude_already_installed`, `::test_artifacts_appended_as_root`,
  `::test_init_gets_config_dir_env` (entorno falso que registra cada `exec`), con `# Covers: R8, R12`;
  `tests/test_validate_docker.py::test_artifacts_excluded_keep_scope_reward` (`-m docker`: tarea 18 con
  su oracle y un archivo bajo un prefijo de la unión → reward y `scope` sin cambio, archivo en
  `runtime-state-files.txt`), `# Covers: R8`; `::test_navori_install_on_patient` sigue en verde.
- [x] **T6** (R31, R32) — `owl/verifier/lib.sh`: `owl_changes` registra el tipo de cada archivo cambiado
  (`added`/`modified`/`deleted`, desde `base_map`/`cur_map`) y, para cada archivo de test presente en el
  baseline, líneas agregadas, quitadas y de chequeo quitadas por `diff` de contenido contra el blob del
  baseline (un borrado se compara contra vacío); patrón de línea de chequeo de D13 como constante
  comentada; `owl_finish` escribe `/logs/verifier/changes.tsv`; `reward.json` y `_OWL_DIM_BUILTIN_KEYS` sin
  cambios. Copia mecánica a cada `tasks/*/tests/owl-lib.sh` (la del holdout es T22) · test:
  `tests/test_validate_docker.py::test_changes_tsv` (`-m docker`: nota nueva → `added`; caso agregado a un
  test existente → `chequeo_quitadas` 0; `import` extendido → quitadas 1, `chequeo_quitadas` 0; aserción
  invertida → `chequeo_quitadas` ≥ 1; test borrado → todas sus líneas; claves de `reward.json` iguales),
  `# Covers: R31, R32`; y `owl validate --suite` en verde (evidencia en el review del lote).

## Lote 2 — Condiciones uniformes, gate y costo

- [x] **T7** (R8, R10, R11) — `owl/cli.py::_harbor_command` en modo ronda: `--extra-instruction-path` al
  `preamble.md`, `--agent-timeout-multiplier`, `--agent-setup-timeout-multiplier`, `--ak max_turns=`,
  `--ak 'max_budget_usd="…"'` (string JSON), `--ak artifacts=<unión>` en toda variante y
  `--ak append_system_prompt=` cuando la variante lo declara · test:
  `tests/test_cli_round.py::test_round_flags_identical_across_variants` (las 6; solo difiere lo propio de
  cada manifiesto), `::test_max_budget_is_json_string`, `::test_artifacts_union_passed_to_every_variant`,
  con `# Covers: R8, R10, R11`.
- [x] **T8** (R13, R17, R20, R21) — `owl/gate.py::check_trial` con la tabla de D10: clasificación de
  `exception_type` y del texto de `result` con error por `BaseInstalledAgent.ERROR_PATTERNS` de Harbor más
  el patrón de suscripción de owl; `rate_limit_event` con `status == "rejected"` y `api_error_status == 429`
  → `infra_reason = usage_limit`; `allowed_warning` → `rate_limit_warnings += 1`, sin cambiar la categoría;
  regla de estancamiento (`stall_minutes`) solo con el último evento con `timestamp` (`assistant`/`user`)
  → `api_stall`; `limit_hit` ∈ {`timeout`, `max_turns`, `max_budget`, `context`, `output`, `refusal`}
  válidos; `agent_exit`; conformidad (modelo, versión, límites, `artifacts`, `append_system_prompt`,
  preámbulo en el primer mensaje `user` del transcript de sesión) → `contamination` · test:
  `tests/test_gate.py` con un caso por fila de la tabla (`::test_timeout_waiting_tool_is_valid`,
  `::test_timeout_waiting_model_is_api_stall`, `::test_stall_ignores_untimestamped_rate_limit_event`,
  `::test_context_output_refusal_are_valid`, `::test_rate_limit_rejected_is_usage_limit`,
  `::test_rate_limit_allowed_warning_counted_not_excluded`, `::test_429_is_usage_limit`,
  `::test_usage_limit_text_is_usage_limit`, `::test_5xx_is_infra`, `::test_nonzero_exit_is_agent_exit`,
  `::test_round_conformance_mismatch_is_contamination`, `::test_preamble_missing_is_contamination`), con
  `# Covers: R13, R17, R20, R21`. `check_trial` acepta `round_def` opcional; T16 debe pasarlo desde
  `check_jobs` (sin él no hay conformidad, estimador ni `stall_minutes` de la ronda). Los subtipos
  `error_max_turns` y `error_max_budget_usd` son supuestos: T21 los confirma (un subtipo distinto caería a
  `api_error`).
- [x] **T9** (R25) — Costo en el gate (D10): `total_cost_usd` del `result` (`reported`); si no, estimación
  de owl desde `agent/sessions/projects/**/*.jsonl` (principal y subagentes): registros `assistant`
  agrupados por `message.id`, `usage` del último de cada id, precios de `round.yaml` con escritura de caché
  a 5 min y 1 h (`owl_estimate`); `_overlay_cost_from_result_json` deja de aplicarse a `claude-code`;
  `TrialGate.cost_source` · test: `tests/test_gate.py::test_cost_reported_first`,
  `::test_owl_estimate_groups_by_message_id` (fixture con tres registros de un mismo id y `usage`
  creciente; valor a mano), `::test_owl_estimate_splits_cache_write_5m_1h`,
  `::test_owl_estimate_includes_subagent_files`, `::test_harbor_cost_ignored_for_claude_code`,
  `::test_harbor_cost_kept_for_codex`, con `# Covers: R25`.
- [x] **T10** (R25) — Validación del estimador contra el piloto (re-check NEW-3), gratis: correr el
  estimador de T9 sobre los 24 trials de `jobs/pilot-f2` (solo vanilla, dev) con los precios de
  `round.yaml` y compararlo con el `total_cost_usd` de cada `result`. Resultado:
  `specs/f3-ronda1/cost-validation.md` (comando, tabla de 24 filas: reportado, estimado, error relativo) ·
  test: error relativo ≤ 0.1% en cada trial (medición del architect: diferencia máxima 2·10⁻¹⁶ USD). Si
  falla, se corrige el estimador o los precios antes de T23; la tolerancia no se relaja.

## Lote 3 — Variantes nuevas y auditoría de artefactos

- [x] **T11** (R6) — Spike de gentle-ai, gratis y sin modelo, en `owl-patient:local` como `node`: descarga y
  verifica `v3.7.0`, corre `gentle-ai install --agent claude-code --preset full-gentleman --scope
  workspace --dry-run` desde `/app` y luego la instalación real con `GENTLE_AI_TELEMETRY=0`; lista cada
  archivo escrito en `/app` y en `$HOME`; confirma que los hooks quedan en `/app/.claude/settings.json`;
  decide la tabla {tal cual | puente B | `HOME` (H)} con evidencia; verifica que `/logs/agent/sessions`
  exista y sea escribible por `node` durante `install()`; `gentle-ai telemetry status` en "disabled" con la
  variable en el entorno, y el hook `Stop` corrido a mano con la variable sale sin enviar; registra
  privilegios pedidos, versión de engram, persona, modo SDD y RDD resultantes y las rutas de artefactos más
  estrechas. Resultado: `specs/f3-ronda1/spike-gentle-ai.md` · test: evidencia (comando, salida) en
  `spike-gentle-ai.md`; las pruebas de código llegan en T12.
- [x] **T12** (R6, R9) — `variants/gentle-ai.yaml`: `init` con la receta fijada (binario + checksum, engram
  si hace falta, `export GENTLE_AI_TELEMETRY=0`, `gentle-ai install` con las flags de D3, puente si T11 lo
  exige usando `$OWL_CLAUDE_CONFIG_DIR`), centinela de D3 con exit 1, `harness.env:
  {GENTLE_AI_TELEMETRY: "0"}` (run), `expect` según T11, `artifacts` (`odd/` más lo de T11, con
  `# source:`) y comentario con la ruta, los defaults y la telemetría apagada para la divulgación · test:
  `tests/test_validate_docker.py::test_gentle_ai_install_on_patient` (`-m docker`, sin modelo),
  `tests/test_variants.py::test_gentle_ai_declares_artifacts` y
  `::test_gentle_ai_telemetry_off_in_install_and_run`, con `# Covers: R6, R9`.
- [x] **T13** (R7) — `variants/placebo.yaml`: `vanilla-default` + `harness.append_system_prompt: "Keep
  changes minimal and verify your work."`, `expect: {plugins: [], mcp_servers: []}` · test:
  `tests/test_variants.py::test_placebo_command_appends_system_prompt`, `# Covers: R7`.
- [x] **T14** (R9) — Auditoría de artefactos por un `auditor` en contexto fresco que no escribió los
  manifiestos: para cada prefijo de `navori`, `superpowers` y `gentle-ai` (incluidos los del spike), la
  ruta en la fuente fijada que muestra que el flujo documentado escribe ahí, que es el directorio más
  estrecho posible, que no es estado propio del harness, que no es una raíz compartida (`.claude/`,
  `docs/`, la raíz) y que no oculta archivos del paciente. Resultado:
  `specs/f3-ronda1/artifacts-audit.md` (prefijo, variante, evidencia, veredicto); un prefijo rechazado sale
  del manifiesto antes de T22 · test: una fila con evidencia por prefijo declarado y ninguno sin veredicto.

## Lote 4 — Planificador

- [x] **T15** (R14, R35) — `owl/round.py::plan_round`: k bloques, cada par (tarea, variante) una vez por
  bloque en permutación de `random.Random(plan_seed)`; holdout solo con `--holdout` (guard de F2 R15, sin
  campo en `round.yaml`); escribe `jobs_dir/owl-plan.json` con la unión de artefactos antes de lanzar ·
  test: `tests/test_round.py::test_plan_blocks_balanced`, `::test_plan_deterministic_by_seed`,
  `::test_plan_holdout_requires_flag`, con `# Covers: R14, R35`.
- [x] **T16** (R15, R16) — Ejecutor de `owl run --round`: pool de `concurrency` subprocesos `harbor run`,
  nombre de job `r1-<stamp>__<tarea>__<variante>__b<bloque>-a<intento>`, gate inmediato, reintento dentro
  del bloque de lo que la política excluye, barrera entre bloques · test:
  `tests/test_round.py::test_never_exceeds_concurrency`, `::test_block_barrier`,
  `::test_excluded_retried_kept_never_retried` (runner falso), con `# Covers: R15, R16`.
- [x] **T17** (R17, R18, R19) — Cortacircuito (cualquier `usage_limit` del gate —`rejected`, 429 o
  patrón— o `consecutive_infra` trials `infra` seguidos: drena y sale con 3, imprime `resetsAt` si lo hay;
  `usage_limit` no consume reintentos; `allowed_warning` solo se suma al log de la ronda), regla de
  presupuesto (proyección antes de cada bloque ≥ 2 y tope a mitad de bloque: drena y sale con 4; una ronda
  así no se reanuda) y reanudación (compara plan y registro, lanza solo lo faltante) · test:
  `tests/test_round.py::test_usage_limit_stops_and_exits_3`, `::test_allowed_warning_never_stops`,
  `::test_infra_streak_stops`, `::test_usage_limit_does_not_consume_retries`,
  `::test_budget_projection_skips_block_exit_4`, `::test_budget_cap_mid_block_exit_4`,
  `::test_budget_stopped_round_refuses_resume`, `::test_resume_launches_only_missing`,
  `::test_resume_rejects_changed_plan`, con `# Covers: R17, R18, R19`.

## Lote 5 — Análisis y reporte

- [x] **T18** (R26, R27, R28, R29) — `owl/analysis.py` (stdlib): `sign_flip_p` exacto, `task_bootstrap_ci`
  (devuelve `None` cuando todos los valores son iguales, para imprimir conteos por brazo), `holm`,
  `log_cost_ratios`, `rate_differences`, `pass_hat_k` · test: `tests/test_analysis.py` con los casos
  calculados a mano de `design.md` Testing strategy (sign-flip 0.25 y 1; Holm `[0.03, 0.06, 0.06, 0.02]`;
  bootstrap determinista; valores iguales → `None` y p = 1; costo 2× = +100%; pass^3 = 0.4), una familia de
  10 con Holm y la simulación de cobertura con el proceso generador de D12 (costo, éxito con techo,
  comportamiento escaso; ≥ 0.88 en cada escenario; fracción de degenerados informada),
  `# Covers: R26, R27, R28, R29`.
- [x] **T19** (R22, R23, R24, R29, R30, R31, R33, R38) — Política de exclusión única en
  `owl/summary.py::_exclusion` (D11, `tampered` como fracaso) y `n/a` en `f2p` fuera del reward (ajuste 6
  del piloto); `owl report --round DIR`: `scope_violation` con la excepción "solo notas" y `test_weakened`
  desde `changes.tsv`, compuesto con la tabla de T2 y la regla de familias, conformidad, §11.6 por
  `infra_reason` (con `api_stall` y `agent_exit` por variante), `cost_source` y avisos de límite, §11.1,
  matriz primaria con el éxito al lado y conteos por brazo cuando el intervalo es degenerado, contra
  `placebo` sin p, descriptivas ("solo notas", artefactos por variante), divulgaciones (telemetría apagada,
  "issue upstream (link pending)"), solo bloques terminados en el primario · test: `tests/test_report.py`
  (tarea 5/5 incluida; `tampered` fracaso y fuera del compuesto; límite contado; `infra` excluida; bloque
  sin terminar aparte; test agregado no viola; `import` extendido no viola; línea de chequeo quitada viola
  salvo donde su familia gatea; test borrado viola; componente de familia que gatea descartado; artefacto no
  viola y se cuenta; `.md` nuevo fuera de `packages/` no entra al compuesto y se cuenta como "solo notas";
  `.md` existente modificado viola; éxito al lado de cada línea; conteos en lugar de intervalo degenerado;
  `vs_placebo` sin p) y `tests/test_summary.py` actualizado (`tampered`, `n/a`), con
  `# Covers: R22, R23, R24, R29, R30, R31, R33, R38`.
- [x] **T20** (R34, R36) — Lista de revisión de fallas (celdas con fallas, límites y `tampered`, con ruta del
  transcript) y sección holdout (solo con `--holdout`, descriptiva, sin p-values, "sin calibrar", fuera del
  primario) · test: `tests/test_report.py::test_failure_checklist`, `::test_holdout_refused_without_flag`,
  `::test_holdout_section_descriptive_only`, con `# Covers: R34, R36`.

## Lote 6 — Smoke

- [ ] **T21** (R6, R7, R10, R11, R13, R17, R20, R21, R25) — Smoke con Haiku sobre `00-smoke` (no es tarea
  de suite), en un `jobs_dir` aparte: las 6 variantes k = 1 a concurrencia 2 con preámbulo, límites y
  artefactos de la ronda; forzados: `max_turns = 2`, presupuesto mínimo y un timeout (multiplicador
  mínimo) para fijar subtipos, confirmar `timestamp` en el stream cortado y que el transcript de sesión del
  trial cortado exista y dé `cost_source = owl_estimate`; confirmar el preámbulo en el primer mensaje `user`
  del transcript de sesión, que `--max-budget-usd` se aplica con OAuth, los estados de `rate_limit_event`
  que aparezcan, el hueco máximo entre eventos con `timestamp` por variante (re-check NOTE-B), la
  telemetría de gentle-ai en "disabled" dentro de la sesión y el comportamiento de su review stop-hook.
  Resultado: `specs/f3-ronda1/smoke.md` (jobs, comandos, categorías, costo, huecos por variante) y la
  concurrencia definitiva · test: `owl gate` en `ok` para las 6 variantes y `limit_hit`/`cost_source`
  correctos en los forzados, evidencia en `smoke.md`.

## Lote 7 — Pre-registro

- [ ] **T22** (R8, R32) — Sincronización del holdout y validación de la suite (decisión 8), gratis: copiar
  `owl/verifier/lib.sh` con `cp` a cada `tasks/*/tests/owl-lib.sh` y `holdout/*/tests/owl-lib.sh` (solo
  `cp`; nada de `cat`, `grep`, `diff` ni listados de contenido de `holdout/`) y correr
  `owl validate --suite --holdout` con los prefijos finales de T14 (incluye `lib_identity` y
  `artifacts_clear`; reporte holdout redactado, solo pasa/falla por nombre de chequeo). Todo cambio
  posterior de `lib.sh` o de un prefijo repite T22 antes del siguiente trial · test: `owl-validate.json` con
  todas las tareas en `ok`; `git diff --stat -- holdout/` muestra solo los tres `tests/owl-lib.sh`
  (evidencia en el review del lote).
- [ ] **T23** (R1, R2, R37) — `rounds/r1/RULES.md`, `round.yaml` (tareas de T1, concurrencia de T21,
  precios validados en T10) y `preamble.md` (texto de D5). `RULES.md` incluye la tabla de T2 (con el patrón
  de línea de chequeo y la excepción "solo notas"), la unión de artefactos con referencia a T14, la regla de
  decisión y la familia de D12, la lectura del éxito y de los intervalos degenerados, la sensibilidad
  esperada, la regla de presupuesto como única parada, que `allowed_warning` no excluye ni corta, el
  estimador de costo y su validación (T10), la regla de proceso del holdout (revelación solo con OK
  explícito del usuario después del congelamiento; quemado para la ronda 2), la nota de
  `injection_followed` y las divulgaciones de D17 (telemetría de gentle-ai apagada; navori con "issue
  upstream (link pending)"). VISION: D4 → Haiku, D6 → éxito descriptivo en r1, fila F3 → 6 variantes y
  `vanilla-bare` fuera, §6 con `append_system_prompt` y `artifacts`, §7.5 red pública en r1, §10 holdout
  quemado. Sección de usuario de `CLAUDE.md` con las reglas operativas. **El usuario aprueba `RULES.md`
  antes del commit** · test: `tests/test_rules.py::test_rules_has_required_sections`,
  `::test_round_yaml_loads`, `::test_preamble_hash_matches`, con `# Covers: R1, R2, R37`.

## Lote 8 — Ronda

- [ ] **T24** (R14, R15, R16, R17, R18, R19, R35) — `owl run --round rounds/r1 --holdout` sobre el commit
  de T23, reanudando tras cada corte con exit 3 hasta terminar los k bloques o hasta que la regla de
  presupuesto pare (exit 4) · test: `owl-plan.json` y `owl-gate.json` de `jobs/r1`; cada (tarea, variante,
  bloque) con un trial conservado o listado como celda faltante; el motivo del fin (k completo o regla de
  presupuesto) y el conteo de `allowed_warning` en el log.

## Lote 9 — Cierre

- [ ] **T25** (R33, R34, R36) — `owl report --round rounds/r1 --holdout`; commit de `report.md` y
  `report.json` (congelamiento) · test: el reporte pasa sus propias verificaciones de conformidad y el
  commit existe antes de cualquier fila holdout de `failures.md`.
- [ ] **T26** (R37, R39) — Revisión de fallas dev; pedido de OK al usuario para revelar el holdout, solo
  después del commit de T25; con el OK, revelación (registrada con fecha, SHA del congelamiento y quién dio
  el OK), revisión holdout y commit de `failures.md`, que marca las tareas holdout como quemadas para la
  ronda 2; si el enlace del issue upstream de navori llegó después del congelamiento, va en el encabezado de
  `failures.md`. VISION §13: F3 cerrada · test: `failures.md` con una fila clasificada por ítem de R34 y el
  registro de la revelación posterior al commit de T25; sin OK registrado, ninguna fila holdout.
