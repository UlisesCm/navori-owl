# Review — F2 Lote 1 (T0 spike, T1+T2 verifier integrity, T3 gate)

**Final verdict:** APPROVED (cycle 3; see "Cycle 3" section below for the latest evidence and quality gate)
**Content receipt:** `.claude/progress/receipt.txt` (signed cycle 3, feature `f2`, target `main`, `status: ok`)

## Cycle 1 summary (superseded findings)

Cycle 1 verdict: CHANGES_REQUESTED. Pass 1 was SPEC_OK. Pass 2 blocked on one CRITICAL
(score 100): `owl_changes`'s `git diff --name-only "$OWL_BASELINE"` was fooled by
`git update-index --assume-unchanged <path>` (plain git plumbing, zero privilege) —
empirically reproduced against the built `tasks/00-smoke` image, making a real
tracked-file edit fully invisible to scope (`scope=1`, `out_of_scope_files=0`, empty
`changed-files.txt`). An informational note (score 65) also flagged missing
`core.fsmonitor`/hooks hardening on the git calls in `lib.sh`.

## Cycle 2 — re-review of the addendum

Per `.claude/progress/implementer_t1t2.md`'s "Addendum — reviewer CHANGES_REQUESTED,
addressed" section: `owl_changes` no longer uses git to decide "what changed" at all.
`owl_snapshot` (raw `find`/`sha256sum`/`readlink`, `.git` pruned) is compared against a
root-owned `/var/lib/owl/baseline.manifest`, refreshed by `ClaudeCodeHarness.run` as
root after moving `refs/owl/baseline`. Git is kept only for `baseline_valid`
(`owl_baseline`) and pristine blob reads (`owl_restore_pristine`, now `cat-file -p`
instead of `git show`), both routed through a new `_owl_git` wrapper hardened with
`GIT_NO_REPLACE_OBJECTS=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`,
`-c core.hooksPath=/dev/null -c core.fsmonitor= -c core.untrackedCache=false`.

### Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- `design.md` D6 point 3 rewritten to document the finding, the fix and its evidence;
  Contracts' `/var/lib/owl/` section, the `seal.sh` and `ClaudeCodeHarness.run`
  Components rows, and Failure modes (two new rows: assume-unchanged/skip-worktree,
  refs/replace/grafts) all updated consistently — checked against
  `specs/f2-suite-v1/design.md:70,80,134,210-239,551-553,596-597`.
- `tasks.md` T1/T2 remain `[x]`; still an honest reflection of what's implemented.
- Scope respected: `git status --porcelain` still shows only T1/T2/T3 files touched
  (`owl/gate.py`, `pyproject.toml`, `uv.lock`, `navori.config.json`, `tests/test_gate.py`
  untouched by this addendum, confirming T3's boundary).

### Pass 2 — Code quality
**Partial verdict:** QUALITY_MISS

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` (this turn) |
| `uv run pytest -q -m 'not docker'` | [x] | `5 passed` (this turn, `tests/test_gate.py`, untouched) |
| `uv run pytest -m docker tests/test_validate_docker.py -v` | [x] | `12 passed in 43-52s` (this turn, real Docker + `harbor`, no model) |

### The original CRITICAL: verified closed
Reran the exact cycle-1 repro against a freshly built image, this turn, no code
changes of my own:
```
git update-index --assume-unchanged package.json
echo MALICIOUS_INJECTED_BACKDOOR >> package.json
bash /tests/test.sh   # (unmodified test.sh)
```
→ `changed-files.txt` now contains `package.json`, `reward.scope == 0`,
`out_of_scope_files >= 1`. Matches `test_assume_unchanged_edit_is_still_counted`
(green in the 12-test run above). Confirmed closed.

### Additional adversarial checks run this turn (all pass, no new gap found)
- `.git` pruning is exact-path only (`-path /app/.git -prune`), never a nested
  `foo/.git` — correct direction of error (over-includes, never hides).
- Deleted files: union-of-paths diff (`base_map`/`cur_map`) correctly flags a path
  present only in the baseline manifest as changed — confirmed by code reading, no
  gap.
- Symlink handling: recorded by target string, never followed, confirmed by the new
  `test_symlink_out_of_app_is_flagged` (green).
- `refs/replace`/grafts: forged this turn against a live container
  (`git replace $base $fake`, tampered `test/subtotal.test.js`) — `_owl_git`'s
  `GIT_NO_REPLACE_OBJECTS=1` keeps `owl_restore_pristine` on the real content; matches
  `test_refs_replace_swap_does_not_fool_pristine_restore` (green).
- **Three-way algorithm identity, verified empirically this turn** (not just "by eye"):
  built the image, ran `owl_snapshot` (sourced from `owl/verifier/lib.sh`) and the
  extracted `ClaudeCodeHarness._SNAPSHOT_CMD` Python string inside the same container
  against the same `/app`, and diffed all three manifests
  (Dockerfile-baked `/var/lib/owl/baseline.manifest`, `owl_snapshot`'s output,
  `_SNAPSHOT_CMD`'s output) — byte-identical, 0 diff lines, all three.

### Issues with confidence ≥80 (block APPROVED)

1. **[score:80]** No automated test asserts the three copies of the snapshot algorithm
   (`owl/verifier/lib.sh::owl_snapshot`, `tasks/00-smoke/environment/Dockerfile`'s seal
   step, `owl/agents/claude_code_harness.py::_SNAPSHOT_CMD`) stay byte-identical. I
   verified manually this turn that they currently are (see above), but that's a
   one-off, not durable regression protection — the exact failure mode this lote's
   own CRITICAL came from (silent divergence in security-critical, duplicated logic).
   `owl_snapshot`'s own docstring (`owl/verifier/lib.sh:73-80`) acknowledges the drift
   risk and defers centralization to T4 (`patient/seal.sh`), which is reasonable — but
   nothing today would catch a future edit to one copy that forgets the other two
   before T4 lands. A cheap fix: a `-m docker` test that runs all three commands
   against the same seeded `/app` (or reuses the fixture the 12 existing tests already
   build) and diffs the three manifests — exactly the check I ran by hand above,
   turned into a regression test. Low effort, high value given what's riding on these
   three staying in sync.

### Informational observations (50-79, don't block)

1. [score:60] `owl/verifier/lib.sh:81-97` (`owl_snapshot`) — no file mode/exec bit is
   captured, only content hash. An agent flipping the executable bit on a file without
   changing its bytes is invisible to `owl_changes`/scope. No current task (00-smoke
   or the catalog) depends on mode bits for reward, so this isn't exploitable today,
   but worth a line in `design.md`'s Failure modes if a later task (e.g. a script
   permission check) needs it.
2. [score:55] `owl/verifier/lib.sh:84-95` — the `find -print0 | xargs -0 sha256sum`
   half of the pipeline is NUL-safe up to `sha256sum`, but `sha256sum`'s own output is
   newline-delimited text (no `-z`/`--zero`); a filename containing a literal newline
   (legal on Linux, only `/` and NUL are forbidden) would split across two manifest
   lines and corrupt the recorded path for that entry. Traced through the failure
   mode: it corrupts the *reported* path, it does not appear to let a real edit go
   undetected (the mismatch still registers as *some* changed entry, which still fails
   an unlisted `scope.allow` glob) — so it reads as a robustness bug, not a reward-
   hacking vector, hence informational rather than blocking. Same class as the file
   mode gap: worth a `sha256sum -z`/NUL-delimited rewrite when this file is next
   touched, not urgent enough to hold up this lote on its own.
3. [score:55] `owl/verifier/lib.sh:84,92` — `find -type f`/`-type l` don't capture
   FIFOs/sockets an unprivileged `node` can create with `mkfifo`; such a special file
   is silently absent from both manifests. Low severity: doesn't appear usable to hide
   a *file* edit (P2P/F2P only ever touch known test paths), just an unaccounted-for
   filesystem object.
4. [score:0, resolved] Cycle 1's informational finding (missing `core.fsmonitor`/hooks
   hardening) is now fully addressed by `_owl_git`'s wrapper — no longer applicable,
   dropped from this pass.

## Recommendation

Add the three-way manifest-identity regression test (finding #1 above) — everything
else in this addendum is solid: the CRITICAL is genuinely closed, verified both by the
implementer's 5 new docker tests and independently reproduced by this review, and the
design docs are updated and consistent with the code. Re-request review once that test
lands; the informational observations don't need to block it.

## Cycle 3 — re-review of Addendum 2 (parity test + manifest hardening)

Per `.claude/progress/implementer_t1t2.md`'s "Addendum 2" section: `owl_snapshot` now
records octal mode for regular files (`F\t<mode>\t<sha256>\t<path>`), typed `O` entries
for FIFOs/sockets/devices (previously invisible), and fails closed (`OWL_BASELINE_VALID=0`,
non-zero return) on a path containing a literal newline instead of silently corrupting a
manifest line. A new `tests/test_validate_docker.py::test_three_snapshot_copies_are_byte_identical`
regression-tests the three-way identity that was cycle 2's blocking finding.

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (signed this cycle, `status: ok`)

### Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK — `design.md` D6 point 3 and the `/var/lib/owl/` Contracts
entry extended to match (mode/typed entries, newline fail-closed); scope still limited to
T1/T2 files (`owl/gate.py`, `pyproject.toml`, `uv.lock`, `tests/test_gate.py`,
`navori.config.json` untouched, confirmed via `git status --porcelain`).

### Pass 2 — Code quality
**Partial verdict:** QUALITY_OK

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` |
| `uv run pytest -q -m 'not docker'` | [x] | `5 passed` |
| `uv run pytest -m docker tests/test_validate_docker.py -v` | [x] | `15 passed in 43.61s` |

### Cycle 2 blocker: verified actually closed (not just present)
Mutated `owl/agents/claude_code_harness.py::_SNAPSHOT_CMD`'s `find` clause locally
(`-newer /nonexistent`, makes it list zero files) and reran
`test_three_snapshot_copies_are_byte_identical` alone: **failed red**, exactly on the
`b == c` assertion, with a concrete diff (`_SNAPSHOT_CMD`'s manifest came back empty
vs. `owl_snapshot`'s 3 real entries) — proves the test isn't a tautology and would
actually catch a future divergence. Reverted the mutation (`cp` from a pre-mutation
backup), confirmed `ruff` clean and the parity test green again before proceeding.

### Newline fail-closed → contamination, not infra (coordinator's specific ask)
Built the current image, created a file with a literal embedded newline in its name as
`node` (`printf "SECRET_BACKDOOR" > "$(printf 'evil\nname.txt')"`), ran the unmodified
`test.sh`:
```json
{"reward": 0, "verifier_complete": 1, "baseline_valid": 0, ...}
```
`verifier_complete: 1` (the verifier ran to completion, no crash/infra failure) and
`baseline_valid: 0` — per `owl/gate.py::check_trial` (unchanged since cycle 1:
`baseline_valid == 0 → contamination`, sticky over `infra`), this trial classifies as
**contamination**, never `infra`/unscored. An agent can't use a newline-named file to
turn a real out-of-scope edit into a trial the gate discards as noise instead of
penalizing — confirmed, not just inferred from reading the code.

### Receipt-sign process note (not a code finding)
First `navori receipt sign` attempt failed: `{"status":"error","error":"diff changes
file mode only"}`. Root cause: `tasks/00-smoke/tests/f2p/test/discount.test.js` was
staged as a rename with one blob, then edited further in the working tree without
re-staging (`git status` showed `RM`) — with `--no-renames`, the tool's raw diff sees
this as a same-mode-looking add whose old/new hash both read as the "not hashed"
placeholder, a false positive in the tool's mode-only-change heuristic, unrelated to
this diff's content or the T1/T2/T3 code itself. Fixed non-destructively with
`git add tasks/00-smoke/tests/f2p/test/discount.test.js` (re-syncs the index to the
current working-tree content already reviewed above — nothing discarded, no working
tree content changed), then `navori receipt sign` returned `"status":"ok"`.

### Issues with confidence ≥80 (block APPROVED)
None.

### Informational observations (50-79, don't block)
Carried over from cycle 2, still true and still non-blocking: `owl_snapshot`'s
per-file `sha256sum`/`stat` calls (not batched) are fine performance-wise at this
scale; no other new gap found. Cycle 2's file-mode/FIFO observations are now resolved
by this addendum (mode captured, typed `O` entries added) — dropped from this pass.

## Recommendation
APPROVED. Receipt signed (`.claude/progress/receipt.txt`, feature `f2`, target `main`,
`status: ok`).
