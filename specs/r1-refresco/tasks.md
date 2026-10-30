# R1 — Refresco al corte — Tasks

Primera instancia de `docs/round-protocol.md`. Puede empezar en paralelo con `specs/round-protocol/`,
salvo T2, que declara `harness.version` y `harness.upstream` y por eso va después de su T1. Cada hito
cierra con `ruff check .` y `uv run pytest -m 'not docker'` en verde; los hitos que tocan instalación
corren además la suite docker. Las pruebas llevan `# Covers: R<n>`. Gasto de modelo: solo el piloto
(T8), centavos a pocos dólares con Haiku 5.5.

## E1 — Plataforma al corte
Estimated LOC: 300

### M1 — Harbor 0.25.0
- **A1** [observable] — La suite completa, docker incluida, pasa sobre Harbor 0.25.0 · `uv run pytest -q` → 0 fallas
- [x] **T1** (R1) — `pyproject.toml` y `uv.lock` a `harbor==0.25.0`; `ClaudeCodeHarness` y `CheatAgent` ajustados a la API de 0.25.0 donde cambió (resolución de credenciales del adaptador de Claude Code), sin cambiar su comportamiento · effect: behavior · test: tests/test_validate_docker.py::test_owl_validate_smoke_end_to_end

### M2 — Agente y variantes al corte
- **A2** [observable] — Las variantes de la ronda cargan con `agent_version` 2.1.312 y los pins del corte, y navori, superpowers y ponytail se instalan sobre el paciente con su centinela y su `expect` · `uv run pytest tests/test_variants.py tests/test_validate_docker.py -q -k "navori or superpowers or ponytail or agent_version"` → todas pasan
- [x] **T2** (R1) — `agent_version: "2.1.312"` en `vanilla-default`, `navori`, `gentle-ai`, `superpowers`, `ponytail` y `placebo`, con `harness.version` y `harness.upstream` donde haya harness · effect: schema · test: tests/test_variants.py::test_round_variants_share_agent_version
- [x] **T3** (R1, R2) — `navori.yaml` a navori 0.12.3 con la versión de engram que espere su instalador; `superpowers.yaml` a v7.0.1 (`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b`); `ponytail.yaml` a `09c434ab73ca43761c5d8b0c5d341926c2fba710`; `expect` y centinelas confirmados contra la instalación real · effect: behavior · test: tests/test_validate_docker.py::test_navori_install_on_patient

### M3 — Prefijos al corte
- **A3** [observable] — Cada prefijo de navori, superpowers y ponytail a la versión del corte tiene fila con evidencia y veredicto · `uv run pytest tests/test_variants.py -q -k artifacts_audit` → pasa
- [x] **T4** (R3) — Spike corto de superpowers v7.0.1 (rutas que escriben brainstorming y sus hooks) y auditoría de prefijos de navori, superpowers y ponytail por un `auditor` en contexto fresco, con los criterios de T14 de F3; un prefijo rechazado sale del manifiesto · effect: docs · test: tests/test_variants.py::test_artifacts_audit_has_one_row_per_declared_prefix

## E2 — gentle-ai v4 y modelo
Estimated LOC: 250

### M4 — gentle-ai v4.3.1
- **A4** [observable] — gentle-ai v4.3.1 se instala sobre el paciente con los defaults del producto, la telemetría apagada y sus prefijos auditados · `uv run pytest tests/test_variants.py tests/test_validate_docker.py -q -k gentle_ai` → todas pasan
- [x] **T5** (R3, R4) — Spike gratis y sin modelo de gentle-ai v4.3.1 en `owl-patient:local` (flags de `install`, preset y flujo ODD por defecto, lo que escribe fuera de `/app`, telemetría, hooks, engram esperado), en `specs/f3-ronda1/spike-gentle-ai.md` §"v4.3.1", y auditoría de sus prefijos · effect: docs · test: tests/test_variants.py::test_gentle_ai_expect_matches_real_install
- [x] **T6** (R2, R4) — `gentle-ai.yaml` a v4.3.1: binario y checksum del release, flags del spike, `GENTLE_AI_TELEMETRY=0` en instalación y run, `expect`, `artifacts`, `harness.version` y `harness.upstream` · effect: behavior · test: tests/test_validate_docker.py::test_gentle_ai_install_on_patient

### M5 — Haiku 5.5 y piloto
- **A5** [observable] — Los 24 trials del piloto pasan el gate y el estimador reproduce `total_cost_usd` al 0.1% en cada uno · `uv run owl gate jobs/pilot-r1` → 24 trials sin `infra` ni `contamination`; tabla de `specs/f3-ronda1/cost-validation.md` §"Revisión 4" sin filas fuera de tolerancia
- [ ] **T7** (R5) — Precios oficiales de Haiku 5.5 (las cinco claves de `prices_usd_per_mtok`, con fuente y fecha) en `specs/f3-ronda1/cost-validation.md`; `DEFAULT_MODELS["claude-code"]` a `anthropic/claude-haiku-5-5` · effect: behavior · test: tests/test_cli_round.py::test_default_claude_model_is_haiku_5_5
- [ ] **T8** (R6, R7) — Piloto: 24 trials (`vanilla-default` × 12 tareas dev × 2) con modelo, pins, preámbulo y límites de la ronda en `jobs/pilot-r1`; validación del estimador y tabla por tarea (éxito, costo, comportamiento) en `specs/f3-ronda1/cost-validation.md` §"Revisión 4" · effect: docs · test: tests/test_gate.py::test_owl_estimate_splits_cache_write_5m_1h
