# Sesión actual

**Estado:** en curso — F2 (specs/f2-suite-v1/tasks.md es el tablero). Lotes 0–1 listos (PR). Siguiente: lote 2 (T4 repo paciente opsdesk + seal.sh que centraliza owl_snapshot; T5 navori sobre el paciente).

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
