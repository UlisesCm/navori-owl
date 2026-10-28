# Sesión actual

**Estado:** F3 en curso. Fix de permisos F2P (`fix/verifier-f2p-perms`, workplan f3-f2p-perms A1–A4 cumplidos) publicado en PR a main. PR #32 (round-protocol E1) reapuntado a main: arrastra también el contenido de #31 (specs rev4), que se mergeó sobre `chore/harness-navori-0.12.3` y nunca llegó a main.

**Siguiente:** mergear el fix F2P y #32; seguir con `r1-refresco` E1 (Harbor 0.25.0); después T29 conformidad → T22 (copiar lib.sh a holdout/ solo con cp, sin leer contenido) → T23 (requiere aprobación de RULES.md).

**Decisiones:** todos los PRs van a main. read-hidden/peek-tests exigen reward=0, f2p=0 y sin filtración (no p2p=0). RH4/I/RH2 después de r1.

**Bloqueo de entorno:** en Pi los subagentes navori terminan sin salida; los ciclos se corren inline y se declara en el cierre. Docker es OrbStack: si no responde, `orb start`.
