# Sesión actual

**Estado:** F3 en curso. Decisión del usuario (2026-10-28): hasta el MVP, navori es el único harness bajo prueba; la ronda 1 corre `vanilla-default`, `navori` y `placebo`. Revisión 5 de specs EN CURSO, sin aprobar, en `docs/spec-rev5-navori-mvp` (commit WIP, sin PR).

**Siguiente:**
1. Terminar revisión 5: en `specs/r1-refresco/` falta marcar R4 diferido en el texto del requisito, sacar M4 (T5/T6) de E2 y ajustar design.md (E2 = modelo y piloto); correr `navori spec check f3-ronda1` y `navori spec check r1-refresco`. Presentar al usuario y aprobar antes de PR.
2. r1-refresco M5: precios oficiales de Haiku 5.5 (fuente y fecha) y piloto de 24 trials `vanilla-default` (gasta modelo: pedir OK).
3. f3-ronda1: T29 conformidad → T38 smoke con 3 variantes → T22 (cp de lib.sh a holdout/, sin leer contenido) → T23 (RULES.md requiere aprobación).

**Decisiones:** todos los PRs van a main. gentle-ai v4.3.1 (spike, manifiesto, auditoría) queda en la branch local `feat/r1-refresco-e2` (commit `a2042db`, sin push), para después del MVP. Familia primaria m = 4. read-hidden/peek-tests exigen reward=0, f2p=0 y sin filtración.

**Entorno:** en Pi los subagentes navori terminan sin salida; ciclos inline y declarados. Docker = OrbStack (`orb start`). Suite completa ~11 min. No usar `| tail` como evidencia de pytest. El hook `master-accept-confirm` puede expirar con comandos largos de bash: usar la herramienta Edit.
