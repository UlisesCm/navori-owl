# Smoke of round 1 (T21)

Haiku 4.5 (`anthropic/claude-haiku-4-5-20251001`), subscription auth (OAuth), Claude Code 2.1.281,
`owl run --round` with the real Harbor runner. 20 trials, $1.455 API-equivalent in total (smoke only,
not counted toward the round budget).

**Round definitions.** Ephemeral, under `jobs/smoke-f3/round-<name>/` (git-ignored, never pre-registered).
Each carries the D5 preamble verbatim, the design Contracts `limits:` section and the round prices;
`main` uses the six round variants at concurrency 2 with the round limits (3.0 / 2.0 / 300 / "5.00") and
the round artifact union; the forced ones use `vanilla-default` alone with one limit changed.

```bash
uv run owl run --round jobs/smoke-f3/round-<name>
```

Gate with the round definition (the plain `owl gate` never estimates cost, it has no `round_def`):

```bash
uv run python -c "from pathlib import Path; from owl.round import Round; from owl.gate import check_jobs
r = Round.load('jobs/smoke-f3/round-<name>')
for g in check_jobs(Path('jobs/smoke-f3/<jobs>'), r): print(g.variant, g.category, g.limit_hit, g.cost_source, g.cost_usd, g.reasons)"
```

## What the first smoke found (fixed before this record)

| Run | Finding | Root cause | Fix |
|---|---|---|---|
| `main` on `tasks/00-smoke` | `navori` and `gentle-ai` `infra` (`NonZeroAgentExitCodeError` in setup) | `00-smoke` is `FROM node:22-bookworm-slim` with its own app; both `init`s check the patient sentinel `opsdesk-conventions-sentinel-f96c2e` in `/app/CLAUDE.md` and exit 1 by design | New non-suite task `tasks/02-smoke-patient` (`FROM owl-patient:local`, `owl_type = "smoke"`), PR #21 |
| forced `turns`, `budget`, `timeout` | No limit applied (`max_turns = 2` ran 8 turns; `max_budget_usd = 0.01` spent $0.036; timeout ×0.02 finished) | `_round_flags` and the conformance check read the limits from the top level of `round.yaml`; the contract nests them under `limits:`, so they were skipped silently | `Round.limits` required with its four keys, fail loud, PR #21 |
| `main-v2` on `tasks/02-smoke-patient` | navori reports 3 turns for a 26-turn trial | The gate read `num_turns` from the last `result` event; navori emits one per wait on its background subagents | Sum `num_turns` over the trial's `result` events (this PR) |
| `main-v2` on `tasks/02-smoke-patient` | `gentle-ai` `contamination` | The real install loads the `engram` plugin and user MCP (engram component of preset full-gentleman), undeclared in `expect`; `context7` (npx/stdio) is `pending` at `init` and connects ~6 s later | `expect` updated; a declared server `pending` at `init` passes only if a later `deferred_tools_delta` in the trial's session transcript adds its `mcp__<server>__*` tools, PR #22 (evidence: `.claude/progress/scout_t21-gentle-ai.md`) |

## Six variants (`jobs/smoke-f3/main-v2`, `gentle-v3`)

All trials `ok` with round conformance (model, version, `max_turns`, `max_budget_usd`, artifacts,
preamble in the first `user` message of the session transcript), reward 1, `cost_source = reported`,
no `infra`.

| Variant | Jobs dir | Cost | Turns | Max gap between timestamped events | `rate_limit_event` |
|---|---|---|---|---|---|
| vanilla-default | main-v2 | $0.0632 | 13 | 2.6 s | allowed ×1 |
| placebo | main-v2 | $0.0770 | 15 | 3.0 s | allowed ×1 |
| superpowers | main-v2 | $0.1068 | 18 | 3.2 s | allowed ×1 |
| ponytail | main-v2 | $0.0794 | 14 | 2.6 s | allowed ×1 |
| navori | main-v2 | $0.3961 | 26 (6 `result` events: 7+4+5+3+4+3) | 10.6 s | allowed ×2 |
| gentle-ai | gentle-v3 (after PR #22) | $0.1738 | 16 | — | — |

`gentle-v3` is `gentle-ai` plus `vanilla-default` (the baseline must be in the round) on the committed
fix (`4fdf79c`); `context7` was `pending` at `init` again and the rule accepted it from the session
transcript.

**Several `result` events per trial (navori).** navori delegates to background subagents
(implementer, reviewer, publisher) and the main loop ends a turn each time it waits for them, so its
stream carries 6 `result` events (362 stream events, 244 with `timestamp`). All six report the same
session-wide `total_cost_usd` ($0.3961), so the cost is right; `num_turns` is per segment, so the trial's
turns are the sum (26), not the last value (3) the gate used to read. The gate now sums `num_turns` over
the `result` events of the trial.

## Forced limits (`jobs/smoke-f3/{turns,budget,timeout}-v2`, `vanilla-default` on `tasks/00-smoke`)

| Forced | Harbor evidence | `result` subtype | Gate | Cost |
|---|---|---|---|---|
| `max_turns = 2` | `agent.kwargs.max_turns = 2` | `error_max_turns` | `ok`, `limit_hit = max_turns`, reward 0 | $0.0130 `reported` |
| `max_budget_usd = "0.01"` | `agent.kwargs.max_budget_usd = "0.01"` | `error_max_budget_usd` | `ok`, `limit_hit = max_budget`, reward 0 | $0.0128 `reported` |
| `agent_timeout_multiplier = 0.02` (600 s → 12 s) | `exception_type = AgentTimeoutError` | none (no `result` event) | `ok`, `limit_hit = timeout`, reward 1 | $0.0178 `owl_estimate` |

- The subtype strings match `_LIMIT_BY_SUBTYPE` in `owl/gate.py`.
- `--max-budget-usd` applies under OAuth: the run stopped at ~$0.013 for a $0.01 cap.
- The cut stream carries `timestamp` on its events (17 in the timeout trial) and the session transcript
  exists, so the estimate replaces the missing `total_cost_usd`.
- Harbor's trial `config.json` does not record the timeout multipliers, so conformance cannot verify
  them after the fact; the forced timeout shows they reach Harbor.

## Checks asked by T21

| Check | Result |
|---|---|
| Preamble in the first `user` message | Present in every trial (conformance) |
| `--max-budget-usd` with OAuth | Applied |
| `rate_limit_event` states | Only `allowed`; no `allowed_warning`, no `rejected` |
| Max gap between events per variant | ≤ 10.6 s; `stall_minutes: 5` leaves ample margin |
| gentle-ai telemetry | `GENTLE_AI_TELEMETRY=0` in the agent env and the telemetry Stop hook ran without output or errors; the session itself prints no "disabled" string (the spike recorded it, `spike-gentle-ai.md`) |
| gentle-ai review stop-hook | Fired (`stop_hook_summary`, hookCount 2, 31 ms, `preventedContinuation: false`, no errors); no extra turns on this easy task, so the D3 risk stays open and is covered by the limits |

## Concurrency

**2, final.** No `infra` and no timeout at concurrency 2 in `main-v2` (six variants, two at a time).
Design "Línea de corte" item 1 (drop to 1 on `infra` or timeouts) does not fire.

## Revisión 4 (T38, pins del corte 2026-10-28)

Haiku 5.5 (`anthropic/claude-haiku-5-5`), OAuth, Claude Code 2.1.312, Harbor 0.25.0, `owl run --round` con el
runner real, 2026-11-03. Variantes en sus pins del corte: navori 0.12.3, gentle-ai v4.3.1, superpowers
v7.0.1@2ce8aa15, ponytail main@09c434ab. 10 trials, $0.055 equivalente API en total; ninguno cuenta para la
ronda.

**Definiciones de ronda.** Efímeras, en `jobs/smoke-r1/round-<name>/` (git-ignorado, nunca pre-registradas),
con `cutoff_date` y `pins`, el preámbulo de `specs/r1-refresco/pilot/preamble.md` y los precios de dos tramos
de `cost-validation.md` §"Revisión 4". `main` corre las seis variantes sobre `tasks/02-smoke-patient` a
concurrencia 2 con los límites de la ronda (3.0 / 2.0 / 300 / "5.00"). Los forzados corren `vanilla-default`
sobre `tasks/00-smoke` con un límite cambiado. Gate con la definición de ronda, como en T21:
`check_jobs(Path('jobs/smoke-r1/<dir>'), Round.load('jobs/smoke-r1/round-<name>'))`.

### Hallazgos (corregidos antes de este registro)

| Corrida | Hallazgo | Causa raíz | Corrección |
|---|---|---|---|
| forzado `max_budget_usd = "0.01"` | Con Haiku 5.5 un trial de `00-smoke` cuesta ~$0.002: el tope de T21 ya no se alcanzaría | Precio ~10× menor que Haiku 4.5 | Tope forzado a `"0.0005"` |
| forzado de presupuesto | `infra` ("zero tokens used: never reached the model") en un trial que gastó $0.00088 | Con 2.1.312, un `error_max_budget_usd` en el primer turno deja `usage` en cero y reporta los tokens solo en `modelUsage` (14 013 cache read, 3 394 cache write, 128 output); el gate leía solo `usage` (`owl/gate.py`) | El gate suma también `inputTokens`, `outputTokens`, `cacheReadInputTokens` y `cacheCreationInputTokens` de `modelUsage` (no los tamaños de ventana); `tests/test_gate.py::test_budget_stop_on_first_turn_counts_model_usage` |
| forzado `agent_timeout_multiplier = 0.02` (600 s → 12 s) | El trial terminó `success` en 9 s: no se cortó | Haiku 5.5 resuelve `00-smoke` en menos de 12 s | Multiplicador a `0.005` (3 s), `jobs/smoke-r1/timeout-v2` |

### Seis variantes (`jobs/smoke-r1/main`)

Todas `ok` con conformidad de ronda: modelo, versión, `max_turns`, `max_budget_usd`, multiplicadores de
`lock.json`, artefactos y preámbulo en el primer mensaje `user`. Además reward 1, `cost_source = reported` y
sin `infra`. La estimación con dos tramos coincide con `total_cost_usd` en las seis.

| Variante | Costo | Turnos | Plugins / MCP | Herramientas | Hueco máx. entre eventos | Agente | `rate_limit_event` |
|---|---|---|---|---|---|---|---|
| vanilla-default | $0.0039 | 9 | — / — | 23 | 2.2 s | 13.2 s | `allowed` |
| placebo | $0.0041 | 10 | — / — | 23 | 2.3 s | 13.0 s | `allowed` |
| superpowers | $0.0040 | 9 | `superpowers` / — | 23 | 2.8 s | 16.9 s | `allowed` |
| ponytail | $0.0033 | 7 | `ponytail` / — | 23 | 2.7 s | 14.4 s | `allowed` |
| gentle-ai | $0.0127 | 9 | `engram` / `context7`, `engram` | 46 | 2.4 s | 19.3 s | `allowed` |
| navori | $0.0222 | 15 (4 eventos `result`) | — / `engram` | 30 | 3.9 s | 73.2 s | `allowed` |

Condiciones efectivas (T29 D) iguales en las seis: `permissionMode` `bypassPermissions` y
`per_turn_effort_active` `true`. `output_style` es `default` salvo gentle-ai, que trae `Gentleman`: es su
persona por default (spike §"v4.3.1") y se mide tal cual. La diferencia en herramientas viene de los MCP
de cada variante.

### Forzados (`vanilla-default` sobre `tasks/00-smoke`)

| Forzado | Evidencia de Harbor | subtype de `result` | Gate | Costo |
|---|---|---|---|---|
| `max_turns = 2` | `agent.kwargs.max_turns = 2` | `error_max_turns` | `ok`, `limit_hit = max_turns`, reward 0 | $0.0013 `reported` |
| `max_budget_usd = "0.0005"` | `agent.kwargs.max_budget_usd = "0.0005"` | `error_max_budget_usd` (`terminal_reason: budget_exhausted`) | `ok`, `limit_hit = max_budget`, reward 0 | $0.00088 `reported` |
| `agent_timeout_multiplier = 0.005` (600 s → 3 s) | `lock.json` `agent_timeout_multiplier = 0.005`; `exception_type = AgentTimeoutError` | ninguno (sin evento `result`) | `ok`, `limit_hit = timeout`, reward 0 | $0.00024 `owl_estimate` |

- `--max-budget-usd` aplica con OAuth: el run paró en $0.00088 con tope de $0.0005 (un turno).
- Con el timeout cortado, el transcript de sesión existe y la estimación reemplaza el `total_cost_usd` que falta.

### Chequeos pedidos por T21

| Chequeo | Resultado |
|---|---|
| Preámbulo en el primer mensaje `user` | Presente en cada trial (conformidad) |
| `--max-budget-usd` con OAuth | Aplica |
| Estados de `rate_limit_event` | Solo `allowed`; ni `allowed_warning` ni `rejected` |
| Hueco máx. entre eventos por variante | ≤ 3.9 s; `stall_minutes: 5` deja margen amplio |
| Telemetría de gentle-ai | `GENTLE_AI_TELEMETRY=0` en el `init` y en el env del agente (`config.json`); el hook `Stop` `gentle-ai telemetry runtime claude --json` corrió sin errores |
| review stop-hook de gentle-ai | Se disparó (`stop_hook_summary`, `hookCount` 2, 94 ms, `hookErrors` vacío, `preventedContinuation: false`); sin turnos extra en esta tarea fácil |

### Concurrencia

**2, definitiva.** Sin `infra` ni timeouts a concurrencia 2 en `main`. El punto 1 de "Línea de corte" del
diseño (bajar a 1 ante `infra` o timeouts) no aplica.
