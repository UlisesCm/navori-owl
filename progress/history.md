# Historia de sesiones

<!--
Entradas más recientes arriba. Formato sugerido (no obligatorio):

## YYYY-MM-DD HH:MM — <agente> — <resumen breve>
- Cambios: <archivos / áreas tocadas>
- Quality gate: ✅ ruff check . verde | ❌ <razón>
- Notas: <decisiones no obvias, blockers, deuda>
- Commit / PR: <hash / URL>
-->

## 2026-09-24 11:20 orchestrator — F1: absorbe navori-evals (variante navori, runtime_state, baseline fijo)
- Cambios: variants/navori.yaml (navori@0.10.0 + engram v2.1.0 fijado con sha256, runtime_state), owl/agents/claude_code_harness.py (commit "variant installed", refs/owl/baseline, .git/info/exclude), owl/gate.py (category ok/infra/contamination), owl/variants.py + owl/cli.py (runtime_state), tasks/00-smoke (baseline en Dockerfile, test.sh mide contra refs/owl/baseline), docs/research/06 §7, VISION §6/§13. navori-evals archivado con nota en su README.
- Quality gate: ✅ ruff check . verde (reviewer Pass 2, APPROVED tras varias rondas).
- Notas: corridas reales navori 00-smoke: $0.049 y $0.29 (delegó en implementer/reviewer y commiteó en branch). Esa corrida destapó que test.sh medía contra HEAD: cambios commiteados eran invisibles; corregido con baseline fijo y fail-closed. Riesgo residual documentado: un agente puede mover refs/owl/baseline con git update-ref (detectarlo requiere registrar el SHA fuera de /app → F2, junto con la corrida tramposa). Recomendado: gate marque baseline_valid=0 como contaminación. Issues upstream: navori-harness#1023 (init no avisa engram faltante) y #1024 (efímeros sin gitignore por defecto).
- Commit / PR: branch feat/f1-absorb-navori-evals

## 2026-09-24 10:15 orchestrator — Cierre de F0: variantes con plugin, probe real y runners compilados
- Cambios: tasks/01-probe/tests/test.sh (`home_claude_clean` por deny-list, fail-closed), owl/gate.py (reward.json inválido → FAIL sin crash), variants/ponytail.yaml (MCP confirmado), docs/research/07.
- Quality gate: ✅ ruff check . verde (reviewer Pass 2, APPROVED tras una ronda de CHANGES_REQUESTED).
- Notas: corridas k=1: superpowers 00-smoke reward=1 ($0.066), ponytail reward=1 ($0.037, sin MCP), vanilla-default 01-probe con falso negativo por estado de runtime en ~/.claude (backups/downloads/sessions), corregido. Skills del init: vanilla solo trae las de Claude Code; superpowers agrega exactamente superpowers:*. No hay equivalente de Harbor en Rust/Go (docs/research/07): nos quedamos en Harbor. F0 cumple su criterio de salida.
- Commit / PR: branch fix/probe-runtime-state

## 2026-09-24 09:40 orchestrator — Soporte Codex en owl y primeras corridas reales
- Cambios: owl/cli.py (agente codex de Harbor, modelo por agente, auth de suscripción para ambos), owl/gate.py (gate por agente; plugins builtin aparte), variants/codex-default.yaml, README (uso), VISION §13.
- Quality gate: ✅ ruff check . verde (reviewer Pass 2, APPROVED).
- Notas: corridas mínimas 00-smoke k=1: vanilla-default reward=1 ($0.04) y codex-default reward=1, ambas PASS. `agents-md@builtin` viene con Claude Code 2.1.281 y no es contaminación. Harbor codex no acepta `--ak variant_id`. El costo de gpt-6-luna ($0.0012) parece artefacto de la tabla de precios; la rama de error del gate de Codex no se ha visto con un log real.
- Commit / PR: branch feat/codex-agent

## 2026-09-23 23:58 orchestrator — Esqueleto F0 revisado y publicado; OTel movido a F4
- Cambios: owl/ (runner, gate, variantes, subclase ClaudeCodeHarness), tasks/00-smoke y 01-probe, variants/*.yaml, pyproject/uv.lock, VISION §5/§8/§13.
- Quality gate: ✅ ruff check . verde (reviewer Pass 2, APPROVED tras una ronda de CHANGES_REQUESTED).
- Notas: el review encontró 3 fallas del gate (caché de plugins no atómica, MCP comparado solo por nombre, fallas de Harbor invisibles), corregidas. OTel pasa a F4: Harbor ya da costo/tokens por trial. PRs de este repo van a main. Pendiente: corridas reales (falta `.env` con el token OAuth).
- Commit / PR: branch feat/f0-harbor-spike
