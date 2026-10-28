---
name: verify-before-done
description: 'Use when about to declare a task done — the Iron Law of task closure: no success claim without fresh evidence from the command that backs it. Applies to implementer, reviewer, publisher and any response that declares "done".'
metadata:
  type: behavior
  maxWords: 663
---

<!-- navori:managed id="verify-before-done-base" hash="8a467680" version="0.12.3" source="@navori/core" fmkeys="name,description,metadata" -->
# Verify Before Done

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

No run THIS TURN, no claim. "Should work" and "previous run was green" are inference.

## Gate function

BEFORE claiming "done / ready / approved": IDENTIFY the proving command → RUN it this turn → READ output, exit code, failures → VERIFY it confirms the claim (NO → declare the real state; YES → claim it WITH evidence).
## Table: claim → required output → not sufficient

| Claim | Required output | Not sufficient |
|---|---|---|
| `ruff check .` / `ruff check . && uv run pytest -m 'not docker'` green | Full command run this turn, exit 0 | "ran it before" |
| Gate answered `PASS (cached <date> … sha256 <hash>)` | Report it as cached, with date and log hash: a time shortcut, never review evidence | Claiming it as a fresh run |
| Zero new errors vs baseline | Classify per **Failure attribution** below, demonstrated over `main` | Diff location alone |
| UI validated in the browser (only if asked) | Observed state via the repo's browser tool | "looks fine in code" |
| Bug fixed | Reproduce the original symptom and see it NOT happen | "code changed, assumed fixed" |
| PR creatable | Pre-flight THIS TURN: not on the protected base branch, `gh auth status`, receipt `"status":"ok"` (prefer `navori receipt check …`; if the installed CLI lacks it, use the repository-built CLI); declared-inline change, your own run. No clean working tree required | "the branch has commits, we can create it" |
| Tests / type-check clean | Suite / `tsc --noEmit` run fresh, exit 0 | "should still be green" |
| A shell edit landed (`sed -i`, a `>` redirect) | Re-read the changed span | The exit code (`sed -i` exits 0 on no match) |
| Suites, builds or coverage in the same checkout | One at a time: parallel runs fight over `dist` and shared artifacts. Worktrees with their own `dist` may run together | Parallel runs |
| Active `dist` lock | Identify the owner, wait. Only a verified-dead owner's lock may be reclaimed | Deleting the lock, killing another session's process |
| Full gate red | Fix with focal tests; rerun the full gate once the fix set is stable. Mandatory before sign/ship | Rerunning after every edit |
| Gate outlives Bash timeout, main session | `run_in_background`, wait on completion or `Monitor`; `TaskStop` unneeded tasks first | Polling (`pgrep`, `ps \| grep`) |
| Gate outlives Bash timeout, subagent | Its `&&` steps one by one, foreground | Backgrounding — a subagent is never re-woken |

## Failure attribution

A failure is **introduced (demonstrated)**, **pre-existing (demonstrated)**, or **origin not determined**. Location relative to `git diff --name-only main` only orients; it never proves origin.

Only the **same command**, run over the comparable base and the change, demonstrates a state: runs disagree → introduced; agree → pre-existing; no comparable run → origin not determined.

Never `git stash` to measure it — it empties the shared tree. Never exempts a red gate.

## Red flags (STOP)

- About to write "done"/"ready"/"should work", or `git commit`/`APPROVED`, without a fresh `ruff check .` run and a full diff read.
- Trusting a subagent's report without verifying its **load-bearing claims** (cited `file:line`s plus the diff it touched) — scope defined in `.claude/agents/orchestrator.md` § Anti-broken-telephone, never a full re-read of a validated diff.

## Rationalization prevention

| Excuse | Reality |
|---|---|
| "Confident" / "passed 10 min ago" / "trivial" / "the subagent said done" | None exempts verification. Re-run. |

## When invoked

`implementer` before `done -> impl_<feature>.md`; `reviewer` before `APPROVED`; `publisher` in pre-flight; any agent before "done".

## Closing

State the claim, the fresh evidence, and any sub-claim you COULD NOT verify.
<!-- /navori:managed id="verify-before-done-base" -->

## Project-specific checks

<!-- user: add here claims specific to your repo and their required evidence. Suggestions:
     - DB migrations: command to validate the state (e.g. your ORM's migration status).
     - Critical areas: auth, permissions, payments, data integrity → specific checks per area.
     - Repo scripts that count as "valid evidence" (e.g. `pnpm e2e:smoke`).
     - Commands forbidden as evidence (e.g. "the Vercel preview" if it's not a real repro).
     - Recurring bug patterns of the repo where inference has historically failed.
-->
