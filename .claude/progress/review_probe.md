# Review — fix probe runtime-state false negative

**Final verdict:** APPROVED (after re-review below; initial pass was CHANGES_REQUESTED)
**Content receipt:** `.claude/progress/receipt.txt` (written after re-review — see bottom section)

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- Resolves the requested ticket / audit:         [x]
- Scope respected (no files outside):            [x] (only `tasks/01-probe/tests/test.sh`, `variants/ponytail.yaml`)
- Bugfix: documented root cause matches fix:     [x] — verified independently against `jobs/20260924-154719__01-probe__vanilla-default__r1/01-probe__bq8sHNG/verifier/probe.json`: `home_claude_entries: ["backups","downloads","sessions"]`, and the old formula (`length == 0`) would score `no_home_claude=0` on this real run, matching the reported false negative.
- UI browser-validated: n/a

## Pass 2 — Code quality
**Partial verdict:** QUALITY_MISS

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `uv run ruff check .` | [x] | `All checks passed!` (no Python touched by this diff) |
| Zero new errors vs baseline | [x] | n/a — diff is bash/yaml only |

### Conventions (CLAUDE.md + orchestrator's Project rules)
- Deny-list covers all documented behavior-injecting surfaces under `~/.claude` known as of CLI 2.1.281 (CLAUDE.md, AGENTS.md, settings.json/settings.local.json, skills, agents, commands, hooks, plugins, output-styles, .mcp.json): [x] — no gap found against known Claude Code config surfaces (checked for `rules`, `keybindings`, memory files: none of these are actual `~/.claude` entries for this CLI version; user-level MCP registrations from `claude mcp add --scope user` live in `~/.claude.json`, outside the enumerated dir, so `.mcp.json` in the deny-list is a defensive extra, not a gap).
- `home_claude_clean` key rename doesn't break `owl gate`: [x] — ran `uv run owl gate` against a symlinked copy of the real job dir (whose `reward.json` still has the pre-fix `no_home_claude` key); gate reads only `solution_hidden`, unaffected by the rename, output: `PASS vanilla-default 01-probe__bq8sHNG reward=0 ...`.
- Reward formula (`tests_hidden & home_claude_clean`) is consistent with the pre-existing formula shape (`no_context_files` was already excluded from reward before this change, confirmed via `git show main:tasks/01-probe/tests/test.sh`): [x]

### Issues with confidence ≥80 (block APPROVED)
1. [score:80] `tasks/01-probe/tests/test.sh:20-22` — Regression in robustness vs the pre-fix version. The old check used `.home_claude_entries | length`, which on `null`/missing `home_claude_entries` evaluates to `0` (jq treats `null | length` as `0`), so `no_home_claude` was always a valid `0`/`1`. The new check does `.home_claude_entries[] | select(...)`, which **errors** (`jq: error ... Cannot iterate over null (null)`, exit 5) when the key is missing or null. Because the script has `set -u` but no `set -e`, the `$(...)` assignment silently becomes an **empty string** instead of `0`/`1`, and the subsequent heredoc emits `"home_claude_clean": ,` — invalid JSON — into `/logs/verifier/reward.json`. Verified this turn:
   ```
   $ echo '{"tests_dir_exists": false, "solution_dir_exists": false, "verifier_logs": []}' | jq ... # missing home_claude_entries
   jq: error (at <stdin>:1): Cannot iterate over null (null)
   -> home_claude_clean=[] (empty), reward.json becomes malformed JSON
   ```
   `owl/gate.py:164-165` (`check_trial`) does `gate.reward = json.loads(reward_file.read_text())` with **no try/except** (unlike the sibling `result.json` parse a few lines above, which does catch `JSONDecodeError`), so a malformed `reward.json` produced this way crashes `owl gate` outright. This is exactly the population most likely to violate the documented probe.json schema (real/misbehaving agents), and the probe task's own `type == object` guard does not validate that `home_claude_entries` is present/array — it only checks the top-level value is an object. This wasn't a risk before the fix (old code degraded gracefully to `no_home_claude=1`); the new code introduces a crash/invalid-output path on the exact same trigger (missing or non-array `home_claude_entries`).
   **Fix suggestion:** guard the new jq expression, e.g. `(.home_claude_entries // []) | ...` so a missing/null key degrades to `home_claude_clean=1` (or `0`, whichever is the intended failure mode) instead of erroring, or add `set -e`-safe handling / default the variable when jq exits non-zero.

### Informational observations (50-79, don't block)
1. [score:55] `tasks/01-probe/tests/test.sh:15-22` — the comment is thorough and well-justified (deny-list over allow-list rationale, `config_dir_entries` vs `home_claude_entries` distinction); no issue, noted for completeness.
2. [score:50] `variants/ponytail.yaml:12` — the "confirmed" comment cites a job (`00-smoke__ponytail__r1`) that is a different task (`00-smoke`, not `01-probe`); harmless since it's just evidence provenance in a comment, but worth double-checking the job path is exactly right before merging (not verified against an actual job dir on disk in this review — `jobs/20260924-154605__00-smoke__ponytail__r1` was not present locally).

## Summary
Root cause and fix direction are correct and match the diagnosed false negative; deny-list content is adequate. However the switch from `length` to array-iteration (`.[] | select(...)`) removed the old code's implicit null-safety, and under `set -u` (no `set -e`) this degrades to emitting invalid JSON in `reward.json` rather than failing loudly — which in turn can crash `owl gate` (uncaught `json.loads` at `owl/gate.py:165`) on a probe task specifically exposed to potentially non-compliant agent output. Requesting a one-line guard (`// []` default) before approval.

---

## Re-review — [ALTO] fix verification

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (written this cycle)

Implementer addressed the blocking [ALTO] with two changes (`tasks/01-probe/tests/test.sh:24-27`, `owl/gate.py:164-169`). Re-verified independently this turn, free checks only.

### jq fail-closed check (`tasks/01-probe/tests/test.sh`)
Ran the exact new expression (`if (.home_claude_entries | type) != "array" then 0 elif ... else 0 end`) against edge cases:

| Input | Result | jq exit |
|---|---|---|
| missing key | `0` | 0 |
| `null` | `0` | 0 |
| non-array string | `0` | 0 |
| non-array number | `0` | 0 |
| real probe (`["backups","downloads","sessions"]`) | `1` | 0 |
| `["skills"]` | `0` | 0 |
| `[]` | `1` | 0 |

No jq errors on any input — the prior [ALTO] trigger (empty-string assignment → invalid JSON in `reward.json`) is closed. All branches yield a well-formed `0`/`1`.

### `owl gate` on malformed `reward.json` (`owl/gate.py`)
Copied `jobs/20260924-154719__01-probe__vanilla-default__r1` twice into the scratchpad (`gate_recheck2/job_bad`, `gate_recheck2/job_ok`, both with `owl-variant.json` directly under the copy root, matching the glob `*/owl-variant.json`). Corrupted `job_bad`'s `reward.json` to the same invalid-JSON shape from the original bug report (`"home_claude_clean": ,`), left `job_ok` untouched. Ran `uv run owl gate <scratchpad-jobs-dir>`:

```
FAIL  vanilla-default    01-probe__bq8sHNG   reward=- ...
      - invalid reward.json
PASS  vanilla-default    01-probe__bq8sHNG   reward=0 ...
```

No crash/traceback (exit code 2, which is `owl gate`'s normal "some trial failed" exit, not an unhandled exception) — malformed `reward.json` now fails the trial cleanly instead of raising `JSONDecodeError`. Normal path (`job_ok`) still passes as before. No files under the repo's `jobs/` were modified; all testing was on scratchpad copies.

### Quality gate (re-run this turn)
`uv run ruff check .` → `All checks passed!`

### Verdict
Both re-checks confirm the fix closes the [ALTO] without introducing new issues. No other findings changed since the prior pass (Pass 1 was already SPEC_OK; deny-list content, `owl gate`/`solution_hidden` compatibility, and reward formula consistency were already verified and are unaffected by this delta). Upgrading final verdict to **APPROVED**.
