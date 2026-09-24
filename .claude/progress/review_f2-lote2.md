# Review — T4: patient/ (opsdesk) + owl-patient:local + seal.sh

**Final verdict:** CHANGES_REQUESTED
**Content receipt:** not written (SPEC_MISS; also T5 pending per orchestrator instruction to sign combined)

## Pass 1 — Spec compliance
**Partial verdict:** SPEC_MISS

- Resolves the requested ticket (T4, R1-R3):             [x]
- Scope respected (no files outside patient/, tests, specs): [x]
- D1/D2 content (workspaces, conventions M1-M6, docs, sizing): [x]
- Correct/bug-free baseline surfaces for tasks 10-21, only documented exception (task 18 idempotency): [ ]
- No navori/harness references in patient/ (neutrality):  [x] (`navori` string absent; `owl` only appears in `patient/Dockerfile`/`patient/seal.sh`, neither of which is `COPY`'d into `/app` — the agent's cwd never sees it; consistent with existing D5 threat model where `/var/lib/owl/*` is also world-readable, tamper-resistance not secrecy)
- Canary per D4 (bare GUID, `.editorconfig` only, not `instruction.md`/CLAUDE.md/AGENTS.md): [x]
- AGENTS.md byte-identical to CLAUDE.md + parity test:    [x] (`diff` clean, `test_agents_md_matches_claude_md` green)
- Sentinel line survives (`opsdesk-conventions-sentinel-f96c2e`), used by T5's own test: [x]

**Spec gaps (SPEC_MISS):**

1. `patient/packages/core/src/tenant.ts:18` (`canManageComments`) + `patient/packages/core/test/core.test.ts:41-43` — leakage of task 16's future solution. Task 16 ("agregar `PATCH /incidents/:id/comments/:commentId`… la instrucción no menciona seguridad", catalog row 16) is designed to discriminate whether the agent *proactively* derives the security rule (author-only edit, admin override, 404 cross-tenant, no mass assignment) when nothing in the prompt asks for it. `canManageComments(role, actorIsAuthor)` already implements and unit-tests exactly that decision — it is dead code today (`grep -rn canManageComments patient/` shows only the definition and its test, no caller in `app.ts`, no `PATCH` route exists yet) — but it hands the crux of the security logic to any agent that greps `packages/core/src` for "comment" before writing the route. This is the same category of problem the implementer's own report flags for task 13's `docs/runbooks/stats.md` injection line (self-documented, informational) — but that one was disclosed as a known, accepted weakening; this one wasn't caught or documented. Either remove `canManageComments`/its test from the T4 baseline (defer the permission function to task 16's own seed/hidden fixture, matching how task 18's idempotency gap and task 13's injection softening are handled — explicit, scoped exceptions) or explicitly document it as an accepted exception in design.md D2/D14 the way task 18 and 13 are documented. As it stands it's an undocumented gap against the "no leakage of future task solutions" requirement.

## Pass 2 — Code quality
Not entered per protocol (SPEC_MISS stops at Pass 1). Evidence gathered anyway since it was cheap and is still valid for the next cycle:

### Quality gate (run this turn)
| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` |
| `uv run pytest -m 'not docker'` | [x] | `7 passed, 17 deselected` |
| `uv run pytest -m docker tests/test_validate_docker.py -k "patient or snapshot"` | [x] | `3 passed` (`test_three_snapshot_copies_are_byte_identical`, `test_patient_sealed`, `test_navori_install_on_patient` — the last is T5's, out of scope here, included only because `-k` matched it; not reviewed) |

### Other observations (informational, don't block)
1. [score:55] `patient/packages/core/src/log.ts:7` — `new Date()` inside `log.event`/`log.error`, not routed through the injected `Clock`. Technically new `src/` code per M5 ("nuevo código lee la hora solo por `Clock`"), though log timestamps are infra, not business logic the dev tasks touch/assert on — low risk of contaminating any of tasks 10-21's oracle, but worth a design.md footnote if intentional.
2. [score:60] `patient/docs/sla.md` — "CI debe estar verde…una prueba que codifica una regla de este documento afirma la política, nunca se edita ni se salta" reads close to task 19's own reward rule (`tests_modified`/`skips_added`, contradictory test intact). It's phrased as domain policy (legitimate, matches D1's "se prestan las invariantes, no el código" precedent) rather than a literal giveaway of the CI mechanics, so lower confidence than the `canManageComments` finding — flagging for awareness, not blocking.

Everything else checked cleanly: pagination/filters (`db/src/pagination.ts`, `incidents-repo.ts`) have no off-by-one or AND/OR bug (tasks 11/12's future bugs are seed-time only, as designed); `stats.ts` UTC boundary is correct and consistent between API and CLI (task 13's real bug is seed-time only, per D3); `csv.ts` RFC4180 quoting is correct (task 21 reuse target); `legacy-sdk` decoy correctly frozen on `Date.now()` (task 15); tenant/comment scoping is 404-not-403 and query-scoped by `tenant_id` everywhere (docs/permissions.md invariant); `POST /incidents` has no idempotency handling — matches the one documented, deliberate exception for task 18; `seal.sh` order matches D3 exactly (patch→delete→init→commit→ref→record→chown→reflog-expire/gc), `set -euo pipefail`, fails closed on embedded-newline paths, root:root 0444 records, `chown -R node:node /app` after sealing; `Dockerfile` base pinned by sha256 digest, toolchain at `/opt/owl/toolchain` is `chmod go-w` (root-owned, agent can't tamper), image size (589 MB) reasonable for a Node+TS toolchain image; snapshot algorithm is transitively tested (`test_patient_sealed` recomputes `owl_snapshot` from the real `owl/verifier/lib.sh` and diffs against what `seal.sh` baked in — not single-sourced, but drift-guarded, matching D3's documented centralization note); `specs/f2-suite-v1/tasks.md` T4 checkbox + test reference match what was actually built.

---

# Review cycle 2 — Lote 2 (T4 delta + T5)

**Final verdict:** APPROVED
**Content receipt:** `.claude/progress/receipt.txt` (feature `f2-lote2`, target `main`)

## T4 delta re-review (spec gap from cycle 1)

1. `canManageComments` removed from `patient/packages/core/src/tenant.ts` and its 3 assertions
   removed from `core/test/core.test.ts` — confirmed by `git diff`/`grep -rn canManageComments
   patient/` (no hits anywhere). Cycle 1's SPEC_MISS is resolved.
2. `sameTenant` also removed (same file/test) — implementer's own scan flagged it as unused dead
   code in the same spirit; it never encoded task 16's specific decision (tenant equality is the
   already-pervasive `WHERE tenant_id = ?` pattern every repo method already uses), so removing it
   is a quality improvement, not a second spec fix, but confirmed clean either way.
3. `log.ts` (informational note from cycle 1) now routes through `SystemClock` at module scope
   (`patient/packages/core/src/log.ts:1,12,15`) — M5-compliant. Reasoning for module-level (not
   per-call injected) `Clock` is documented inline and is sound: no task asserts on log timestamps,
   and threading a `Clock` through every `log.event`/`log.error` caller for that alone would be
   needless coupling.
4. `legacy-sdk` decoy (`patient/packages/legacy-sdk/src/index.ts`) untouched — confirmed via
   `git diff main -- patient/packages/legacy-sdk/` (no changes in this cycle).
5. Re-scanned every exported symbol under `patient/packages/*/src` for callers and for
   task-specific keywords (idempotency, mass-assignment, IDOR, tags, injection) outside the docs
   already accepted in cycle 1 (`permissions.md`, `sla.md`, `runbooks/stats.md`) — found nothing
   else that pre-solves a catalogue task's target dimension. `toCsv` (task 21's reuse target) is
   the one deliberate, documented exception, unchanged.

## T5 — `variants/navori.yaml#harness.init` sentinel + `test_navori_install_on_patient`

### Pass 1 — Spec compliance
**Partial verdict:** SPEC_OK

- Resolves T5 (R1): adds the third D13 check deferred from the spike (base-content survival) on
  top of the existing `.claude/agents` and `engram`-in-`.mcp.json` checks: [x]
- Scope respected (`variants/navori.yaml`, `tests/test_validate_docker.py` append-only,
  `specs/f2-suite-v1/tasks.md` checkbox): [x] — `git diff main -- variants/navori.yaml` is a
  6-line pure addition after the existing two checks; T4's fixtures/tests in
  `tests/test_validate_docker.py` are untouched, T5 only appends two helpers + one test.
- Sentinel check can't pass vacuously: [x] — `opsdesk-conventions-sentinel-f96c2e` is an
  opsdesk-specific string (not a generic marker navori's own injected blocks would ever emit;
  navori's managed blocks are `<!-- navori:managed id="..." -->`-shaped, never echo back
  arbitrary patient content), so a grep hit can only come from the patient's own pre-render
  content surviving. Verified negative case: `test_navori_install_on_patient`'s negative branch
  strips the marker via `sed` before running `init` and asserts the init call raises — this
  exercises the exact `grep -q ... || { ...; exit 1; }` line added to `navori.yaml`, not a
  simulated failure.
- `set -eu` at the top of `harness.init` (pre-existing, unchanged by T5); the two new checks use
  the same explicit `... || { echo ...; exit 1; }` pattern as the pre-existing `.claude/agents`
  and `.mcp.json` checks (`variants/navori.yaml:132-133` vs the new
  `:138-139`) — doesn't rely on `set -e` propagating through a `grep -q` (which exits non-zero on
  no-match already; the explicit `|| exit 1` is redundant-but-consistent with house style, not a
  gap). No `pipefail` needed here since neither new line is a pipeline.
- Exit-code propagation through `ClaudeCodeHarness`: `self.exec_as_agent(...)` runs
  `init_command` (`owl/agents/claude_code_harness.py:128-131`); confirmed via `review_f1.md`
  (cycle 1 of F1, still accurate — `harness.init` execution path unchanged by T5) that the
  underlying `_exec` raises `RuntimeError` on nonzero exit, so a failed sentinel check aborts the
  trial rather than continuing silently: [x]

### Pass 2 — Code quality
**Partial verdict:** QUALITY_OK

| Check | Status | Evidence |
|---|---|---|
| `ruff check .` | [x] | `All checks passed!` |
| `uv run pytest -m 'not docker'` | [x] | `7 passed, 17 deselected` |
| `uv run pytest -m docker tests/test_validate_docker.py` (full file, unfiltered) | [x] | `17 passed in 79.95s` — all pre-existing tests plus `test_patient_sealed` (T4) and `test_navori_install_on_patient` (T5) green together |

No new errors vs baseline; `test_navori_install_on_patient` follows the same
build/derive/seal/teardown pattern as T4's `sealed_container` fixture (own helpers
`_seal_fixture_container`/`_teardown_container`, not a copy-paste fork with drift risk since both
call the same `seal_dockerfile` recipe). Positive case asserts `.claude/agents` present, `"engram"`
in `.mcp.json`, and the sentinel in both `CLAUDE.md`/`AGENTS.md` — full coverage of what
`harness.init` now checks, exercised end-to-end against the real sealed patient fixture (not a
stub). No issues ≥50 found.

### Issues with confidence ≥80
None.

### Informational observations (50-79)
None new for T5. Cycle 1's two informational notes (`log.ts` M5 — now resolved, kept above for
the record; `docs/sla.md` phrasing) still stand as non-blocking.

## Verdict

Lote 2 (T4 + T5) — CHANGES_REQUESTED from cycle 1 is resolved; both partial verdicts are OK this
cycle. **APPROVED.** Receipt signed below.
