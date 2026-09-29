# Review — F2 lote 8, parte pre-holdout (T13 doc + validate hardening + task fixes)

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (written on APPROVED)

Note: branch not behind origin/main (0). Holdout/ and work-* dirs not opened (D10).

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- T13 doc + VISION §7.1 + tests: [x]
- Validate hardening (required_files, metadata, dimensions, loud hardcode): [x]
- Task fixes (exec bit 15/17, f2p in 20): [x]
- Scope respected (only the listed files): [x]
- Accepted deviation (owl_target_dimension required, not required in owl_dimensions): consistent code/test/doc: [x]

## Pass 2 — Code quality
**Partial verdict:** QUALITY_OK

### Quality gate (this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check . && uv run pytest -m 'not docker'` | [x] | All checks passed; 101 passed, 55 deselected |
| `owl validate --suite --checks static,oracle -n 4` | [x] | 12/12 PASS (10-21), incl. new required_files/metadata/dimensions; 15/17/20 also re-run alone: PASS |

### Verified
- Holdout redaction: `dimensions` goes through `_redact_section`; holdout static reports check names only (new `required_files`/`metadata` reasons never printed); the loud hardcode reason goes through the cheat redaction. Test asserts the `dimensions` section keys.
- `evaluate_dimensions`: strict set equality per oracle trial, both directions reported, empty rewards fail; a missing reward.json becomes `{}` and fails.
- `required_files` suite vs non-suite split is justified (smoke/probe have no hardcode/scope) and tested.
- Doc vs lib.sh/validate.py: function order, owl_dim rules (regex, value, built-ins, returns 1), polarity (`= 1`), fail-closed unregistered dim, attack table (refs, commits, record_writable, f2p=1 on move-baseline, tamper p2p vs nop), static check names, `-t holdout/<id> --holdout` refusal: all match the code. Marker blocks are machine-checked by tests.
- VISION §7.1 wording consistent with doc §11. The `IS_SANDBOX=1` claim about Claude Code is external and not backed in-repo (not verified by me); it is worded as a side note.

### Issues with confidence >=80 (block APPROVED)
None.

### Informational observations (50-79, don't block)
1. [MEDIO][score:70] `docs/task-authoring.md:357-361` (integrity rule 3) prescribes `chmod -R go-rwx /tests /logs/verifier` "falla cerrado". No dev task does this: the only tested pattern is task 18 (`tasks/18-repro-duplicate-create/tests/test.sh:66-67`): non-recursive `chmod 700 /tests /logs/verifier ... || true` plus restoring the original modes afterwards. The doc is the sole contract, so it should describe what was validated under Harbor mounts. Fix: rewrite rule 3 to the task-18 pattern (non-recursive chmod 700, restore modes before `owl_finish`), or state the goal (node must not read /tests or /logs/verifier while agent code runs) without a literal command and drop "falla cerrado si no se pudo".
2. [MEDIO][score:65] `docs/task-authoring.md:424-430`: the holdout-report vocabulary list omits `dimensions`, and the "casi siempre es alguna de estas" list omits the most likely blind failure for a new author: `owl_dimensions` != real reward.json keys (forgetting `typecheck`/`conventions` or an `owl_dim`). Add both. Item "4. dimensions" (l.421) is numbered as if part of the oracle/nop/attacks sequence; fold it into the list properly.
3. [MEDIO][score:60] `docs/task-authoring.md:60-61` says `tests/owl-lib.sh` must be executable; `required_files` does not require it (harmless, it is sourced). Align doc or check.
4. [score:55] Doc rules 4/5 ("nombres, mtimes o rutas", "ciclo de vida de npm", "solo comprueba que el proceso salio con error") are generalized lessons from dev tasks 18/19. Generic enough, not identifiable, but borderline and not caught by the keyword guard.
5. [score:55] `tests/test_validate.py`: no test that a failing `dimensions` section on a holdout task is redacted to `["dimensions"]` (only the passing path is asserted). Correct by code reading.
6. [score:50] Doc says `OWL_REWARD` must equal `owl_reward`; no static check enforces it (cheap future check).

## Final review (holdout + docs) — APPROVED

Pass 1 SPEC_OK / Pass 2 QUALITY_OK.

- Gate this turn: `ruff check .` all checks passed; `uv run pytest -m 'not docker'` 102 passed, 55 deselected.
- `cmp owl/verifier/lib.sh tasks/*/tests/owl-lib.sh`: no diffs.
- Holdout mechanical (holdout/ contents never opened): 30-tenant-filter-leak, 31-comment-pin, 32-stats-to-db each refused without `--holdout` ("Refusing to run holdout task(s) without --holdout"). The exit code is 1, not 2, because `owl/tasks.py:135` raises `SystemExit(str)`. The refusal works and this is not blocking. Redacted reports jobs/validate-20260929-182459 and -182930 hold only check names plus ok/reasons, and 32 has its own dirs. Suite+holdout run (T15) is pending from the orchestrator.
- docs/task-authoring.md: the built-in key list (doc lines 196-199) matches `_OWL_DIM_BUILTIN_KEYS` in lib.sh:688. The chmod rule 3 (`chmod 700 /tests /logs/verifier`, non-recursive, restored before owl_finish) matches tasks/18 test.sh `_lock`/`_unlock` (lines 66-67). `dimensions` is documented as its own check.
- VISION.md: the §10 "Suites por perfil" paragraph and the F6 row are consistent with the suite/holdout split and `owl_type`. The §7 no-root rewording (IS_SANDBOX) is also in the diff. It reads consistently and was not in the brief.
- test_validate_task_holdout_redacts_failing_dimensions has `# Covers: R14` and passes.

Informational [55]: the brief expected exit 2 on refusal, and the code returns 1. Change the code only if a spec requires 2.

## Receipt refresh (delta re-sign) — APPROVED stands

After the final APPROVED the orchestrator edited only session-state files. Verified by diff: `specs/f2-suite-v1/tasks.md` changes only T13, T14, T15 from `[ ]` to `[x]`; `progress/current.md` changes only the Estado line; `progress/history.md` adds only one new top entry for lote 8, factual against this review (102 passed, APPROVED) and the T15 result. `jobs/validate-20260929-183418/owl-validate.json` has 15 entries (12 dev, 3 holdout) with `ok: true` on all. `navori receipt check` before signing reported drift `[]` and `uncovered: [specs/f2-suite-v1/tasks.md]`, so nothing else moved since the last receipt. No code changed, so the previous gate (ruff clean, 102 passed) still applies; I did not re-run it. Receipt re-signed over the full current diff (status ok, uncovered `[]`, drift `[]`). The holdout/ contents were not opened.
