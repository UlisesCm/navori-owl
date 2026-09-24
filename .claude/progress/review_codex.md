# Review — owl run/gate: Codex CLI support

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (written on APPROVED — binds the diff to the reviewed bytes)

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- Resolves the requested ticket / audit:         [x]
- Scope respected (no files outside):            [x]
- Bugfix: documented root cause matches fix:     n/a (feature, not bugfix)
- UI browser-validated (only if the user requested it): n/a (no UI in this repo/task)

Verified against scope items:
- `owl/cli.py`: `AGENT_IMPORT_PATHS`/`DEFAULT_MODELS` per-agent, `--auth oauth` maps to `CODEX_FORCE_AUTH_JSON=1`
  with an early fail if `~/.codex/auth.json` is missing, `--auth api-key` needs no code change (Codex/Claude
  both default to their respective API key env vars). `_effective_model` rejects mixed-agent runs both with and
  without explicit `-m`. `codex` variants reject `plugins`/`init`/`bare` (owl/cli.py:24-27). `--ak variant_id=`
  now gated to `claude-code` only (owl/cli.py:49-53) — confirmed this was a real-run fix (Harbor's built-in
  `codex` agent schema has no `variant_id` kwarg; `implementer_codex.md:139-153`).
- `owl/gate.py`: dispatch via `_AGENT_CHECKS` map on `variant.get("agent", "claude-code")`, unknown agent fails
  loud (`gate.py:167-172`). `_check_claude_code` unchanged apart from builtin-plugin exclusion (diff shows the
  only change is splitting `path == "builtin"` / `source` ending `"@builtin"` plugins into `builtin_plugins`,
  the rest of the logic — init event, mcp_servers, `expect` comparison, result-event checks — is untouched).
  `_check_codex` reads `agent/codex.txt`, fails on `error`/`turn.failed` events, fails when no `turn.completed`
  event exists ("run did not finish"), fails when `turn.completed`'s `usage` sums to zero ("never reached the
  model"). Codex variants with non-empty `expect.plugins`/`expect.mcp_servers` fail loud instead of being
  silently ignored (gate.py:106-109). Cost/tokens overlaid from `result.json`'s `agent_result.cost_usd` for
  both agents (gate.py:154-168).
- `variants/codex-default.yaml`: `agent: codex`, empty harness, empty `expect`, matches the shape of
  `vanilla-default.yaml`.
- README "## Uso" section + VISION §13 line present and accurate.

**Real-run evidence checked this turn** (no new `harbor run` invoked, per instructions):
- Built a symlink dir in the scratchpad pointing at `jobs/20260924-153003__00-smoke__vanilla-default__r1` and
  `jobs/20260924-153348__00-smoke__codex-default__r1` (jobs/ itself never touched), ran
  `uv run owl gate <dir>` → both **PASS**, `reward=1`:
  ```
  PASS  codex-default      00-smoke__dzjA7zG   reward=1 cost=$0.0012 turns=1 plugins=[] builtin_plugins=[] mcp=[]
  PASS  vanilla-default    00-smoke__JrmiLJj   reward=1 cost=$0.0404 turns=7 plugins=[] builtin_plugins=['agents-md'] mcp=[]
  ```
- Read the real `agent/codex.txt`: events are exactly `thread.started`, `turn.started`, `item.started`/
  `item.completed` (agent_message, command_execution, file_change), `turn.completed` with a **flat** `usage`
  dict (`input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`,
  `reasoning_output_tokens`) — matches `_check_codex`'s parsing exactly (no nested `info`/`usage` wrapper, the
  implementer's documented open question). No `error`/`turn.failed` event was present in this positive sample,
  so that branch is still untested against a live log, but the shape it does handle (missing `turn.completed`,
  zero-usage `turn.completed`) is confirmed sound and does not silently pass a broken run.
- `result.json`'s `agent_result` shape confirmed identical to Claude's (`cost_usd`, `n_input_tokens`,
  `n_cache_tokens`, `n_output_tokens`, `model_usage`) — the cost overlay is correct and agent-agnostic.
- No secrets leak: `~/.codex/auth.json` is only checked with `.is_file()` and its **path** (not contents)
  appears in the `SystemExit` message (owl/cli.py:78-80) — same pattern as the pre-existing `--bare` check.
  Nothing in `agent/codex.txt` or the diff logs env var values.
- Claude path behavior unchanged apart from the `builtin_plugins` split: confirmed via diff — `_check_claude_code`
  is the prior `check_trial` body verbatim, only the plugin-partition lines are new.

## Pass 2 — Code quality (only if SPEC_OK)
**Partial verdict:** QUALITY_OK

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `uv run ruff check .` | [x] | `All checks passed!` |
| Zero new errors vs baseline | [x] | Gate is fully green; no per-file errors to cross-check |

### Conventions (CLAUDE.md + orchestrator's Project rules)
- Code/comments in English, chat in Spanish: [x] (code/comments in English, README/VISION prose in Spanish
  matching the project's existing docs language)
- No AI traces in code/comments: [x]

### Issues with confidence ≥80 (block APPROVED)
None found.

### Informational observations (50-79, don't block)
1. [score:65] `jobs/20260924-153348__00-smoke__codex-default__r1/00-smoke__dzjA7zG/result.json` —
   `cost_usd: 0.00119636` for `openai/gpt-6-luna` at 55,412 input tokens (50,176 cached) + 342 output +
   69 reasoning tokens. `gpt-6-luna` does not match any publicly documented OpenAI pricing SKU as of this
   review, so this cost is very plausibly a litellm/Harbor pricing-lookup fallback (e.g. defaulting to a
   cheap or zero-rate table for an unrecognized model id) rather than a real ChatGPT-plan-equivalent cost.
   Flagging per the task brief — not a code defect in this diff (the overlay code correctly relays whatever
   Harbor reports), but the resulting `$` figures in any codex-default report should not be trusted at face
   value until the pricing table is verified against `openai/gpt-6-luna` specifically.
2. [score:55] `owl/gate.py:127` — `_check_codex`'s error-branch (`type in ("error", "turn.failed")`) has not
   been exercised against a real negative sample (only a positive `turn.completed` run was captured); the
   implementer's own open-questions section already flags this. Low severity since the shape it *did* confirm
   (missing/zero-usage `turn.completed`) already prevents a broken codex run from silently passing, and the
   error-field fallback (`error.get("error") or error.get("message") or error`) degrades gracefully if the key
   name is off.
