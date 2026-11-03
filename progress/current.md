# Sesión actual

**Estado:** F3 en curso. `feat/r1-refresco-e2` (pusheada, sin PR) tiene M4 cerrado, T7 y T29 con tests y docs. `ruff check .` verde y `uv run pytest -m 'not docker'` → 344 passed. Precios de Haiku 5.5 en `specs/f3-ronda1/cost-validation.md` §"Revisión 4".

**Siguiente:** abrir el PR de E2 a main (lo crea el usuario); sin merge, el progress de main sigue viejo y ya hizo rehacer M4 dos veces. Decidir si el estimador cobra el tramo >100k de Haiku 5.5 por request (riesgo R7) antes de T8. T8 piloto (gasta modelo, pedir OK; `owl run -v vanilla-default --suite -k 2 --preamble <draft> --limits <draft> --jobs-dir jobs/pilot-r1`) → T22 → T23 (`round.yaml` con `cpus`, `memory_mb` y precios ≤100k).

**Decisiones:** todos los PRs van a main. engram de gentle-ai sin fijar: releases/latest pasó de 3.6.0 a 3.6.1 (11-03); plugin 0.1.21. `lock.json` ausente o sin trials = contaminación de conformidad. Rama `wip/r1-e2-m4-duplicado` descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
