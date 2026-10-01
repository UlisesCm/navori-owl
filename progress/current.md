# Sesión actual

**Estado:** F3 en curso (`specs/f3-ronda1/`, spec rev. 3 aprobado). Lotes 0-3 y T18 (T1-T14, T18) mergeados (PRs #17 y #18). Lotes 4 y 5 (T15-T17 runner, T19-T20 `owl report`) mergeados (PRs #19 y #20); deuda: 4 MEDIO del review en el workplan `f3-lote5`. T21 hecha: PR #21 mergeado (tarea `tasks/02-smoke-patient`, `Round.limits` obligatorio), PR #22 mergeado (expect de gentle-ai con engram, regla de MCP `pending` confirmado en la sesión) y PR #23 mergeado (`specs/f3-ronda1/smoke.md` y el gate que suma `num_turns` de todos los `result`; navori emite uno por espera de subagentes): las 6 variantes `ok` con conformidad, forzados con `error_max_turns`, `error_max_budget_usd` y timeout con `owl_estimate`, concurrencia 2 definitiva, $1.455 en total. Hueco residual: harbor no registra los multiplicadores de timeout en `config.json`. `owl validate --suite` 12/12. Investigación de Terminal-Bench y Harbor completa en `docs/research/08-terminal-bench-y-harbor.md`. PR #24 abierto: MEDIO de los reviews de lotes 1, 3 y 5 y `VISION.md` alineado con D16 (red pública declarada). `.DS_Store` locales borrados. **RH1 (hueco `node --test`)** en `feat/f3-rh1-verifier` (workplan `f3-rh1`; diseño `.claude/progress/solution_rh1.md`, challenge `challenge_rh1.md`): decisión del usuario, defensa en capas antes de r1 (gate TAP por lista exacta de archivos, guard preload root que congela `assert` y bloquea `exit`/`reallyExit`/stdout, tripwire solo reporte en `tripwire.tsv`, ataques `import-payload`, `assert-patch` y `forged-frame`) y worker fuera de proceso (C) después de r1; 16/18/19 por el helper. `owl validate --suite` 12/12 con 9 ataques; en review. **Decisiones pendientes antes de T23:** candidatas A-I / RH2-RH5 / H1-H3 (H1 `HARBOR_TELEMETRY=0` es una línea); `progress/` raíz de navori como artefacto y fila de `.superpowers/` en `artifacts-audit.md`; texto de riesgo residual de RH1 en `RULES.md` (incluir que el `npm test` de `contradictory_red` en la 19 y las corridas locales del holdout siguen con `node --test` sin gate; corregir en D13 el "en un paso posterior" de 16/18/19, ya hecho). Siguiente: T22 (copia mecánica de `lib.sh` al holdout y `owl validate --suite --holdout`) tras mergear RH1.

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
