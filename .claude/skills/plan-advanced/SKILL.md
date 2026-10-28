---
name: plan-advanced
description: Use when `navori plan classify` returns level 2 (score ≥ 8 or a floor) or the plan gate escalates a feature after two rejections — runs the architect design, the auditor challenge and the user's choice before the level-2 workplan. Not for level 1 (plan-simple) or an accepted spec (spec-bootstrap).
metadata:
  type: reference
---

<!-- navori:managed id="plan-advanced" hash="0e302da5" version="0.12.3" source="@navori/core" fmkeys="name,description,metadata" -->
# plan-advanced — level-2 workplan

## Steps

1. Dispatch `architect` with the task, the signals and `classify`'s breakdown → it writes
   `solution_<feature>.md`.
2. Dispatch a fresh-context `auditor` (challenge encargo) → `solution_review_<feature>.md`.
3. Present the surviving options and challenge findings. Before asking the user to choose, give
   the compact `resumen de decisión` in chat per `formato-respuesta.md`, including recommendation,
   rationale, scope, pertinent risks/blockers and verification. "Present the surviving options to
   the user with the recommended one first and the challenge findings beside each; the user picks."
   If only one survives, say so and move on.
4. Your verdict, post-challenge: READY / CONCERNS / BLOCKED. `solution.verdict: BLOCKED` blocks dispatch;
   `bloqueado` means the criterion cannot be run or accepted until unblocked.
5. Write the level-2 workplan: everything `plan-simple` covers plus `solution {path, verdict}`,
   phases with their `A<n>`, and risks with their rollback; render and check it, then give the
   compact `resumen de decisión` in chat per `formato-respuesta.md` before asking for approval. As in
   `plan-simple`, an `A<n>` reaches `cumplido` only with evidence the routing-watch hook recorded
   because the host ran its exact `command`. Also: replan when `navori plan classify <feature> --diff` returns a higher level, and update `level` and `classification` in the workplan.
6. Two `CHANGES_REQUESTED`: at level 0/1, a fresh `solution_<f>.md` and its challenge before the next dispatch (each pair of rejections needs its own); at level ≥2, escalate to the user, who alone authorizes another round with `navori plan escalation-reset`. The architect diagnoses why the previous design failed before redesigning.
7. "Knowledge destinations the architect proposes are proposals: write none without the user's
   approval, and a Dominio entry only on explicit approval."
8. Receipts, gate logs and `navori plan escalation-reset` are local attestations without authentication: seatbelts, not boundaries. Codex review independence depends on `CODEX_THREAD_ID`.

## Before declaring done

- [ ] `architect` dispatched with task, signals and `classify`'s breakdown; `solution_<feature>.md`
      exists.
- [ ] Fresh-context `auditor` challenge ran; `solution_review_<feature>.md` exists.
- [ ] Surviving options presented to the user with the recommended one first and the challenge
      findings beside each (or the single survivor named); the user picked.
- [ ] Your verdict recorded: READY / CONCERNS / BLOCKED; a `BLOCKED` solution blocks dispatch.
- [ ] Level-2 workplan written (solution reference, phases with `A<n>`, risks with rollback),
      rendered, checked green, and approved.
- [ ] Replanned on a higher `classify --diff` level, with `level` and `classification` updated.
- [ ] Two rejections handled by the R38 rule above; after the second, the diagnosis in both
      `solution_<feature>.md` and `solution_review_<feature>.md` precedes any redesign.
- [ ] No knowledge destination written without the user's explicit approval.
- [ ] Receipts and resets treated as local attestations; Codex review independence checked via `CODEX_THREAD_ID`.

If any item fails, fix it and re-run the whole list.
<!-- /navori:managed id="plan-advanced" -->

## This repo's level-2 workplans

<!-- user: add here what's specific to your repo — who reviews `solution_<feature>.md`
     before the user sees it, and any local convention for phase boundaries or
     rollback evidence. -->
