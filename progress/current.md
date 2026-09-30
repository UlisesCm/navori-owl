# Sesión actual

**Estado:** F3 en curso (`specs/f3-ronda1/`, spec rev. 3 aprobado). Lotes 0-3 y T18 (T1-T14, T18) mergeados (PRs #17 y #18). Lote 4 (T15-T17: `plan_round`, `owl/runner.py` con cortacircuito, presupuesto y reanudación; `check_jobs` con `round_def`, `TrialGate.resets_at`) en el PR #19 (abierto); solo probado con runner falso. Lote 5 (T19-T20: `owl report --round`, `tampered` conservado como fracaso, `f2p` n/a, lista de fallas, holdout descriptivo; `TrialGate.result_event` y rechazo de holdout antes de leer logs) aprobado (243 passed) en `feat/f3-lote5-report`, apilado sobre `feat/f3-lote4`; deuda: 4 MEDIO del review en el workplan `f3-lote5`. `owl validate --suite` 12/12. Investigación de Terminal-Bench y Harbor completa en `docs/research/08-terminal-bench-y-harbor.md`. **Decisiones pendientes antes de T22/T23:** (1) cerrar el hueco del verifier `node --test` (RH1+RH3+RH4, un solo cambio de `lib.sh`, primero probar el ataque `import-payload` en Docker con Node 22); (2) cuáles candidatas A-I / RH2 / H1-H3 entran a F3 (H1 `HARBOR_TELEMETRY=0` es una línea); (3) arreglar `VISION.md:173` (red). Siguiente en el plan: T21 (smoke, primer gasto de modelo; ejercita por primera vez `owl run --round` real). Antes de T22: borrar los `.DS_Store` de `tasks/*/tests/` y resolver los MEDIO del review del lote 3 (ver `progress/history.md`).

## Tarea
Cerrar F0 según VISION §13: gate de contaminación funcionando sobre corridas reales, telemetría por variante, tests ocultos al agente.

## Plan
- [x] Validar tareas 00-smoke y 01-probe con `-a oracle` (pasa) y `-a nop` (F2P falla)
- [x] Confirmar /tests oculto durante la fase del agente (oracle probe: tests_dir_exists=false)
- [x] `ruff check .` verde (implementer → reviewer)
- [x] Review completo del esqueleto `owl/` + `tasks/` antes del primer commit
- [x] `.env` con `CLAUDE_CODE_OAUTH_TOKEN` (validar gratis con curl a /v1/models)
- [x] Corrida real mínima: vanilla-default y codex-default × 00-smoke, k=1 → ambas PASS
- [x] Corrida real de superpowers + ponytail y del probe 01 (k=1): PASS; probe corregido (estado de runtime en ~/.claude)
- [x] Gate ajustado con datos reales: plugins `builtin` aparte; eventos de Codex confirmados
- [x] Baseline Codex (`codex-default`, suscripción ChatGPT) adelantado de F5
- [x] OTel fuera de F0 → F4 (confirmado por el usuario; VISION §5 y §13 actualizados)
- [x] Commit del esqueleto en branch `feat/f0-harbor-spike` + PR a `main`

## Archivos previstos
owl/cli.py, owl/gate.py, owl/variants.py, owl/agents/claude_code_harness.py, variants/*.yaml, VISION.md (§5, §13)

## Notas
- Harbor ya extrae costo y tokens por trial (`total_cost_usd` del evento `result` + trayectoria ATIF por paso) y cada job = una variante, así que la atribución de costo por variante no necesita OTel.
- Harbor fuerza `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` e `IS_SANDBOX=1` en el agente.
- El `setup_command` de Harbor copia `~/.claude/skills` del contenedor al CLAUDE_CONFIG_DIR del trial: inocuo con imagen limpia, pero es un vector si una imagen trae skills.
