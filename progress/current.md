# Sesión actual

**Estado:** F3 en curso. PR #36 (`feat/r1-refresco-e2` → main) abierto: M4, T7, T9 (tramo de prompt largo de Haiku 5.5 en el estimador) y T29. `ruff check .` verde y `uv run pytest -m 'not docker'` → 355 passed. Precios de las dos columnas en `specs/f3-ronda1/cost-validation.md` §"Revisión 4".

**Siguiente:** mergear #36 (sin merge, el progress de main sigue viejo y ya hizo rehacer M4 dos veces). T8 piloto, que valida el tramo contra `total_cost_usd`, (gasta modelo, pedir OK; `owl run -v vanilla-default --suite -k 2 --preamble <draft> --limits <draft> --jobs-dir jobs/pilot-r1`) → T22 → T23 (`round.yaml` con `cpus`, `memory_mb` y los precios con `long_context`).

**Decisiones:** todos los PRs van a main. engram de gentle-ai sin fijar: releases/latest pasó de 3.6.0 a 3.6.1 (11-03); plugin 0.1.21. `lock.json` ausente o sin trials = contaminación de conformidad. Rama `wip/r1-e2-m4-duplicado` descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
