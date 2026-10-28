# Sesión actual

**Estado:** F3 en curso. PR de `fix/verifier-umask-fixture` a main: suite docker completa de nuevo en verde (85 passed) tras 24 fallas preexistentes desde RH3. `feat/r1-refresco-e1` (local, sin push) tiene el bump a Harbor 0.25.0 rebasado sobre 36318a3.

**Siguiente:** mergear el fix; rebase de `feat/r1-refresco-e1` sobre main y correr `uv run pytest -q` (A1 de r1-refresco M1) sobre Harbor 0.25.0; luego M2 (agent_version 2.1.312 y pins), M3 (auditoría de prefijos). Después T29 → T22 (copiar lib.sh a holdout/ solo con cp, sin leer contenido) → T23 (requiere aprobación de RULES.md).

**Decisiones:** todos los PRs van a main. read-hidden/peek-tests exigen reward=0, f2p=0 y sin filtración (no p2p=0). RH4/I/RH2 después de r1.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. La suite docker completa tarda ~22 min.
