# Review — F2 lote 9 (T16: owl summary, R16/R17)

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` in the worktree (signed, status ok)

Branch not behind origin/main (0). holdout/ not opened.

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- R16 per-task success over gate-ok trials, mean cost/turns, secondary dims: [x]
- R17 flag 0/k and k/k (D12 "0 o n"): [x] `summary.py` flag only when n_valid>0
- Excluded trials counted per category, not defeats: [x] in table (`excluded` column) and JSON (`excluded` dict per cell)
- Fail-closed: gate-ok trial with missing/non-numeric reward, non-dict JSON, invalid JSON -> `infra` excluded; parametrized test covers 7 shapes. A crashing verifier is visible as `infra:N` in table and JSON, never a silent drop or a defeat: [x]
- gate.py: non-dict reward.json -> `_fail(..., "infra")` (previously could crash on later `.get`); `task_path` is additive. Existing gate behavior unchanged, existing tests green: [x]
- exit_refused exit 2 consistent: run (`resolve_task_args`), validate (existing tests pass), summary; tested in test_tasks and test_summary: [x]
- Scope respected: [x]
- Accepted deviation: `--json PATH` explicit, design.md:709 says it writes `owl-summary.json`. Schema is a superset of D12 (adds `excluded`, `n_valid`, `flag` as `"0/k"|"k/k"|null`). Judged acceptable; update design.md:709 to `--json PATH`.

## Pass 2 — Code quality
**Partial verdict:** QUALITY_OK

| Check | Status | Evidence |
|---|---|---|
| `ruff check . && uv run pytest -m 'not docker'` | [x] | All checks passed; 91 passed, 55 deselected |
| Smoke `uv run owl summary <main>/jobs` | [x] | table renders; excluded shown (infra/contamination); exit 0 |

### Issues >=80 (block)
None.

### Informational (50-79)
1. [score:65] `owl/summary.py:cmd_summary` — holdout detection relies on `task_path` from the trial `config.json`; a trial with no/malformed config falls back to the job-name task and is never refused. Fail-open on R15 for corrupted trials only; a holdout trial would have been produced by `owl run`, which records config. Consider treating unreadable task_path as unknown and noting it.
2. [score:60] Holdout results are read (`check_jobs`) before refusal; nothing is printed, so no leak. Fine, noted.
3. [score:55] A cell with n_valid=0 (all excluded) shows `0/0` and no flag; correct for the T17 rule (needs re-run, not a defeat) but the pilot reader should watch the `excluded` column.
4. [score:50] design.md:709 should be updated to `--json PATH` and `excluded` in the schema.

## Cycle 2 — fail-closed holdout refusal

**Final verdict:** APPROVED

- `_holdout_ref` (owl/summary.py:113): unreadable task_path is refused as `unresolved: <trial>` unless `--holdout`; consistent with R15 (refuse without explicit flag) and D10 (holdout results unread).
- No-trial exception verified: `check_jobs` (owl/gate.py:217-228) emits the `no trial:` gate only when no subdir has `config.json`; it carries no result data, and it is the sole producer of that reason prefix. Exception refuses if `holdout/<task>` exists, so it cannot leak holdout results.
- Gate this turn: `ruff check .` clean; `pytest -m 'not docker'` 92 passed, 55 deselected (exit 0). Branch not behind origin/main.
- Informational [score:55]: a no-trial job whose name doesn't parse to `stamp__task__variant__rN` falls back to the whole job name as task, so a holdout task could slip only in a result-less job (no data exposed). Not blocking.

## Rebase + receipt refresh

**Final verdict:** APPROVED (unchanged)

- Branch rebased onto origin/main a807abf (0 behind). Code diff vs origin/main is the approved T16 set: README, owl/{cli,gate,tasks,summary}.py, design.md, tests/{test_summary,test_tasks}.py; no surprises.
- Session-state diffs checked: tasks.md T16 `[ ]`->`[x]`; current.md Estado line; history.md new T16 entry (116 passed matches this turn's gate). Factual. Observation: current.md says T17 is "corriendo en jobs/pilot-f2"; the directory exists in the main checkout, but a live run is not verifiable from here.
- Gate this turn: `ruff check .` clean; `pytest -m 'not docker'` 116 passed, 55 deselected.
- Receipt re-signed over the full diff (includes session-state files).
