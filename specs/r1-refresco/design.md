# R1 — Refresco al corte — Design

## Approach

Primera instancia del procedimiento de `specs/round-protocol/`: fijar la fecha de corte, subir cada pin
a la versión estable vigente en esa fecha, repetir el spike y la auditoría de prefijos de los harnesses
que cambiaron de versión mayor o de flujo, y recalibrar costo y sensibilidad con un piloto del modelo
nuevo. El resultado deja a `specs/f3-ronda1/` en condiciones de correr su entrega de conformidad y
pre-registro (smoke, sincronización del holdout y `RULES.md`) sobre los pins finales.

Dos entregas, porque tienen riesgos y costos distintos:
1. **E1 — Plataforma** (gratis): Harbor, Claude Code, navori, superpowers y ponytail, con la suite
   docker en verde y la auditoría de prefijos.
2. **E2 — gentle-ai v4 y modelo** (gasta modelo solo en el piloto): spike y manifiesto de gentle-ai
   v4.3.1, precios de Haiku 5.5 y piloto.

**Descartado:**
- *Congelar las versiones de septiembre y correr r1 ya.* Mediría Haiku 4.5, cuyo retiro ya puede
  anunciarse ("not sooner than October 15, 2026"), y un flujo de gentle-ai que ya no existe.
- *Correr r1 con lo viejo y refrescar en r2.* Quema el holdout en una ronda de poco valor.
- *Reusar el piloto de F2 para calibrar.* Corrió con Haiku 4.5; sus tasas de éxito y su costo no
  predicen los de 5.5.

## Components

- `pyproject.toml`, `uv.lock` — Harbor 0.25.0 — covers R1.
- `owl/agents/claude_code_harness.py`, `owl/agents/cheat.py` — ajuste a la API de Harbor 0.25.0 sin
  cambio de comportamiento — covers R1.
- `variants/*.yaml` — `agent_version` 2.1.312; navori 0.12.3 con su engram; superpowers v7.0.1;
  ponytail `09c434ab`; gentle-ai v4.3.1; `harness.version` y `harness.upstream` de
  `specs/round-protocol/` — covers R1, R2, R4.
- `specs/f3-ronda1/artifacts-audit.md` — filas a las versiones del corte — covers R3.
- `specs/f3-ronda1/spike-gentle-ai.md` §"v4.3.1" — covers R3, R4.
- `owl/cli.py` (`DEFAULT_MODELS`) — Haiku 5.5 — covers R5.
- `specs/f3-ronda1/cost-validation.md` §"Revisión 4" — precios con fuente, piloto y validación del
  estimador — covers R5, R6, R7.

## Decisions

- **D1 — Corte y pins.** El corte es el día en que E1 fija los pins; lo registra `rounds/r1/round.yaml`
  (`cutoff_date`) en el pre-registro de F3. Después del corte, un pin cambia solo con motivo escrito en
  `RULES.md` y repitiendo lo que pida `docs/round-protocol.md`. Cambios observados el 2026-10-28 (PyPI,
  npm, GitHub):

| Pieza | Antes | Corte | Riesgo |
|---|---|---|---|
| Harbor | 0.23.0 | 0.25.0 | La suite sin docker pasa (292 passed, 1 skipped) sobre una copia de `origin/main`; el adaptador `harbor.agents.installed.claude_code` reescribió su resolución de credenciales, así que la suite docker y el smoke deciden |
| Claude Code | 2.1.281 | 2.1.312 | Cambios en hooks, MCP, subagentes y escape de `stream-json`; el gate y el smoke los cubren |
| navori | 0.10.0 | 0.12.3 | Versión de engram esperada a confirmar en su script de instalación |
| superpowers | v6.4.1 | v7.0.1 (`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`) | Brainstorming reescrito y hooks nuevos: spike corto y auditoría de prefijos |
| ponytail | `e3ba2aa6` | `09c434ab73ca43761c5d8b0c5d341926c2fba710` | 139 commits; auditoría de prefijos |
| gentle-ai | v3.7.0 | v4.3.1 | Flujo ODD: spike completo |
| engram | 2.1.0 | la que espere cada harness | Se registra la vista en el trial |

  Codex (`0.156.1` → `0.165.0`) no entra en r1 y no se toca.
- **D2 — Qué harness pide spike (R3).** gentle-ai (v3 → v4, flujo nuevo) y superpowers (v6 → v7) piden
  spike y auditoría; navori (0.10 → 0.12) y ponytail (commit nuevo, sin versión mayor) solo auditoría de
  prefijos, con un spike si la auditoría encuentra rutas nuevas fuera de `/app`.
- **D3 — Modelo.** `anthropic/claude-haiku-5-5`: $0.10/$0.50 por MTok de entrada/salida según el
  changelog de Claude Code 2.1.293. Los tres precios de cache no están en ese changelog: se toman de la
  tabla oficial de Anthropic con fecha, y el piloto los valida (R7).
- **D4 — Piloto (R6, R7).** 24 trials: `vanilla-default` × 12 tareas dev × 2, con el modelo, los pins, el
  preámbulo y los límites de la ronda, en `jobs/pilot-r1`. Sirve para validar el estimador de costo,
  recalcular la sensibilidad esperada que declara `RULES.md` y detectar tareas que queden en 0/2 o 2/2
  (R23 de F3 las mantiene en el análisis; el piloto solo lo informa). Costo esperado: centavos a pocos
  dólares. Corre después de E1 y de la variante gentle-ai nueva, porque usa los pins finales.

## Failure modes

- **Harbor 0.25.0 rompe la suite docker.** Se corrige el adaptador; si la causa es un cambio de
  comportamiento de Harbor que owl no puede absorber, el pin de Harbor se queda en 0.23.0 con motivo
  escrito en `RULES.md` (R40 de F3).
- **Un harness nuevo no se instala sin interacción.** El spike lo detecta antes de tocar el manifiesto;
  el pin se queda en la última versión que instala, con motivo en `RULES.md`.
- **El estimador falla la tolerancia con los precios nuevos.** Se corrigen los precios o el estimador;
  la tolerancia del 0.1% no se relaja (R7).

## Testing strategy

| Riesgo | Prueba |
|---|---|
| Harbor nuevo rompe el aislamiento o el verifier | suite docker completa, `tests/test_validate_docker.py::test_owl_validate_smoke_end_to_end` (R1) |
| Una variante queda con otra versión de Claude Code | `tests/test_variants.py::test_round_variants_share_agent_version` (R1) |
| Instalación real distinta de `expect` | `tests/test_validate_docker.py::test_navori_install_on_patient` y `::test_gentle_ai_install_on_patient` (R2, R4) |
| Prefijo nuevo sin auditar | `tests/test_variants.py::test_artifacts_audit_has_one_row_per_declared_prefix` (R3) |
| Telemetría de gentle-ai encendida | `tests/test_variants.py::test_gentle_ai_telemetry_off_in_install_and_run` (R4) |
| Modelo por defecto viejo | `tests/test_cli_round.py::test_default_claude_model_is_haiku_5_5` (R5) |
| Estimador fuera de tolerancia | `tests/test_gate.py::test_estimated_cost_matches_reported` y la tabla del piloto (R6, R7) |

## NOT in scope

- Conformidad (workplan `f3-conformity`), smoke, sincronización del holdout y `RULES.md`: entrega de
  conformidad y pre-registro de `specs/f3-ronda1/`.
- Codex y `vanilla-bare`: no están en r1.
- Código de pins, corte y holdout quemado: `specs/round-protocol/`.
