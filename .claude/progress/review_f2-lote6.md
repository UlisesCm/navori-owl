# Review — F2 lote 6 (T11: tasks 16, 17, 18)

**Final verdict:** CHANGES_REQUESTED
**Content receipt:** not written (CHANGES_REQUESTED never signs)

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK (catalog fidelity, canary, exec bits, byte-identical lib all pass); the blocking items below are verifier-integrity defects found in Pass 2 focus items.

- Catalog rows 16-18 (design.md) covered: [x]. Row 18 promises "test nuevo falla con src baseline AND pasa con fix oculto AND src sin cambios"; that guarantee is breakable (finding 1).
- Canary in every file except `instruction.md` (grep loop, no MISSING; `instruction.md` has 0): [x]
- `solve.sh`/`hardcode.sh` executable (755 x6): [x]
- `cmp owl/verifier/lib.sh tasks/{16,17,18}-*/tests/owl-lib.sh`: identical [x]
- Scope: only the three new task dirs are added: [x]

## Pass 2 — Code quality
**Partial verdict:** QUALITY_MISS

### Quality gate (this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` |
| `uv run pytest -m 'not docker'` | [x] | `77 passed, 1 skipped, 44 deselected` |
| `uv run owl validate -t tasks/16.. -t tasks/17.. -t tasks/18.. -n 4` | [x] | PASS x3 (jobs/validate-20260929-145142) |

### Issues with confidence >=80 (block APPROVED)

1. **[CRÍTICO][score:97] `tasks/18-repro-duplicate-create/tests/test.sh:67-83` — stateful test cheat reproduced: reward=1 with zero real repro.**
   I copied the task and replaced `cheat/hardcode.sh` with a test that fails if `/tmp/.owl-flag2` does not exist (creating it) and passes otherwise. `owl validate` reported `hardcode: reward=1, expected 0` (jobs/validate-20260929-150117). The `/app` before/after diff cannot see it. Two further leaks make it even cheaper, with no state planted by the test:
   - `/logs/verifier/repro-fixed.log` is created by root's redirect before run 2 only, so `existsSync("/logs/verifier/repro-fixed.log")` distinguishes the runs (and `repro-baseline.log` likewise), if `/logs/verifier` is node-traversable.
   - `/tests` (containing `fix.patch`) is readable by `node`, so a test can read the patch and fail exactly when `/app` src lacks its markers. That is oracle-aware, not a repro.
   Fix (task-local, small; all in `test.sh`, nothing in lib.sh):
   - Before each `_run_tests`, `chmod 700 /tests /logs/verifier` (root-only) and write the run logs to a root-only dir (e.g. `mktemp -d` 0700) and copy them into `/logs/verifier` afterwards. Restore modes before `owl_finish` if lib.sh needs to write there as root (root is unaffected).
   - Run node with `env -i HOME=<fresh 0700 node-owned dir> TMPDIR=<same> PATH=...` and, between run 1 and run 2, `pkill -9 -u node` plus `find / -xdev -user node -not -path '/app/*' -not -path '/proc/*' \( -type f -o -type l \) -delete` (and empty the fresh HOME). Adding `/dev/shm` and `/var/tmp` to the wipe list is cheap.
   - Add a docker test in `tests/test_validate_docker.py` (`# Covers: R6`) with the stateful attack above (plus one reading `/tests/fix.patch`) asserting `reward=0`.
   - Note that a stray node-owned file in /app itself is already covered by the snapshot diff; keep it.

2. **[ALTO][score:85] `tasks/17-tooling-typecheck-project/instruction.md:1-8` — language inconsistent with the suite.** Tasks 10, 13, 15 (and 11/12/14 by the same pattern) have English `instruction.md`; 17 is Spanish. Suite consistency is a stated requirement and the language is a confound for cross-task comparison. Translate to English, keeping the constraints (no `@ts-ignore`, `as any`, lowering tsconfig options, or dropping files from compilation). Also confirm `task.toml` metadata/comments remain English (they are). The `instruction.md` must still carry no canary.

### Informational observations (50-79, don't block)

3. **[MEDIO][score:70] `tasks/17-tooling-typecheck-project/tests/test.sh` suppression regex (check 3).** It catches `@ts-*` and `as any` / `<any>` but not a plain `: any` annotation (e.g. `const inc: any = incidents`) or `as unknown as`. `: any` is the most common LLM way to silence tsc. Add `:[[:space:]]*any([^A-Za-z_]|$)` to the regex; a legit fix never needs it. The `weak` message already reports which file fired, so no other change is needed. (I could not confirm reward=1 for this variant with my probe because a `.map` callback parameter also turned implicit-any, but the regex gap is by code reading.)

4. **[MEDIO][score:65] Task 18 documents the source-grepping limitation nowhere durable.** `tests/test.sh` header mentions only the /tmp limit (which finding 1 removes). Add to the header comment of `tests/test.sh` and to design.md (row 18 or D8): "a repro that greps `src` for `Idempotency-Key` (or otherwise reads the app source) is not detected; needs LLM judge D9". Spanish or English following the file's language.

5. **[MEDIO][score:60] Task 18 static `tests/visible-tests.txt`.** Acceptable as a tripwire: if the patient gains a test, oracle validate fails loudly (comment says so), and it is what keeps f2p computable under `move-baseline`. Keep it. Cheap hardening: in `tests/test.sh`, if baseline is valid, `comm` the static list against `git ls-tree` of the baseline `packages/*/test/*.test.*` and force `f2p=0` + a log line on a mismatch, so a stale list can't silently count a new visible test as agent-authored; it is not required now.

### Focus items answered

- **Item 3 (task 16 fairness): OK.** `docs/permissions.md` lists viewer with no "Edit own comment" (403 even on own), responder own, admin any ("Edit / delete another user's comment": admin), cross-tenant is 404 never 403, and the mass-assignment paragraph. 401 comes from `auth.ts`. Comment under another incident is not spelled out in docs but follows from the path and from `CommentsRepo.get` tenant scoping; it is 404 by REST semantics (acceptable). Check order is NOT an undocumented dependency: every 403 probe sends a valid body and every 400 probe uses an authorized author with an existing comment, so any order of 404/403/400 that gives the right status per case passes. Oracle and hardcode behave as designed (PASS).
- **Item 4 (task 17 detection): OK apart from finding 3.** Isolated probes via `owl validate` on copies of the task: excluding `packages/cli` from `include` -> hardcode reward=0 (v17a PASS); lone `as any` at the failing call -> reward=0 (v17b PASS); rewriting to `.sort()` with no config change -> reward=1 (legit accepted); `lib: ["esnext"]` -> reward=1 (legit accepted). The forbidden-option list does not false-positive on these. Baseline tsconfig has `strict`, `noUncheckedIndexedAccess` and `skipLibCheck` all `true`, matching the test.sh expectations; `paths` is compared to the baseline value.
- **Item 5:** see finding 2.

## Chat reply
CHANGES_REQUESTED -> .claude/progress/review_f2-lote6.md

---

# Cycle 2

**Final verdict (cycle 2):** CHANGES_REQUESTED
**Content receipt:** not written.

## Pass 1
SPEC_OK unchanged. Task 18's catalog promise is still breakable (finding 6).

## Pass 2 - gate (this turn, final tree)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | All checks passed |
| `uv run pytest -m 'not docker'` | [x] | 77 passed, 1 skipped, 53 deselected |
| `pytest tests/test_validate_docker.py -m docker -k repro` | [x] | 9 passed (53s) |
| `owl validate -t 17 -t 18` | [x] | PASS x2 (jobs/validate-20260929-153000; whole run 4m39 wall with -n 2, 18 alone ~1m13 job time) |
| owl-lib.sh identical (16/17/18), canary, exec bits | [x] | cmp identical, 755 x6, canary missing only in instruction.md (expected) |
| repo hygiene | [x] | no probe files or jobs tracked (jobs/ ignored); my scratch probe test removed |

## Cycle-1 findings status
- 2 (task 17 instruction in English): fixed. 3 (regex): fixed and PROVEN, see below. 4 (documented limit): fixed (test.sh header + design.md). 5 (visible-tests vs baseline ls-tree): fixed.
- 1 (stateful test cheat): the channels named in cycle 1 are closed (flags in /tmp, /var/tmp, /dev/shm, HOME, .git, node_modules; /tests and /logs reads; docker tests pass). BUT a new, equivalent channel remains open (finding 6).

## Task 17 probe (item 2), scratch copy outside the repo, one `owl validate`
- Lone `const list: any = incidents.map(...); list.toSorted()` with tsconfig untouched: typecheck=1, checks_weakened=0, reward=0. Blocked as intended.
- Legit `.toSorted()` -> `.sort()` rewrite: reward=1 in the 5 oracle runs. Real oracle (lib es2023) passes validate: regex does not flag it.
- No task 17 findings remain.

## Issues >=80

6. **[CRÍTICO][score:97] `tasks/18-repro-duplicate-create/tests/test.sh:_reset_node` (`find /app -mindepth 1 -delete; cp -a "$rdir/app/." /app/`) leaks run identity through /app filesystem metadata.**
   The restore re-creates every entry in /app, so in run 2 the inodes, ctime and birthtime are new and `/app`'s directory mtime is ~60 ms old, whereas in run 1 it is the age of the agent's last write. Measured with a probe test in the real sealed container: run 1 `now - mtime(/app)` = 1,364,879 ms; run 2 = 59.6 ms (inode 19215713 vs 19216733, `now - ctime(/app/package.json)` 1752 ms vs 63 ms).
   Reproduced end to end: a "repro" whose only body is `assert.ok(Date.now() - statSync("/app").mtimeMs < 1500)` gets `f2p=1, repro_fails_baseline=1, repro_passes_fix=1, reward=1` from the real `tests/test.sh` (sealed_container, run this turn). It tests nothing about duplicate creation. This is exactly the cycle-1 class (a test that fails run 1 and passes run 2 with no real repro), and the new docker tests do not cover it.
   Fix, in `test.sh` only:
   - Do a differential restore instead of wipe and copy: compare `owl_snapshot` before/after (already taken), delete only entries that are new, `cp -a` back only entries whose content/mode/owner changed, and never touch untouched files (their inode and ctime stay). `.git`, `node_modules` and `data/` are excluded from the snapshot diff, so for them use `find -newer <marker>` (marker created just before run 1) to find what run 1 touched.
   - After the restore, `touch -r "$rdir/app/<dir>" <dir>` for every directory whose entries changed, including `/app` itself, to put dir mtimes back. Do this deepest first.
   - Residual channel (ctime/birthtime of entries that run 1 itself modified) cannot be reset; state it in the header as accepted, since a test must have touched the file in run 1 to see it, and then the signal carries no information the test could not already produce itself.
   - Add a docker test `# Covers: R6` with the mtime-age attack above (threshold 1500 ms) asserting `f2p == 0`, and one with `birthtimeMs`/`ino` recorded... birthtime cannot be persisted across runs, so the age-of-`/app` check plus an age-of-untouched-file check (`/app/package.json` ctime vs `/usr/local/bin/node` ctime, run 1 vs run 2 differ by minutes) is enough.
   Alternative if the differential restore is judged too costly: run 2 must at least follow a `sleep`-free path that keeps `/app` untouched: apply fix.patch straight on the pristine /app after killing node and deleting only the new entries; the same "do not recreate untouched files" rule applies.

## Informational (50-79)
7. [score:60] `tasks/18-repro-duplicate-create/tests/test.sh:_reset_node`: System V IPC (shm/msg/sem created by node) and abstract-namespace state survive process death only for SysV IPC; run 1 can `shmget` a key and run 2 reads it. Container IPC namespace is shared. Cheap fix: `ipcs -m -q -s` (or `ipcrm -a` when present) filtered to owner node, in `_reset_node`. Not verified in the container (util-linux `ipcrm` availability unchecked), reported from code reading.
8. [score:55] Task 17 regex `:[[:space:]]*any([^A-Za-z_]|$)` also fires on a comment such as `// note: any value`, since added lines include comments. A legit fix rarely adds that; accept or strip `//` comments before grep.
9. Answered focus 1 (safety of `find / -xdev -user node -delete`): it excludes /app, /root, /home/node, /proc; the verifier's inputs (`/opt/owl/toolchain`, `/var/lib/owl/*`, /tests) are root-owned, and fix.patch is fed via stdin from /tests, so nothing needed is deleted. /app restore does return to the pre-run-1 state (backup taken after `owl_restore_pristine`, agent's test present) in content and mode; only metadata differs (finding 6). Runtime: 9 repro docker tests 53 s total, task 18 validate about 1 min 13 s job time: no explosion.

## Chat reply
CHANGES_REQUESTED -> .claude/progress/review_f2-lote6.md

---

# Cycle 3

**Final verdict (cycle 3):** APPROVED
**Content receipt:** `.claude/progress/receipt.txt`

## Pass 1
SPEC_OK. Finding 6 is resolved under the orchestrator's decision (symmetric restore before run 1 and run 2, residual no-state channels accepted in the D9-judge class).

## Pass 2 - gate (this turn, final tree)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | All checks passed |
| `uv run pytest -m 'not docker'` | [x] | 77 passed, 1 skipped, 55 deselected |
| `pytest tests/test_validate_docker.py -m docker -k repro` | [x] | 11 passed (60s) |
| `owl validate -t 16 -t 17 -t 18` | [x] | PASS x3 (jobs/validate-20260929-160655) |
| owl-lib.sh identical in tasks/*/tests | [x] | cmp silent for all |
| scratch probe file | [x] | removed, not in git status |

## Verification of the focus items
1. mtime/ctime-age attack on /app: covered by the new docker tests (`app-mtime-age`, `app-ctime-age`), both f2p=0. Extra probes in the sealed container (age check via ctime `> N ms` on /app/package.json at 20 and 60 ms, /app/packages at 40 ms, /home/node at 40 ms, none touched by fix.patch): all f2p=0 (repro_fails_baseline=0, meaning the age is already above the threshold in run 1). Node start-up latency dominates the restore-to-test gap, so the residual difference (git apply, tens of ms) is a pure relative-timing channel needing threshold tuning; same accepted class. The whole docker suite (59 tests) also passed once with the probes.
2. Tamper snapshot: `before` is taken of the /app the backup was copied from, just before the first reset, and `after` right after run 1 before the second reset; the restore recreates identical content/mode, so the diff still flags anything run 1 leaves in /app (covered by the existing flag tests in /app/.git and node_modules paths and by the docker suite). Still meaningful.
3. Gate: see table.

## Issues >=80
None.

## Informational
10. [score:55] `tasks/18-repro-duplicate-create/tests/test.sh:_run_tests`: `touch /app` equalizes only /app's mtime; run 2 has extra latency from `git apply` before the test starts (tens of ms). Accepted (relative timing, needs finely tuned thresholds, D9 judge).
11. [score:50] `_reset_node` declares `local i d` and later `local kind id` (id shadow, harmless).

## Chat reply
APPROVED -> .claude/progress/review_f2-lote6.md
