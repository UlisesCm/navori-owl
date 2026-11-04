# Sesión actual

**Estado:** F3 en curso. #36 (M4, T7, T29) mergeado en main antes de T9; T9 (tramo de prompt largo de Haiku 5.5 en el estimador) y los borradores del piloto (`specs/r1-refresco/pilot/`) van en `feat/r1-refresco-t9` (PR #37). T8 piloto hecho: 24/24 gate ok, estimador 5e-16, $0.197 total; ninguna request pasó de 100k (máx. 67 930), así que el tramo alto sigue sin validarse contra Claude Code. Tareas 10/12 en 2/2 y 16, 19 en 0/2 (`cost-validation.md` §"Revisión 4"). r1-refresco E2 completo. `ruff check .` verde y `uv run pytest -m 'not docker'` → 355 passed. Precios de las dos columnas en `specs/f3-ronda1/cost-validation.md` §"Revisión 4".

T38 smoke hecho en `feat/f3-smoke-r1`: 6 variantes `ok` y forzados con su límite (`smoke.md` §"Revisión 4"), concurrencia 2 definitiva; fix del gate para `modelUsage` con 2.1.312.

T22 hecho en `feat/f3-holdout-sync`: `owl validate --suite --holdout` 15/15 tras corregir la copia de tests ocultos de 16/19 (`owl_copy_hidden`); el 0/2 del piloto en 16 no mide al agente (`cost-validation.md`).

**Siguiente:** mergear el PR de T22 → (opcional, gasta cuota) re-correr 16 y 19 ×2 del piloto → T23 → T23 (`round.yaml` con `cpus`, `memory_mb` y los precios con `long_context`; `RULES.md` recalcula la sensibilidad con la línea base en el techo en 10 de 12 tareas).

**Decisiones:** todos los PRs van a main. engram de gentle-ai sin fijar: releases/latest pasó de 3.6.0 a 3.6.1 (11-03); plugin 0.1.21. `lock.json` ausente o sin trials = contaminación de conformidad. Con Haiku 5.5 los forzados del smoke necesitan tope $0.0005 y timeout ×0.005. `test_launch_exception_drains_and_exits_nonzero` es intermitente (timing), preexistente. Rama `wip/r1-e2-m4-duplicado` descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
