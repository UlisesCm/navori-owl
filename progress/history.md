# Historia de sesiones

<!--
Entradas más recientes arriba. Formato sugerido (no obligatorio):

## YYYY-MM-DD HH:MM — <agente> — <resumen breve>
- Cambios: <archivos / áreas tocadas>
- Quality gate: ✅ ruff check . verde | ❌ <razón>
- Notas: <decisiones no obvias, blockers, deuda>
- Commit / PR: <hash / URL>
-->

## 2026-09-23 23:58 orchestrator — Esqueleto F0 revisado y publicado; OTel movido a F4
- Cambios: owl/ (runner, gate, variantes, subclase ClaudeCodeHarness), tasks/00-smoke y 01-probe, variants/*.yaml, pyproject/uv.lock, VISION §5/§8/§13.
- Quality gate: ✅ ruff check . verde (reviewer Pass 2, APPROVED tras una ronda de CHANGES_REQUESTED).
- Notas: el review encontró 3 fallas del gate (caché de plugins no atómica, MCP comparado solo por nombre, fallas de Harbor invisibles), corregidas. OTel pasa a F4: Harbor ya da costo/tokens por trial. PRs de este repo van a main. Pendiente: corridas reales (falta `.env` con el token OAuth).
- Commit / PR: branch feat/f0-harbor-spike
