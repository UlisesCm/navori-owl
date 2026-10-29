# R1 — Refresco al corte — Requirements

## Context
La ronda 1 de F3 se diseñó con las versiones de fines de septiembre de 2026 (Harbor 0.23.0, Claude Code
2.1.281, navori 0.10.0, superpowers v6.4.1, gentle-ai v3.7.0, Haiku 4.5). Al 2026-10-28 todas tienen
versión nueva, gentle-ai v4 cambió su flujo (ODD reemplaza a SDD) y Haiku 5.5 es el Haiku por defecto.
Decisión del usuario: antes del pre-registro, la ronda mide las versiones vigentes a una fecha de corte.
Este spec es la primera instancia del procedimiento de `specs/round-protocol/` y deja a
`specs/f3-ronda1/` listo para su entrega de conformidad y pre-registro.

Revisión 5 (2026-10-28), con decisión del usuario: hasta terminar el MVP, navori es el único harness
bajo prueba. R4 (gentle-ai v4) queda diferido; E2 se reduce a modelo y piloto (M5).

## Requirements (EARS)

### Plataforma
- **R1** — The system SHALL pin Harbor, the Claude Code agent version and every harness variant of round 1 to the latest stable release published on or before the round's cutoff date (on 2026-10-28: Harbor 0.25.0, Claude Code 2.1.312, navori 0.12.3, superpowers v7.0.1, ponytail commit `09c434ab73ca43761c5d8b0c5d341926c2fba710`, gentle-ai v4.3.1), and the whole test suite, docker tests included, SHALL pass on those pins.
- **R2** — Every harness variant of round 1 SHALL install on `owl-patient:local` at its pinned version with its sentinel check passing and its `expect` section equal to what the real installation registers.
- **R3** — WHEN a harness changes major version or its documented workflow between its previous pin and the cutoff, the system SHALL have a free, model-less spike of the new version (install flags, files written outside `/app`, telemetry, hooks, expected engram version) and a fresh-context audit of its artifact prefixes before its manifest enters the round.

### gentle-ai v4
- **R4** — The `gentle-ai` variant SHALL install release v4.3.1, verified against its published checksum, with the product defaults the spike confirms (preset `full-gentleman`, its persona and ODD as its development workflow), and SHALL set `GENTLE_AI_TELEMETRY=0` in both the installation and the agent run environments.

### Modelo y piloto
- **R5** — The default Claude Code model of owl SHALL be `anthropic/claude-haiku-5-5`, and the five prices of the round's `prices_usd_per_mtok` (input, output, cache read, 5-minute and 1-hour cache write) SHALL come from Anthropic's official pricing, recorded with source and date.
- **R6** — Before round 1's `RULES.md` is committed, owl SHALL run a pilot of 24 trials (`vanilla-default`, each of the 12 dev tasks twice) with the round's model, pins, preamble and limits in `jobs/pilot-r1`, apart from the round's jobs directory, and SHALL report per task its success, cost and behavior results; no pilot trial SHALL count in the round.
- **R7** — The cost estimator of owl SHALL reproduce `total_cost_usd` within 0.1% on every pilot trial at the R5 prices, and IF any trial falls outside that tolerance THEN the estimator or the prices SHALL be corrected before round 1's `RULES.md` is committed, without relaxing the tolerance.
