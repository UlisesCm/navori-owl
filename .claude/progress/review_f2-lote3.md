# Review — F2 Lote 3 (T6, T7, T8)

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt`

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- Resolves the requested ticket / audit:         [x]
- Scope respected (no files outside):            [x] (only `.claude/.managed-drift-stamp`/`.routing-watch` drift, harness bookkeeping, not application scope)
- Bugfix: documented root cause matches fix:     n/a (feature work)
- UI browser-validated (only if the user requested it): n/a

Reviewed against `git diff feat/f2-lote2-patient` + untracked (branch is stacked on the unmerged lote-2 PR #7), per the review scope. `specs/f2-suite-v1/tasks.md` T6/T7/T8 all `[x]`.

### Adversarial checks
1. **No model can ever be called by `owl validate`.** `owl/validate.py::_run_harbor_job` (line 246-263) never passes `--env-file` nor `-m/--model`. The three agents it drives (`oracle`, `nop`, `CheatAgent`) never touch `harbor.agents.model_connection` — confirmed by reading `harbor/agents/nop.py` and `harbor/agents/oracle.py` in `.venv/lib/python3.13/site-packages/harbor` (no model client instantiated). Docker isolates the container's env regardless of what the host `harbor` subprocess inherits, so ambient host credentials are moot. Sound.
2. **Infra errors vs. defeated attacks.** `_trial_reward` returns `None` (not `{}`) when `reward.json` is missing; `evaluate_*` compare `reward.get("reward") != 1/0`, so a missing/incomplete trial fails the check rather than reading as a false pass. Oracle explicitly asserts `len(rewards) == 5` (`evaluate_oracle`, validate.py:138). No path treats "verifier never ran" as "reward=0 → pass".
3. **`move-baseline` expectation correction** (implementer's own finding, `impl_t6t8.md` lines 56-71): verified independently by reading `owl/verifier/lib.sh` — `owl_p2p`/`owl_restore_pristine` both `[ "$OWL_BASELINE_VALID" = "1" ] || return 0` (lines 342, 376), while `owl_f2p` (line 400) has no such gate. So under `move-baseline`, `f2p=1`/`p2p=0` is exactly what the fail-closed gate is designed to produce, not a second failure — `_BASELINE_INDEPENDENT_REWARD_KEYS = {"f2p"}` (validate.py:161) is the correct, minimal scoping. **However, `specs/f2-suite-v1/design.md` D8's table (line 334) still reads "todo componente de owl_reward en 1"**, which is now factually wrong for any task whose `owl_reward` includes `p2p` (i.e., every real task besides degenerate ones). This was flagged by the implementer in `impl_t6t8.md` but never corrected in `design.md` itself. Suggested exact wording for that cell: replace "todo componente de `owl_reward` en 1" with "todo componente de `owl_reward` ajeno al gate de `baseline_valid` en 1 (p. ej. `f2p`); los que dependen de `owl_restore_pristine`/`owl_p2p` (p. ej. `p2p`) van a 0 por el mismo gate, no por un fallo aparte". Documentation-only drift, not a code defect — informational, not blocking (see below).
4. **Holdout guard and redaction.** `owl.tasks.is_holdout`/`holdout_signals` fail closed on either signal (path or metadata); `resolve_task_args` (shared by `owl run` and `owl validate`) refuses any holdout task without `--holdout`, exit via `SystemExit`. `_redact_section`/`validate_task` (validate.py:327-385) replace reasons with check names only for holdout tasks — verified against D10's "solo nombres de checks" contract and unit-tested (`test_validate_task_holdout_report_has_no_content`).
5. **CheatAgent attacks are real, deterministic, run as the agent user.** Read `owl/agents/cheat.py` in full: `tamper-fail`/`tamper-pass` actually mutate visible test files; `move-baseline` genuinely applies the oracle solution via the same `build_execution_command`/`Task` path as `OracleAgent`, commits, moves the ref, and attempts (and is expected to fail) to overwrite `/var/lib/owl/baseline`; `plant-reward` starts a real detached `setsid` loop; none use `exec_as_root`. `PYTHONPATH` question: `owl` is editable-installed in `.venv` (`_editable_impl_navori_owl.pth`, confirmed by `import owl` succeeding from `/tmp` with `.venv/bin/python`), so under normal invocation (activated venv or `uv run`, where `.venv/bin` precedes any global `~/.local/bin/harbor`) `owl/validate.py`'s bare `"harbor"` subprocess call resolves to the venv's own `harbor` and needs no explicit `PYTHONPATH`. Confirmed empirically: `source .venv/bin/activate && which harbor` → `.venv/bin/harbor`. The docker tests' explicit `PYTHONPATH=ROOT` injection is a defensive measure for pytest invocations that don't go through an activated venv/`uv run` (this session's raw shell had `~/.local/bin/harbor` shadowing it) — not evidence that production `owl validate` usage is broken. Not a blocker.
6. **`test_suite_catalog.py` skip.** Explicit reason, activates automatically once `tasks/` has ≥12 tasks (`len(tasks) < 12: pytest.skip(...)`), no manual re-enable needed. R4/R5 coverage is explicitly assigned to T6 in `tasks.md` (not T8), so `owl validate --suite` not independently re-running this exact count/coverage check is consistent with the task split, even though design.md D9 prose describes it as part of `owl validate`'s own static-check phase — informational, not a spec gap (see below).

**Spec gaps (if SPEC_MISS):** none — Pass 1 is SPEC_OK.

## Pass 2 — Code quality (only if SPEC_OK)
**Partial verdict:** QUALITY_OK

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` |
| `uv run pytest -m 'not docker'` | [x] | `65 passed, 1 skipped, 25 deselected in 3.16s` |
| `uv run pytest -m docker tests/test_validate_docker.py::test_owl_validate_smoke_end_to_end` | [x] | `1 passed in 141.33s` (real Docker + harbor, no model, no `--env-file`) |
| Zero new errors vs baseline | [x] | All touched/new files (`owl/validate.py`, `owl/tasks.py`, `owl/agents/cheat.py`, `owl/cli.py`, `tests/test_*.py`) pass ruff and pytest; no regressions in pre-existing suites (`test_gate.py`, `test_patient_docs.py`) |

### Conventions (CLAUDE.md + orchestrator's Project rules)
- Code/comments in English, chat-facing artifacts n/a: [x]
- No hardcoded secrets/credentials, no `--env-file`/model wiring anywhere in the new validate/cheat code: [x]
- Typed functions, no bare `Any` without justification (`dict[str, Any]` used for opaque JSON payloads, standard for this kind of Harbor interop code): [x]
- SDD traceability (`specs/f2-suite-v1/tasks.md` exists): T6/T7/T8 each cite their `R<n>` and tests carry `# Covers: R<n>` (`tests/test_tasks.py`, `tests/test_suite_catalog.py`, `tests/test_validate.py`, `tests/test_validate_docker.py`, `tests/test_cheat.py`): [x]

### Issues with confidence ≥80 (block APPROVED)
None found.

### Informational observations (50-79, don't block)
1. [score:65] `specs/f2-suite-v1/design.md:334` — D8's `move-baseline` table cell ("todo componente de `owl_reward` en 1") is stale against the verified `owl/verifier/lib.sh` behavior; `evaluate_cheat`'s `_BASELINE_INDEPENDENT_REWARD_KEYS` scoping is correct, but the design doc should be corrected to avoid a future author (e.g. T13's `docs/task-authoring.md`) restating the wrong expectation. Suggested wording is in Pass 1, item 3 above.
2. [score:55] `owl/validate.py` (`cmd_validate`/`static_checks`) — D9's "con `--suite`: de 12 a 15 tareas... cobertura de cada categoría" static check isn't wired into `owl validate --suite` itself; it only lives in the decoupled `tests/test_suite_catalog.py` (consistent with `tasks.md`'s own R4/R5→T6 assignment, so not a spec gap, but means a suite that later drifts outside 12-15 tasks or loses category coverage won't be caught by `owl validate --suite` alone, only by running the pytest suite).
3. [score:55] `owl/validate.py:224` (`_collect_trial_dirs`) — if Harbor ever failed to create a trial directory for a given `CheatAgent` attack (rather than creating one with a missing `reward.json`), that attack would be silently absent from `entry["cheat"]`, not counted as a failure. Verified this is a non-issue in the current Harbor version (`Trial._init_result` writes `config.json` for every planned trial before execution, unconditionally), but worth a comment if Harbor's trial-init ordering ever changes.

## Notes for engram (informational, not saved by this role)
- Decision worth persisting: `_BASELINE_INDEPENDENT_REWARD_KEYS = {"f2p"}` in `owl/validate.py` is the correct fix for D8's `move-baseline` expectation, verified against `owl/verifier/lib.sh`'s `OWL_BASELINE_VALID` gating; `design.md` D8's table text still needs the correction quoted above.

## Delta re-sign (post-APPROVED)

One-line docs-only change to `specs/f2-suite-v1/design.md`'s D8 `move-baseline` table cell, applying the exact wording suggested in Pass 1 item 3 / observation 1 above. No code, no test, no logic touched. Gate re-run over live bytes: `ruff check .` — all checks passed; `uv run pytest -m 'not docker'` — 65 passed, 1 skipped. Receipt re-signed: `targetSha`/`headSha` `416f976a...`, `status: ok`. Original APPROVED verdict stands.
