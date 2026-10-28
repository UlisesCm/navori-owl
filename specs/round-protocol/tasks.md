# Round protocol — Tasks

Debe mergearse antes de la entrega E3 de `specs/f3-ronda1/` (T23 escribe `rounds/r1/round.yaml` con
`cutoff_date`, `pins` y el registro de quemados). Ninguna tarea gasta modelo. Cada hito cierra con
`ruff check .` y `uv run pytest -m 'not docker'` en verde; las pruebas llevan `# Covers: R<n>`.

## E1 — Protocolo de ronda reutilizable
Estimated LOC: 450

### M1 — Pins declarados y verificados
- **A1** [observable] — `Round.load` rechaza una ronda con Harbor o harness distintos de sus pins y lista cada diferencia · `uv run pytest tests/test_round.py tests/test_variants.py -q -k "pin or harness_version"` → todas pasan
- [ ] **T1** (R2) — `Variant` gana `version` y `upstream` desde `harness.version` y `harness.upstream`; `Variant.load` los exige con `plugins` o `init` y valida el prefijo de `upstream`; `navori`, `superpowers`, `ponytail` y `gentle-ai` declaran sus valores actuales · effect: schema · test: tests/test_variants.py::test_harness_version_required_with_plugins_or_init
- [ ] **T2** (R1, R3) — `Round.load` exige `cutoff_date` y `pins`, compara `pins.harbor` con la versión instalada y cada `pins.variants` con `Variant.version`, rechaza pins de variantes ajenas a la ronda y junta todas las diferencias en un solo error · effect: behavior · test: tests/test_round.py::test_round_refuses_harbor_mismatch

### M2 — Encabezado del reporte sin ronda fija
- **A2** [observable] — El reporte de una ronda `r2` sintética no contiene "r1" y muestra corte y pins · `uv run pytest tests/test_report.py -q -k header` → todas pasan
- [ ] **T3** (R4) — `_header` y `_md_header` toman `round_def.id`, `cutoff_date` y `pins`; `PHRASE` se forma con el id de la ronda · effect: behavior · test: tests/test_report.py::test_header_uses_round_id_and_pins

### M3 — Vigencia de pins
- **A3** [observable] — `owl pins --round` con fetcher falso imprime una fila por pin, marca `newer` y `major`, y una fuente caída sale `unknown` con exit 0 · `uv run pytest tests/test_pins.py -q` → todas pasan
- [ ] **T4** (R5, R6) — `owl/pins.py` con `latest(source, fetch)` para las cuatro fuentes (sin prereleases), tabla fija de fuentes por agente y `pin_rows`; subcomando `owl pins --round DIR` en `owl/cli.py` · effect: behavior · test: tests/test_pins.py::test_marks_newer_and_major

### M4 — Holdout quemado y procedimiento
- **A4** [observable] — Un plan con `--holdout` que incluye una tarea de `holdout/burned.yaml` se rechaza nombrándola; un registro inválido rechaza todo plan con holdout · `uv run pytest tests/test_round.py tests/test_tasks.py -q -k burned` → todas pasan
- **A5** [observable] — `docs/round-protocol.md` tiene la tabla de disparadores con los cuatro disparadores de R9 y la regla de R10 · `uv run pytest tests/test_docs.py -q -k round_protocol` → pasa
- [ ] **T5** (R7, R8) — `burned_tasks(holdout_dir)` en `owl/tasks.py` (falla cerrado) y chequeo en `round_tasks` cuando `holdout` es verdadero; `holdout/burned.yaml` vacío (`[]`) · effect: behavior · test: tests/test_round.py::test_plan_refuses_burned_holdout
- [ ] **T6** (R9, R10) — `docs/round-protocol.md`: secuencia (corte, pins, spike, auditoría de prefijos, precios, piloto, smoke, sincronización del holdout, validación, pre-registro) y tabla disparador → pasos, con la regla de cambio de pin después del corte · effect: docs · test: tests/test_docs.py::test_round_protocol_has_trigger_table
