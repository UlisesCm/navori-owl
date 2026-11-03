# Sesión actual

**Estado:** F3 en curso. `feat/r1-refresco-e2` (sin push nuevo, sin PR) tiene M4 cerrado y, solo código, T7 (`DEFAULT_MODELS` a `anthropic/claude-haiku-5-5`), flags `--preamble`/`--limits` de `owl run` para el piloto y T29 completo (H1 `HARBOR_TELEMETRY=0`, H2/A `lock.json` + `limits.cpus/memory_mb` opcionales, D permisos/herramientas/esfuerzo en `TrialGate`, G `net_pinning`). Por pedido del usuario, sin tests ni docs: `uv run pytest -m 'not docker'` → 10 failed, 301 passed.

**Deuda (antes del PR):** 9 fixtures sin `lock.json` (`tests/test_round.py` FakeHarbor, `tests/test_gate.py::test_round_conformance_ok`); doc de autoría sin `net_pinning` (`test_authoring_doc_prescriptions_match_validate_and_tasks`); tests nuevos: `test_default_claude_model_is_haiku_5_5`, `test_conformity_reads_lock_multipliers`, telemetría, pinning, flags del piloto; marcar T7/T29 en tasks.md. Precios de Haiku 5.5 (fuente y fecha) en `cost-validation.md`.

**Siguiente:** saldar deuda → T8 piloto (gasta modelo, pedir OK; `owl run -v vanilla-default --suite -k 2 --preamble <draft> --limits <draft> --jobs-dir jobs/pilot-r1`) → T22 → T23 (`round.yaml` debe declarar `cpus` y `memory_mb`).

**Decisiones:** todos los PRs van a main. engram 3.6.0 = releases/latest al corte; el plugin engram de gentle-ai no está fijado y ya derivó (0.1.19 el 10-30, 0.1.21 el 11-02). `lock.json` ausente o sin trials = contaminación de conformidad. Rama `wip/r1-e2-m4-duplicado` = M4 rehecho por error; descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
