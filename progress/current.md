# Sesión actual

**Estado:** F3 en curso. #36 (M4, T7, T29) mergeado en main antes de T9; T9 (tramo de prompt largo de Haiku 5.5 en el estimador) y los borradores del piloto (`specs/r1-refresco/pilot/`) van en `feat/r1-refresco-t9` (PR #37). T8 piloto hecho: 24/24 gate ok, estimador 5e-16, $0.197 total; ninguna request pasó de 100k (máx. 67 930), así que el tramo alto sigue sin validarse contra Claude Code. Tareas 10/12 en 2/2 y 16, 19 en 0/2 (`cost-validation.md` §"Revisión 4"). r1-refresco E2 completo. `ruff check .` verde y `uv run pytest -m 'not docker'` → 355 passed. Precios de las dos columnas en `specs/f3-ronda1/cost-validation.md` §"Revisión 4".

**Siguiente:** mergear #37 → f3-ronda1: T38 smoke de T21 con Haiku 5.5 (gasta modelo) → T22 → T23 (`round.yaml` con `cpus`, `memory_mb` y los precios con `long_context`; `RULES.md` recalcula la sensibilidad con la línea base en el techo en 10 de 12 tareas).

**Decisiones:** todos los PRs van a main. engram de gentle-ai sin fijar: releases/latest pasó de 3.6.0 a 3.6.1 (11-03); plugin 0.1.21. `lock.json` ausente o sin trials = contaminación de conformidad. Rama `wip/r1-e2-m4-duplicado` descartable.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
