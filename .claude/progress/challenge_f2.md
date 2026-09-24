# Challenge — f2-suite-v1 — 2026-09-24 — commit 5dbacf0 (branch feat/f2-suite-v1)

Falsifies `.claude/progress/solution_f2.md` + `specs/f2-suite-v1/design.md` against
`specs/f2-suite-v1/requirements.md` (R1–R17). No verdict — that's the orchestrator's call.

## Method
Read `harbor` 0.23 source in `.venv/lib/python3.13/site-packages/harbor/`, current
`tasks/00-smoke/`, `owl/agents/claude_code_harness.py`, `variants/navori.yaml`, `VISION.md`.
Ran cheap local checks: `npx --yes navori@0.10.0 init --yes` on a fresh repo with a pre-existing
`CLAUDE.md`; `docker run` against `node:22-bookworm-slim` for npm-global permissions and
`node:sqlite`/`.ts`; a local `docker compose build` with `FROM` a locally-tagged image and
`pull_policy: build`. No real model calls.

## BLOCKER — none

## CONCERN

**C1 — D13's `navori` workaround measures a codepath no real `npx navori@0.10.0` user gets.**
Reproduced the underlying bug myself, on the **published** package (design only verified HEAD
v0.10.0-4 locally and flagged the published version as unconfirmed — now confirmed):
`npx --yes navori@0.10.0 init --yes` on a repo with a pre-existing `CLAUDE.md` prints "Detecté
infraestructura Claude — uso modo 'coexist' (seguro)" and exits with "archivos existentes
intactos" — no `.claude/`, no `.mcp.json`, no agents/skills/hooks. Confirmed independently.
D13's fix (move `CLAUDE.md` aside, force `fresh` mode, reinsert the base content between
markers) does not exist in navori's public CLI — it's owl-only glue that makes the `navori`
variant *fully functional* in a scenario where a real user would be stuck with `coexist` and no
harness at all. The benchmark's `navori` variant therefore doesn't represent
`npx navori@0.10.0 init --yes` on an existing-`CLAUDE.md` repo; it represents a hypothetical
fixed version. Compared with the other variants (verified in `variants/*.yaml` and D13's own
text): `vanilla-bare` doesn't read `CLAUDE.md` by design, `codex-default` reads `AGENTS.md`, and
the plugin variants don't touch `CLAUDE.md` — none of them has an analogous "would silently fail
to install for a real user" gap that owl is patching over. This is legitimate as a *research*
choice (comparing harnesses' steady-state behavior, not onboarding bugs) but it is asymmetric:
one variant's install path was hand-fixed by the same people running the benchmark. The design
does surface this as an open question (§4, "workaround ahora + issue upstream en paralelo") and
doesn't hide it, which is why this is a CONCERN and not a BLOCKER — but "en paralelo" should be
"before F3 ships its report", and `RULES.md`/the F3 report should say explicitly, next to the
`navori` variant's results, that its install differs from the public CLI's default behavior on a
repo with an existing `CLAUDE.md`. Otherwise a reader compares "navori" against "codex-default,
run as documented" and "navori, run with an undisclosed patch to its onboarding".

**C2 — D5's stated rationale for non-root ("Claude Code rechaza `--dangerously-skip-permissions`
como root", VISION §7.1) is already worked around by Harbor itself.** Verified in
`.venv/lib/python3.13/site-packages/harbor/agents/installed/claude_code.py:1830-1831`: Harbor's
`ClaudeCode.run()` sets `env["IS_SANDBOX"] = "1"` specifically to "Allow bypassPermissions mode
when running as root inside containers." So `bypassPermissions` as root is not actually blocked
in Harbor's current adapter — `00-smoke` runs the agent as root today (no `USER` in
`tasks/00-smoke/environment/Dockerfile`, confirmed) and presumably already uses
`bypassPermissions` without issue. This doesn't break D5's recommendation — D5's real load-bearing
argument is baseline integrity + privilege separation of the verifier (D6.2), which stands on its
own — but the permission-mode justification in VISION §7.1 / D5's opening paragraph is factually
wrong as currently worded and should be corrected before it's cited again as evidence.

**C3 — R2's literal wording ("every task file") is not satisfiable as designed, and D4's proposed
narrowing is a judgment call being made by the architect, not the user.** R2 says "every task
file"; D4 exempts `instruction.md` on the grounds that Harbor hands it verbatim to the agent as
the prompt. That's a reasonable exemption, but it's a requirement change, correctly logged as an
open question ("[human] 3") — flagging only so the orchestrator doesn't let this slide into
"proceed" without the user actually answering it. Same for open question 4 (coexist workaround)
and open question 1 (pilot model) — three requirement-level decisions parked as questions for a
single verdict pass is a lot to leave open at challenge time; the orchestrator should get explicit
answers to at least 1 and 4 before greenlighting build, since both change what gets built (D12's
Haiku-vs-Sonnet split, D13's workaround-vs-upstream-fix split).

## NOTE

**N1 — `owl_begin`'s `rm -rf /logs/verifier/*` is load-bearing, not defensive boilerplate.**
Verified in `harbor/trial/single_step.py::SingleStepTrial._run_verifier`: for `SHARED` mode (the
mode F2 uses — single-container tasks, no `[[steps]]`), the shared-verifier path calls
`_run_shared_verifier` directly with **no** call to `_reset_shared_step_verifier_dirs` (that reset
only exists on the multi-step path, `Trial._run_step_verifier`, unused here). So Harbor does not
wipe `/logs/verifier` before running a single-step task's verifier — a `reward.json` an agent
planted during its 0777-mounted phase (`TrialPaths.chmod_dir`, confirmed 0o777 on
`trial_dir/agent_dir/user_agent_dir/verifier_dir/artifacts_dir`) really does survive into the
verifier phase unless the task's own `test.sh`/`owl_begin` cleans it. Hallazgo 3 and D6.1 are
correct, and worth restating plainly in the design (currently phrased as "el test.sh actual... no
limpia", true, but doesn't say Harbor itself never will either for single-step tasks).

**N2 — the `[agent] user`/`exec_as_root` split is real and already exercised by Harbor's own
agents, which de-risks D5.** Verified `AgentConfig.user`/`VerifierConfig.user` exist
(`harbor/models/task/config.py:342,565`) and that both `ClaudeCode.install()` (curl-bootstrap path
on non-Alpine, lands in `$HOME/.local/bin`, confirmed writable by uid 1000 in
`node:22-bookworm-slim`) and `Codex.install()` (nvm under `$HOME/.nvm`, then
`exec_as_root(... ln -sf .../usr/local/bin)`, `codex.py:343-382`) already run their install as the
non-root agent user and only escalate specific steps via `exec_as_root`. This is a good precedent
for `ClaudeCodeHarness.run`'s planned root rewrite of `/var/lib/owl/baseline` — same pattern
already in production code, not a novel risk. One thing NOT yet exercised by an existing example:
`navori init` running as `node` — the D13 workaround's `mv CLAUDE.md` / re-run / reinsert dance
needs to happen inside `init_command`, which today runs via `exec_as_agent` (non-root) per
`ClaudeCodeHarness.run`; moving the *original* `CLAUDE.md` aside before `init_command` runs and
restoring content after it needs either a root step bracketing `init_command`, or doing the whole
dance as the agent user (fine, since `/app` is `chown`'d to `node` before the agent phase) — the
design doesn't specify which, and it matters for where the byte-for-byte reinsert check runs.
Left as a design gap for the spike, not a blocker.

**N3 — `docker compose build` with `pull_policy: build` and a `FROM` pointing at a purely local,
unregistered image tag works as expected.** Reproduced directly: built a base image
`owl-patient-test:local` from a local Dockerfile, then built a child image `FROM
owl-patient-test:local` via a `docker-compose.yaml` mirroring
`harbor/environments/docker/docker-compose-build.yaml` (`build: {context: ...}`,
`pull_policy: build`). Succeeded without any registry error. D3's premise checks out; Failure
mode #2 in the design is being conservative rather than covering a real known risk (no `build:
pull:` override in Harbor's compose template that would force a registry pull).

**N4 — `node:sqlite` and bare `.ts` execution confirmed flagless on the exact image/version the
design cites.** `docker run node:22-bookworm-slim` (v22.23.3): `node:sqlite` works with only an
`ExperimentalWarning` (design's mitigation, `--disable-warning=ExperimentalWarning`, is the right
fix), and a `.ts` file runs directly via type stripping. Matches D1/D2's "sin flag" claims
verbatim.

**N5 — the scope-bypass and baseline-tamper vectors in hallazgo 2 are real in the shipped
`tasks/00-smoke/tests/test.sh` today**, not hypothetical: `git ls-files --others
--exclude-standard` and reading `.git/info/exclude` from inside `/app` are both confirmed in the
current script (`tasks/00-smoke/tests/test.sh:37-56`, own comments already document the
`.git/info/exclude`-based `runtime_state` mechanism, which is agent-writable). D6.3's fix
(exclude patterns sourced only from `/var/lib/owl/ignore`, root-owned, never `--exclude-standard`)
directly closes this; no counter-evidence found.

**N6 — task catalogue (point 5 of the brief): no verifier that leaks the answer or is obviously
gameable found in the 15-row table**, but two things are worth the orchestrator's attention rather
than a hard flag:
- `12-accidental-combined-filters` (D14) is explicitly speculative — "hasta 3 corridas… si ninguna
  produce regresión, se escribe a mano". That's an honest fallback, but it means the category's
  *realism* claim (an organically-produced accidental bug) is not guaranteed at design time; the
  catalogue entry should say "provisional" until the harvest actually runs, not read as settled.
- Holdout-as-siblings (30↔16, 31↔11/13, 32↔15) is the exact mechanism D10 itself calls out as
  losing calibration ("se acepta que su dificultad queda sin calibrada") — sibling-of-a-dev-task
  is weaker isolation than an independent author (open question 2, already flagged by the
  architect). Not a design flaw so much as an accepted, disclosed limitation given a one-person
  budget — but if nobody answers open question 2, F3 inherits an un-calibrated, self-authored
  holdout, which is exactly trap §14.7 territory (tasks designed by the harness's own author).

**N7 — `owl validate`'s ~180-trial / k=2 pilot arithmetic is internally consistent.** 15 tasks ×
(5 oracle + 1 nop + 6 cheat) = 180, matches D9's own count. The Beta(2,2) power argument in D12
(`P(0/2 or 2/2) = 0.6`) checks out: for `p~Beta(2,2)`, `E[p(1-p)] = ab/((a+b)(a+b+1)) = 4/20 = 0.2`,
so `P(neither 0/2 nor 2/2) = 2·E[p(1-p)] = 0.4` → `P(flagged) = 0.6`, exactly D12's number. The
design is honest that k=2 buys smoke-test coverage and cost, not calibration, and says so
explicitly — no overclaim found.

## R1–R17 coverage
All 17 requirements have a decision cited in the traceability table (design.md "Trazabilidad
R → decisión") and I did not find one with no corresponding component/decision. R2's scope is
narrowed by D4 (see C3). R12/R13 are carried over from F1 and match the current
`owl/gate.py`-shaped pattern the solution describes (not independently re-read in full — see
Gaps below).

## Gaps / not independently verified (time-boxed out)
- `owl/gate.py::check_trial`'s actual current `solution_hidden` pattern (design claims
  `baseline_valid` "sigue el mismo patrón") — not read; take D11 on the architect's word or have
  the reviewer confirm against the real file once F2 lands code.
- `harbor/verifier/verifier.py::Verifier._parse_reward_json` numeric-only rejection — cited by
  design, not independently opened; low risk, narrow claim.
- Whether `runuser` is present in `node:22-bookworm-slim` (D6.2 depends on it) — not checked;
  cheap to verify (`docker run node:22-bookworm-slim which runuser`), left for the spike as the
  design itself proposes.
- CheatAgent's six attacks (D8) were assessed for internal coherence only (each targets a distinct
  vector, one attack per trial so none masks another) — not runnable without the patient repo and
  tasks existing yet, so no dynamic falsification was possible; that's expected at design stage.
