# Review — F0 Harbor spike skeleton (fix cycle 2)

**Final verdict:** APPROVED
**Content receipt:** n/a — untracked files, not a git-tracked feature branch diff; no `navori receipt sign` target applies (repo confirmed as review-only invocation, no `<feature>` id provided by caller).

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- All 3 previously-blocking findings addressed as described in the task:
  - `owl/variants.py:69-83` `materialize_plugins()`: clones into `<target>.partial`, `rmtree`s any leftover partial before cloning, checks out the pinned ref, renames to `target` only after both subprocess calls succeed (no `check=True` raise mid-way leaves `target` populated). [x]
  - `owl/variants.py:18,50-55`: `Variant.load` now rejects any plugin `ref` that isn't a 40-char lowercase hex SHA (`_FULL_SHA_RE`), raising `SystemExit` with a clear message. Cache key `f"{plugin.name}@{plugin.ref}"` (variants.py:73) now embeds the full ref, not a 12-char prefix. [x]
  - `owl/gate.py:70-74`: `check_trial()` now iterates every MCP server in `system/init` and fails the gate (with a reason) if `status != "connected"`, including when `status` is absent (`None != "connected"`). This is on top of, not instead of, the existing name-set comparison. [x]
  - `owl/cli.py:85` records `harbor_exit_code` in `owl-variant.json`; `owl/gate.py:102-117` `check_jobs()` detects job dirs with zero trial subdirectories (no `config.json`) and synthesizes a failing `TrialGate` with reason `"no trial: harbor exited with {code}"`. [x]
  - `tasks/01-probe/tests/test.sh:15-17`: comment corrected — the code path (`gate.py:95-97`, `solution_hidden == 0` → fail) was already right; the comment now correctly states a real agent must produce `solution_hidden=1`. Comment-only, no functional change. [x]
- Scope respected: only the 4 files named in the task were touched (verified via targeted reads/greps; no unrelated files modified). [x]
- Bugfix: root cause documented in the prior review for each of the 3 findings matches the applied fix (non-atomic clone → temp+rename; name-only MCP check → per-entry status check; silent drop of failed jobs → synthetic FAIL record). [x]
- UI browser-validated: n/a, no UI in this diff.

## Pass 2 — Code quality (SPEC_OK)
**Partial verdict:** QUALITY_OK

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` (run this turn from repo root) |
| Zero new errors vs baseline | [x] | Same clean result as prior review; no regressions introduced |

### Edge cases checked
- Rename when target's parent is missing: `partial = target.with_name(target.name + ".partial")` shares `target`'s parent; `partial.parent.mkdir(parents=True, exist_ok=True)` runs before clone, so the parent exists by the time `partial.rename(target)` executes (same directory, no cross-fs rename risk). Confirmed via `owl/variants.py:75-81`.
- Partial leftover handling: on every call, if a stale `.partial` dir exists it's `rmtree`'d before re-cloning — no accumulation, no reuse of a half-finished clone. `owl/variants.py:76-77`.
- Both committed manifests' refs (`ponytail.yaml`, `superpowers.yaml`) verified programmatically: both are exactly 40 lowercase hex chars, pass `_FULL_SHA_RE` — `Variant.load` will not reject real data.
- Synthetic `TrialGate` shape (`owl/gate.py:109-115`) vs `write_report`/`cmd_gate`: uses the same dataclass as real trials, so `asdict()` in `write_report` serializes it identically; `cmd_gate`'s print line handles `None`/`[]` defaults for `cost_usd`, `reward`, `num_turns`, `plugins`, `mcp_servers` without crashing — verified by reading the format string against the dataclass defaults (gate.py:16-26, cli.py:100-107).
- `check_trial`'s new per-server status loop is additive to the existing name-set comparison (doesn't short-circuit or duplicate-suppress); multiple reasons can be appended for the same underlying failure, which is acceptable (informational, not a functional bug).

### Conventions (CLAUDE.md + Project rules)
- Code/comments in English, matches repo convention. [x]
- No new `any`/untyped constructs introduced. [x]

### Issues with confidence ≥80 (block APPROVED)
None.

### Informational observations (50-79, don't block)
1. [score:55] `owl/gate.py:114` — the synthetic failure's `reasons` message interpolates `code` which may be the string `"unknown"` (if `harbor_exit_code` is absent from an older/malformed `owl-variant.json`) or `0` (if harbor somehow exited 0 without producing a trial dir, e.g. wrote to a wrong `--job-name`). Neither breaks the gate, just a slightly confusing message in an already-rare edge case — not worth blocking.
