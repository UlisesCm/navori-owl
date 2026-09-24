# Sesión actual

**Estado:** pausado — F0 (spike Harbor). Siguiente paso: el usuario crea `.env` con `CLAUDE_CODE_OAUTH_TOKEN` y se corre la ronda real.

## Tarea
Cerrar F0 según VISION §13: gate de contaminación funcionando sobre corridas reales, telemetría por variante, tests ocultos al agente.

## Plan
- [x] Validar tareas 00-smoke y 01-probe con `-a oracle` (pasa) y `-a nop` (F2P falla)
- [x] Confirmar /tests oculto durante la fase del agente (oracle probe: tests_dir_exists=false)
- [x] `ruff check .` verde (implementer → reviewer)
- [x] Review completo del esqueleto `owl/` + `tasks/` antes del primer commit
- [ ] `.env` con `CLAUDE_CODE_OAUTH_TOKEN` (lo genera el usuario con `claude setup-token`)
- [ ] Corrida real: vanilla-default + superpowers + ponytail × 00-smoke + 01-probe, k=1, Haiku
- [ ] `owl gate jobs/` sobre esas corridas; ajustar el gate con datos reales
- [x] OTel fuera de F0 → F4 (confirmado por el usuario; VISION §5 y §13 actualizados)
- [x] Commit del esqueleto en branch `feat/f0-harbor-spike` + PR a `main`

## Archivos previstos
owl/cli.py, owl/gate.py, owl/variants.py, owl/agents/claude_code_harness.py, variants/*.yaml, VISION.md (§5, §13)

## Notas
- Harbor ya extrae costo y tokens por trial (`total_cost_usd` del evento `result` + trayectoria ATIF por paso) y cada job = una variante, así que la atribución de costo por variante no necesita OTel.
- Harbor fuerza `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` e `IS_SANDBOX=1` en el agente.
- El `setup_command` de Harbor copia `~/.claude/skills` del contenedor al CLAUDE_CONFIG_DIR del trial: inocuo con imagen limpia, pero es un vector si una imagen trae skills.
