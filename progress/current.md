# Sesión actual

**Estado:** F3 en curso. r1-refresco E1 (Harbor 0.25.0, Claude Code 2.1.312, navori 0.12.3 + engram 3.6.0, superpowers v7.0.1, ponytail 09c434ab, auditoría de prefijos) en PR a main desde `feat/r1-refresco-e1`; suite completa 396 passed.

**Siguiente:** mergear E1; r1-refresco E2: M4 gentle-ai v4.3.1 (spike gratis + auditoría de prefijos), M5 precios de Haiku 5.5 y piloto de 24 trials (gasta modelo). Después f3-ronda1: T29 conformidad → T22 (copiar lib.sh a holdout/ solo con cp, sin leer contenido) → T23 (requiere aprobación de RULES.md).

**Decisiones:** todos los PRs van a main. engram 3.6.0 = releases/latest que instala navori 0.12.3 al corte. read-hidden/peek-tests exigen reward=0, f2p=0 y sin filtración (no p2p=0). RH4/I/RH2 después de r1.

**Entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara. Docker es OrbStack: si no responde, `orb start`. Suite completa ~11 min; docker sola ~22 min. No encadenar pytest con `| tail` como evidencia: oculta el exit code.
