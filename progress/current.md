# Sesión actual

**Estado:** F3 en curso. #36 (M4, T7, T29) mergeado en main antes de T9; T9 (tramo de prompt largo de Haiku 5.5 en el estimador) y los borradores del piloto (`specs/r1-refresco/pilot/`) van en `feat/r1-refresco-t9`. T8 piloto en curso en `jobs/pilot-r1`. `ruff check .` verde y `uv run pytest -m 'not docker'` → 355 passed. Precios de las dos columnas en `specs/f3-ronda1/cost-validation.md` §"Revisión 4".

**Siguiente:** T8 piloto (aprobado; `owl run -v vanilla-default --suite -k 2 --preamble specs/r1-refresco/pilot/preamble.md --limits specs/r1-refresco/pilot/limits.yaml --jobs-dir jobs/pilot-r1`): gate, estimador contra `total_cost_usd` con las dos columnas y tabla por tarea en `cost-validation.md` §"Revisión 4" → T22 → T23 (`round.yaml` con `cpus`, `memory_mb` y los precios con `long_context`).

**Decisiones:** todos los PRs van a main. engram de gentle-ai sin fijar: releases/latest pasó de 3.6.0 a 3.6.1 (11-03); plugin 0.1.21. `lock.json` ausente o sin trials = contaminación de conformidad. Rama `wip/r1-e2-m4-duplicado` descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
