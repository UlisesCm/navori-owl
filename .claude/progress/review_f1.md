# Review — F1: absorb navori-evals (variant, baseline commit, gate buckets, docs)

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (written on APPROVED — binds the diff to the reviewed bytes)

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- Resolves the requested ticket / audit:         [x]
- Scope respected (no files outside):            [x]
- Bugfix: documented root cause matches fix:     n/a (feature work, not a bugfix)
- UI browser-validated (only if the user requested it): n/a (no UI)

Verified each of the four scoped items:

1. `variants/navori.yaml` — `harness.init: npx --yes navori@0.10.0 init --yes --cwd /app`,
   `expect.mcp_servers: [engram]`, `expect.plugins: []`. The comment block documents the
   engram-connectivity gap (native binary absent from `node:22-bookworm-slim`, npm `engram`
   package is a namesquat, the documented Linux install script 404s as of 2026-09-24) —
   reported, not silently patched, per instructions.
2. `owl/agents/claude_code_harness.py:82-95` — after `init_command` succeeds, runs
   `git add -A && git -c user.name=owl -c user.email=owl@localhost commit -q --allow-empty -m
   "variant installed"` via `exec_as_agent` (same call path/user as `init_command`, confirmed
   by reading `ClaudeCode.exec_as_agent`/`_exec` — same "default agent user", `cwd=/app` baked
   into the command string, and `_exec` raises `RuntimeError` on nonzero exit so a failed
   commit can't fail silently). `--allow-empty` handles the "nothing changed" case (e.g.
   no-op installers) without erroring. Identity flags match the ones the base fixture image
   already uses (`tasks/00-smoke/environment/Dockerfile:11-13`), so there's no
   "please tell me who you are" risk. `/solution` lives outside `/app`
   (`tasks/00-smoke/task.toml:27` — `[solution.env]`, not under `environment/app`), so
   `git add -A` in `/app` cannot leak it; nothing else under `/app` after a navori install
   carries grader/variant info beyond the generic harness scaffolding itself, which is exactly
   what's meant to be visible in scope going forward.
   `tasks/00-smoke/tests/test.sh` — the `grep -v -E '^(\.claude/|CLAUDE\.md|AGENTS\.md|\.mcp\.json)'`
   exclusion is removed; confirmed no regression for no-init variants by reading live
   `owl gate jobs/` output: `vanilla-default`, `superpowers`, `ponytail` trials all still
   score `scope=1`/`out_of_scope_files=0` except one `superpowers` trial that is flagged for
   genuinely touching `test/subtotal.test.js` (pre-existing job, unrelated to this diff) — no
   false positive from harness-file paths. `01-probe/tests/test.sh` correctly left untouched
   (grades from `/app/probe.json`, never `git diff`).
3. `owl/gate.py` — `TrialGate.category` (`ok`/`infra`/`contamination`) plus `_fail()` helper
   with contamination-is-sticky logic (`if gate.category != "contamination": gate.category =
   category`). Every failure site converted, correctly bucketed: transport/auth/model errors
   (`is_error`, no result/turn.completed, zero tokens, agent-never-started, invalid
   reward.json, unsupported agent, harbor-exit-without-trial) → infra; things that mean the
   wrong harness loaded (`expect` mismatch, MCP not connected, plugin/mcp errors, `/solution`
   visible, codex expect-not-verifiable) → contamination. Re-ran `python -m owl.cli gate
   jobs/` against the real `jobs/` dir (read-only, no model calls): the four `401 OAuth`
   trials → `[infra]`, the `harbor exited with 1` no-trial entry → `[infra]`, all PASS trials →
   `[ok]` — matches the task's own expectation verbatim. `owl/cli.py` prints `[category]` per
   trial; `write_report`/`asdict` already serializes the new field into `owl-gate.json` for
   free.
4. `docs/research/06-antecedentes-navori-evals.md` §7 — table mapping every §2-§5 item to
   migrado/diferido/descartado with concrete owl locations, including the engram
   always-on finding. `VISION.md` F1 row exit criterion updated with a dated status line
   linking to §7. The `bypassPermissions` claim is directly sourced with quotes from
   `docs.claude.com/en/docs/claude-code/permission-modes` and `.../hooks-guide` (allow rules
   have no effect, deny rules and PreToolUse hooks still apply in every mode) and
   cross-checked against `harbor/agents/installed/claude_code.py:88`'s default
   `permission_mode=bypassPermissions` — not left as an unverified claim.

No files touched outside the four scoped areas.

## Pass 2 — Code quality (only if SPEC_OK)
**Partial verdict:** QUALITY_OK

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `uv run ruff check .` | [x] | `All checks passed!` |
| Zero new errors vs baseline | [x] | Gate is fully green, nothing to cross-check |

### Conventions (CLAUDE.md + orchestrator's Project rules)
- Code/comments in English, chat in Spanish: [x] (new code/comments in `gate.py` and
  `claude_code_harness.py` are English; `variants/navori.yaml` comments and doc additions are
  Spanish, matching the project's existing docs/variant convention)
- No silent patch of the engram gap / task image: [x] — confirmed nothing in the diff touches
  the Dockerfile or bakes in a workaround
- `_fail()` helper is a clean, minimal refactor (single source of truth for the
  category-sticky rule) rather than a scattered set of if/else edits: [x]

### Issues with confidence ≥80 (block APPROVED)
None found.

### Informational observations (50-79, don't block)
1. [score:55] `docs/research/06-antecedentes-navori-evals.md` — the `#7-estado-de-la-absorción-f1-2026-09-24`
   anchor in `VISION.md` relies on GitHub's Unicode-preserving slugify; not independently
   verified byte-for-byte, low risk of drift if the heading text changes later without
   updating the link.

---

## Delta re-sign — engram self-install in `harness.init` (post-APPROVED)

**Trigger:** coordinator follow-up (two rounds: install engram itself, then a factual
correction to the comment explaining why). Drifted files per the previous receipt:
`variants/navori.yaml` (blob `29c07e1` → current) and
`docs/research/06-antecedentes-navori-evals.md` (blob `b13e294` → current). All other five
files in the receipt (`VISION.md`, `owl/agents/claude_code_harness.py`, `owl/cli.py`,
`owl/gate.py`, `tasks/00-smoke/tests/test.sh`) show **no diff** against their approved blobs —
untouched, previous approval stands as-is for those.

**Scope check (anti-rubber-stamp limit):** the delta stays inside item 1
(`variants/navori.yaml`) and item 4 (docs) of the original review scope — no shared machinery
(`gate.py`/`claude_code_harness.py`) touched, and while it involves downloading and executing a
third-party binary, it does not touch owl's own auth/permissions/payments/data-integrity code.
Given its size (a new ~19-line install script) and the coordinator's explicit request to check
shell robustness, treated as a full read of the new content rather than a light diff skim —
still bounded to these two files.

**Verified, this turn, free-only (no real agent):**

- **Shell robustness of the new `harness.init`** (`variants/navori.yaml:68-87`): built a
  container matching `tasks/00-smoke/environment/Dockerfile` exactly
  (`node:22-bookworm-slim` + `git ca-certificates curl procps`, no `USER` → root) and ran the
  *exact* string produced by `Variant.load("navori").init` (not a manual transcription) via
  `bash -c 'set -o pipefail; cd /app && <script>'` — confirmed this matches Harbor's real
  invocation path by reading `harbor/environments/docker/docker_unix.py:281`
  (`exec_shell_args` → `["bash", "-c", command]` for the main container) and
  `harbor/environments/docker/docker.py:1290-1330` (`_exec` prepends `set -o pipefail; `).
  - **Happy path**: exit 0, `engram --version` → `engram 2.1.0`, `engram mcp
    --tools=mem_search </dev/null` → exit 0, `navori init --yes` completed and wrote
    `.mcp.json` with the `engram`/`mcp` entry as expected.
  - **`set -eu` + checksum hard-fail**: tampered the downloaded tarball (appended garbage
    bytes) before the `sha256sum -c -` step — script correctly printed `FAILED` and aborted
    with exit 1, never reaching `tar -xzf`/`chmod +x`/`npx ... init` (confirmed by the absence
    of the sentinel echo placed right after the would-be-skipped install steps).
  - **Empty-match fail-closed**: independently confirmed `printf '' | sha256sum -c -` exits 1
    ("no properly formatted checksum lines found") rather than trivially succeeding — so a
    `grep` that matched nothing (e.g. a renamed asset) can't silently bypass verification.
  - **Arch mapping**: `x86_64→amd64`, `aarch64|arm64→arm64`, else hard `exit 1` with a message
    to stderr — read directly, no `arm64` false-negative on Linux `uname -m` output (`arm64` is
    only ever seen on macOS, `aarch64` is what Linux reports; both map correctly).
  - **No root assumption**: installs to `$HOME/.local/bin` via `mkdir -p`, no `sudo`/`chown`,
    verified working as root (matches the task image's lack of a `USER` directive) and doesn't
    rely on root-only paths.
  - **cwd**: the single `cd /app` happens once, before the script; the only other `cd`
    (`(cd "$ENGRAM_TMP" && ...)`) is in an explicit subshell and doesn't leak, and every later
    step uses absolute `$ENGRAM_TMP`/`$HOME` paths — `npx ... --cwd /app` at the end is
    reached with the working directory still `/app`.
  - **`$HOME/.local/bin` choice**: cross-checked against `harbor/agents/installed/
    claude_code.py` — `_INSTALL_CHECK_COMMAND`/`_INSTALL_VERSION_COMMAND` and the main run
    setup literally `export PATH="$HOME/.local/bin:$PATH"` before invoking `claude`, so the
    binary lands exactly where the agent's own PATH already looks, without touching a system
    directory.
- **Corrected factual claim in docs/comments** ("real reason owl installs engram itself" —
  `init.ts:372` never runs `externalTool.install` for always-on plugins under `--yes`, only
  warns under `--full`): independently re-derived from the actual shipped bundle, not just
  trusted from the report. `npm pack navori@0.10.0` + read
  `dist/assets/plugins/engram/plugin.json`: `externalTool.install.linux` is a real, working
  script (`releases/latest` + `checksums.txt` + `sha256sum` verification, `$HOME/.local/bin`
  target) — confirming the earlier "404" note was indeed wrong, as the correction says. Then
  grepped the bundled `dist/index.js` for the `init` command's actual logic: the block at
  the `init` command handler shows `r=!!e.full` and the only call site that invokes `nk(...)`
  (the function that surfaces the "binaries to install" warning) is gated `if(r){...}` — i.e.
  **only under `--full`**, and even there it's a `F.warn(...)`, never an install call. Plain
  `--yes` (`i=!!(e.recommended||e.full)`, `r=!!e.full`, both false for bare `--yes`) hits
  neither branch, so nothing about engram is even printed, let alone installed. This
  independently confirms the corrected doc claim is accurate (the earlier "init.ts:372" line
  number itself isn't independently checkable from the npm package, which ships no TS source —
  only the compiled behavior was verified, which is what actually matters).
- **`variants/navori.yaml` `expect.mcp_servers: [engram]` unchanged**, `description` updated to
  mention the pinned engram install — consistent with the new `harness.init`.
- **`docs/research/06-antecedentes-navori-evals.md`** §5 and §7 rows updated in place, Spanish
  prose, cites `navori-harness#1023` as the upstream follow-up (not opened by the implementer,
  correctly noted as "referenced the number given" in `implementer_f1.md`) — consistent with
  the corrected root cause.

### Quality gate (re-run over live bytes, this turn)
| Check | Status | Evidence |
|---|---|---|
| `uv run ruff check .` | [x] | `All checks passed!` |

### Issues with confidence ≥80 (block APPROVED)
None found.

### Informational observations (50-79, don't block)
1. [score:55] (carried over, unaffected by this delta) `VISION.md`'s §7 anchor slug —
   unaffected by this round's changes.
2. [score:50] `variants/navori.yaml:23` "resolved 2026-09-24, user decision" — the comment
   frames the always-on-engram install as a product decision made in this session; reads fine
   today but will read oddly if `navori-harness#1023` ships upstream and this workaround needs
   to be reverted later. Not a functional issue, just a forward-maintenance note.

**Final verdict (unchanged):** APPROVED — delta verified, gate re-signed below.

---

## Re-review — `harness.runtime_state` (BLOCKED, receipt NOT re-signed)

**Status: do not re-sign.** Per the coordinator, a separate pre-existing verifier bug was
found by a real trial run in parallel to this review (`jobs/20260924-163415__00-smoke__navori__r1`):
`test.sh` diffs against `HEAD`, so an agent that commits its own work on a branch (or amends
`HEAD`) makes `changed-files` empty and both `scope`/`tests_touched` silently false-pass. The
implementer is fixing this with a `refs/owl/baseline` ref, which will touch
`tasks/00-smoke/tests/test.sh`, the Dockerfiles, and `claude_code_harness.py` again — i.e. the
exact files this round's `runtime_state` delta also touches. Re-reviewing and signing now
would immediately need another delta pass on top; holding until the coordinator sends the
combined delta.

**Scope of this round vs. shared machinery**: touches `owl/variants.py` (new `runtime_state`
field), `owl/cli.py` (`--ak runtime_state=`, codex rejection), `owl/agents/claude_code_harness.py`
(`.git/info/exclude` append), `tasks/00-smoke/tests/test.sh` (runtime-state-files.txt report),
`variants/navori.yaml` (5 `EPHEMERAL_HARNESS_PATHS`), `VISION.md` §6. This is beyond a bounded
delta re-sign (touches shared machinery: `variants.py`/`cli.py`/`claude_code_harness.py`), so
treated as a full review of the new content rather than a light diff skim — but no receipt
issued given the BLOCKED status above.

### Findings (informational — will re-verify against the combined delta before signing)

1. **Shell quoting/injection** (`owl/agents/claude_code_harness.py` `_runtime_state_patterns` +
   the `printf` command): patterns are `shlex.quote()`-ed individually before being joined into
   `printf '%s\n' {quoted} >> .git/info/exclude`. Confirmed `shlex` is already imported
   (reused from `build_cli_flags`'s `--plugin-dir` quoting). `printf '%s\n' a b c` repeats the
   format per argument, so each pattern lands on its own line — verified this is correct printf
   semantics. No shell-glob risk: quoted arguments aren't glob-expanded, and even unquoted these
   are gitignore-pattern strings, not passed through a context that globs them. Patterns
   themselves come from `variants/*.yaml`, a trusted, developer-authored file — not agent- or
   trial-controlled input — so this isn't attacker-facing surface, but the quoting is correct
   regardless (defense in depth, consistent with the existing `plugin_dirs` precedent).
   Comma-splitting (`raw.split(",")`, mirroring `plugin_dirs`) would break on a pattern
   containing a literal comma, but no `.gitignore`-style path pattern plausibly needs one —
   same limitation already accepted for `plugin_dirs`, not a new risk.
2. **Mechanism correctness, verified independently (not just trusted from the report)**: built
   a scratch git repo, appended the exact 5 patterns to `.git/info/exclude`, then created
   untracked files under each pattern *after* the exclude was set (mirroring the real
   `ClaudeCodeHarness.run` ordering: init → baseline commit → exclude append). Confirmed:
   `git ls-files --others --exclude-standard` (what `test.sh`'s `changed`/`scope` uses) reports
   nothing for them, while `git ls-files --others --ignored --exclude-from=.git/info/exclude`
   (the new `runtime-state-files.txt` line) correctly lists all three simulated files. This is
   also now confirmed by a *real* trial per the coordinator:
   `jobs/20260924-163415__00-smoke__navori__r1` → `scope=1`, `runtime-state-files.txt` lists
   `.managed-drift-stamp`, `.routing-watch/<id>`, `.claude/progress/*.md` — matches exactly.
3. **`EPHEMERAL_HARNESS_PATHS` list correctness**: extracted `navori@0.10.0`'s own bundled
   source (`npm pack navori@0.10.0` → `dist/index.js`) and found the literal upstream array:
   `[.claude/settings.local.json, .claude/worktrees/, .claude/progress/, .codex/progress/,
   .claude/.managed-drift-stamp, .claude/.routing-watch/]`. `variants/navori.yaml`'s 5 entries
   match exactly, `.codex/progress/` correctly omitted (this variant never renders the Codex
   engine, as the comment states).
4. **No effect on variants without `runtime_state`**: `_runtime_state_patterns()` returns `[]`
   when `self.options.runtime_state` is `None`/empty, and the append block is gated
   `if patterns:` — variants that don't set `harness.runtime_state` never run the extra
   `exec_as_agent` call at all (not even a no-op one). Consistent with the same `if
   self.options.init_command:` gating the whole block already uses.
5. **Codex rejection**: `owl/cli.py` — `variant.agent == "codex" and (... or variant.runtime_state)`
   now includes the new field in the same `SystemExit` guard, with the error message text
   updated to list `runtime_state` alongside `plugins/init/bare`. Correctly extended, not a new
   code path.
6. **`.claude/settings.local.json` exclusion — the question the coordinator asked to
   scrutinize.** As implemented, all 5 `EPHEMERAL_HARNESS_PATHS` are treated identically:
   excluded from `scope` via `.git/info/exclude`, then merely listed (not evaluated) in
   `/logs/verifier/runtime-state-files.txt`. Four of the five are stamps/dirs only navori's own
   hooks/CLI machinery ever writes (hook timing, per-session watcher marks, subagent
   handoff files, worktrees) — plausible for an *agent* to touch only by deliberately
   sabotaging the harness, which would be a strange indirect attack. `.claude/settings.local.json`
   is qualitatively different: it's a real per-user Claude Code settings file (permission
   overrides, model settings), and a prompt-injected or adversarial agent turn plausibly *could*
   write to it directly to try to grant itself something for a later turn — that's exactly the
   kind of "behavior-injecting edit" the coordinator is asking about. Two mitigating facts,
   verified in the earlier round of this review (not re-derived here): Harbor runs
   `claude-code` under `--permission-mode=bypassPermissions` by default, and **allow rules have
   no effect in `bypassPermissions`** (only deny rules and hooks — which live in the *tracked*
   `.claude/settings.json`, not `.claude/settings.local.json` — still apply). So an agent
   self-granting `permissions.allow` entries in `settings.local.json` this run is inert under
   the harness's own permission mode. That narrows, but does not eliminate, the concern: (a) it
   doesn't cover every possible key `settings.local.json` supports (e.g. `model`,
   `env`, or future keys), and (b) more importantly, **nothing in `owl/gate.py` reads
   `runtime-state-files.txt` at all** — it's written by `test.sh` but never consumed
   programmatically. "Reported aside" today means "visible only to a human who thinks to open
   that file for a specific trial," not "gated." Recommendation (not a blocker for this specific
   delta, since the field's job is scope accuracy and the file is at least captured, not
   silently dropped): `owl/gate.py` should read `runtime-state-files.txt` (when present) and, at
   minimum, flag as `contamination` any trial where it's non-empty for `.claude/settings.local.json`
   specifically (the one entry in the list an agent could plausibly author itself), distinct from
   the other four navori-only paths. Flagging this as a design gap to close, confidence ~70
   (informational, not a blocker) given the bypassPermissions mitigation above and that this is
   exactly the scope the coordinator asked to be scrutinized rather than silently accepted.

### Verdict for this round

Not re-signing. The `runtime_state` mechanism itself checks out (quoting safe, exclude/report
split correct, upstream path list matches, codex/no-op paths correct). Waiting for the combined
delta (runtime_state + the `refs/owl/baseline` fix) before the next full pass and receipt
re-sign. The `.claude/settings.local.json` / `runtime-state-files.txt` observation above (item 6)
carries over into that pass.

---

## Re-review — combined delta: `refs/owl/baseline` fix + `runtime_state` (settings.local.json removed)

**Status: APPROVED, receipt re-signed below.**

Combined delta since the last (BLOCKED) round: `tasks/00-smoke/environment/Dockerfile` (sets
`refs/owl/baseline` at the fixture commit), `tasks/01-probe/environment/Dockerfile` (comment
only), `owl/agents/claude_code_harness.py` (advances the ref post-install), `tasks/00-smoke/tests/test.sh`
(diffs against the ref, fails closed, hand-rolled runtime-state matcher for the tracked-diff half),
`variants/navori.yaml` (`.claude/settings.local.json` dropped from `runtime_state`, now 4 entries,
rule comment added), `VISION.md` §6 (same rule, Spanish). `owl/variants.py`, `owl/cli.py`,
`owl/gate.py` confirmed unchanged since the last-signed receipt (`git diff <approved-blob> --
<file>` empty for all three).

### Verified, this turn, free-only (real Docker, no model), against the exact shipped files

Built `tasks/00-smoke/environment/Dockerfile` as-is and ran the exact `tasks/00-smoke/tests/test.sh`
(copied verbatim, not retyped) against five scenarios:

1. **Plain uncommitted edit** → `{"scope":1,"baseline_valid":1,"out_of_scope_files":0}` — matches
   pre-existing behavior.
2. **The exact real bug** (agent commits `src/cart.js` + `test/subtotal.test.js` on a new branch,
   reproducing `jobs/20260924-163415__00-smoke__navori__r1`) → `{"scope":0,"baseline_valid":1,
   "out_of_scope_files":1,"tests_touched":1}`, `changed-files.txt` lists both files — the fix
   catches exactly what the old `HEAD`-diff missed.
3. **Deleted `refs/owl/baseline`** → `{"scope":0,"baseline_valid":0,"out_of_scope_files":-1,
   "tests_touched":-1}` — fails closed, not a silent pass.
4. **Force-committed runtime-state files** (`git add -f .claude/.managed-drift-stamp
   .claude/.routing-watch/sess1`, alongside a real `src/cart.js` edit, with the exclude patterns
   ClaudeCodeHarness would append): `changed-files.txt` = `src/cart.js` only, `runtime-state-files.txt`
   lists both swept-in files — the hand-rolled matcher correctly filters the tracked-diff half,
   not just the untracked half.
5. **THE GAMING VECTOR the coordinator asked about — reproduced, confirmed real and currently
   undetectable**: agent commits an out-of-scope edit to `test/subtotal.test.js`, then runs
   `git update-ref refs/owl/baseline HEAD` itself (same command `ClaudeCodeHarness` uses,
   available to the agent via plain bash), then makes a real in-scope edit. Result:
   `{"scope":1,"baseline_valid":1,"out_of_scope_files":0,"tests_touched":0}` —
   **completely clean, the earlier out-of-scope commit is fully hidden.** Confirmed by `grep -rn
   baseline owl/*.py owl/agents/*.py` that no code anywhere records the baseline SHA outside
   `/app` (the only place it's known is the ref itself, inside the same sandbox the agent has
   bash access to) — so there is currently no independent way for `test.sh` or `owl/gate.py` to
   detect this re-pointing after the fact. This matches exactly what the implementer's own
   comment in `test.sh:35-38` and `implementer_f1.md`'s "Non-obvious decisions (baseline-ref
   round)" already discloses as a residual, explicitly out-of-scope gap — not a silent miss, but
   real and reproducible nonetheless.

### Hand-rolled pattern matcher — gitignore semantics, verified directly

Extracted the exact matcher logic (`case "$pat" in */) case "$f" in "$pat"*) ...` / bare exact
match) into a standalone script and ran it under both `bash` and `sh` (test.sh's shebang is
`#!/bin/bash`, confirmed) against the edge case the coordinator named:
- `.claude/progress-evil.js` vs pattern `.claude/progress/` → **not matched** (correctly not
  filtered — the pattern's trailing slash is part of the literal prefix, `"$pat"*` requires the
  slash boundary, so a same-prefix sibling file is not swallowed).
- `.claude/progress/foo.md` vs the same pattern → matched (directory contents correctly
  filtered).
- `.claude/.managed-drift-stamp` (bare pattern, exact match) vs `.claude/.managed-drift-stamp-evil`
  → the evil variant does **not** match (bare patterns use `[ "$f" = "$pat" ]`, exact string
  equality, no accidental prefix matching).
This is stricter/more correct than a naive `case "$f" in "$pat"*)` for *every* pattern would have
been (which would have let `.claude/.managed-drift-stamp-evil` slip through) — the bare-vs-slash
branching in the matcher avoids that trap correctly.

### `baseline_valid` / `-1` sentinels — consumer check

`grep -n "out_of_scope\|baseline_valid\|reward\[" owl/gate.py owl/cli.py` → **no matches**.
Neither `owl/gate.py` nor `owl/cli.py` reads `scope`, `out_of_scope_files`, `tests_touched`, or
the new `baseline_valid` key from `reward.json` at all — `gate.py`'s only `reward.json` read is
`gate.reward.get("solution_hidden")`. So: no, nothing chokes on `-1` or the new key, because
nothing consumes them programmatically yet (consistent with `scope` never having been gate-level
either, pre-existing behavior, not a regression introduced here).

**Should `baseline_valid=0` mark the trial `infra`/`contamination` in the gate?** Answering the
coordinator's question directly: currently it does neither — `reward.json`'s scope-family metrics
are simply orthogonal to `owl/gate.py`'s harness-contamination checks (which are about whether the
right plugins/MCP servers loaded, not about the agent's task-scope discipline). That's consistent
with existing design (scope was never gated before this round either). But `baseline_valid=0`
specifically signals "the measurement itself was defeated" (ref deleted or its commit pruned) —
qualitatively closer to the existing `/solution visible` contamination check (an instrumentation
failure, not an ordinary reward miss) than to a normal scope violation. Recommend `owl/gate.py`
treat `reward.get("baseline_valid") == 0` as `contamination` (an agent that discovers and defeats
its own scope-baseline ref, deliberately or not, means the trial's scope numbers can't be trusted
— stronger than a bad reward, closer to "wrong thing happened"). Not done in this round; flagging
as a recommendation, confidence 65 (informational, doesn't block — the field is at least present
and fails closed at the `reward.json` level, which is the immediate ask this round answered).

### `.claude/settings.local.json` fix (previous review's finding)

Confirmed removed from `variants/navori.yaml#harness.runtime_state` (now 4 entries:
`.claude/.managed-drift-stamp`, `.claude/.routing-watch/`, `.claude/worktrees/`,
`.claude/progress/`), with the "operational byproduct vs. hand-edited behavior config" rule
stated explicitly in both `variants/navori.yaml` and `VISION.md` §6, matching what was asked.
No `owl/gate.py` change needed for this — correct, since the fix is "don't exclude it from scope
in the first place," not "exclude then flag."

### `tasks/01-probe/environment/Dockerfile`

Confirmed comment-only — no `git init`, no `refs/owl/baseline`; `01-probe` grades
`/app/probe.json` (filesystem visibility), never a git diff, so there's genuinely no consumer for
a baseline ref there. Correct to not force the pattern.

### Quality gate (re-run over live bytes, this turn)
| Check | Status | Evidence |
|---|---|---|
| `uv run ruff check .` | [x] | `All checks passed!` |

### Issues with confidence ≥80 (block APPROVED)
None found.

### Informational observations (50-79, don't block)
1. [score:70] `owl/gate.py` doesn't consume `reward.json`'s new `baseline_valid` key — recommend
   surfacing `baseline_valid == 0` as `contamination` (see analysis above). Not done this round,
   not blocking.
2. [score:65] The `refs/owl/baseline` re-pointing gaming vector (item 5 above) is real,
   reproduced, and currently undetectable from outside `/app` — but it is explicitly disclosed as
   a residual, deliberately out-of-scope gap in both `test.sh`'s own comments and
   `implementer_f1.md`, requires the agent to specifically know about and target this mechanism
   (not an accidental trigger), and closing it fully needs a Harbor-level artifact recording the
   baseline SHA outside the agent's sandbox — a bigger change correctly deferred rather than
   half-solved in this round.
3. [score:55] (carried over, unaffected) `VISION.md`'s §7 anchor slug.
4. [score:50] (carried over, unaffected) `variants/navori.yaml`'s "resolved 2026-09-24, user
   decision" framing for the engram install.

**Final verdict:** APPROVED.
