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
