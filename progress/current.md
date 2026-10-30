# Sesión actual

**Estado:** F3 en curso. r1-refresco E1 mergeado (#35). E2 M4 (gentle-ai v4.3.1, expect confirmado con claude real) cerrado en `feat/r1-refresco-e2` (commits a2042db, cde4529); suite completa 396 passed. Sin PR todavía: E2 abre PR al cerrar M5.

**Siguiente:** r1-refresco M5: T7 precios oficiales de Haiku 5.5 (cinco claves con fuente y fecha en `specs/f3-ronda1/cost-validation.md`) y `DEFAULT_MODELS["claude-code"]`; T8 piloto de 24 trials en `jobs/pilot-r1` (gasta modelo, pedir OK). Después f3-ronda1: T29 conformidad (incluye smoke de RDD/stop-hook de gentle-ai v4 headless) → T22 (copiar lib.sh a holdout/ solo con cp, sin leer contenido) → T23 (requiere aprobación de RULES.md).

**Decisiones:** todos los PRs van a main. engram 3.6.0 = releases/latest que instalan navori 0.12.3 y gentle-ai 4.3.1 al corte; el plugin engram de gentle-ai (0.1.19) no está fijado. read-hidden/peek-tests exigen reward=0, f2p=0 y sin filtración (no p2p=0). RH4/I/RH2 después de r1.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code. Para spikes sin modelo, Claude Code real se instala en el contenedor con el bootstrap de Harbor (`bash -s -- <versión>`).
