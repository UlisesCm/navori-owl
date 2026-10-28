---
name: plan-simple
description: Use when `navori plan classify` returns level 1 or the plan gate denies an implementer dispatch — writes the level-1 workplan JSON, renders and checks it, and keeps it current while the work runs. Not for level 2 (plan-advanced) or an accepted spec (spec-bootstrap).
metadata:
  type: reference
---

<!-- navori:managed id="plan-simple" hash="fc246c15" version="0.12.3" source="@navori/core" fmkeys="name,description,metadata" -->
# plan-simple — level-1 workplan

## Steps

1. Draft `.navori/state/handoffs/workplan_<feature>.json`: a one-line observable goal; 1 to 5
   `A<n>` criteria, each with `command` and `expected`; at least one item out of scope;
   files measured against the repo (`"new": true` for new ones); declared signals
   (`floor:<name>`, `critical-area:declared`, `bug-without-root-cause`) in `classification.signals`:

   ```json
   {
     "feature": "<feature>",
     "level": 1,
     "classification": { "score": 0, "level": 1, "signals": [] },
     "objective": "<one observable line>",
     "acceptance": [{ "id": "A1", "description": "<criterion>", "command": "<exact command>", "expected": "<observable output>" }],
     "outOfScope": ["<item>"],
     "files": [{ "path": "<path>", "new": false }]
   }
   ```

2. Run `navori plan classify <feature>` → tell the user the level, score and breakdown in ≤ 4
   lines. If it comes back level 2 or higher, switch to `plan-advanced`.
3. Run `navori plan render <feature>` and `navori plan check <feature>` until both are green;
   give the compact `resumen de decisión` in chat per `formato-respuesta.md`, including recommendation,
   scope, pertinent risks/blockers and verification; then
   show the rendered `.md` and wait for the user's approval.
4. "Open every implementer encargo with `workplan: <feature>` and list the `A<n>` that sub-task covers."
5. "When a sub-task closes, record it with `navori plan update`" (each `A<n>`'s status and
   decisions); `progress/current.md` points at the workplan, it doesn't copy it. Acceptance evidence depends on the host's signal (Claude's main thread included): the routing-watch hook records it only when the host itself ran the exact `command` of that `A<n>`. `--progress A<n>=cumplido` is accepted only with that evidence, and `cumplido` without evidence is a `plan check` warning. A single owner runs `navori plan update` and must mark right after running the command on the same tree.
6. A change outside the approved files is a decision: record it and ask the user before
   dispatching it.
7. "Never write `workplan_<feature>.md` by hand — it is `navori plan render` output."

Level 2's `solution.verdict: BLOCKED` blocks dispatch; `bloqueado` means the criterion cannot be run or accepted until unblocked.

## Before declaring done

- [ ] Workplan drafted with a one-line goal, 1-5 `A<n>` with `command`/`expected`, ≥1 out-of-scope
      item, measured files, declared signals.
- [ ] `navori plan classify <feature>` ran and the level/score/breakdown went to the user in ≤ 4
      lines; a level ≥ 2 result switched to `plan-advanced`.
- [ ] `navori plan render` and `navori plan check` both green; the user approved the rendered `.md`.
- [ ] Every implementer encargo opened with `workplan: <feature>` and its `A<n>` list.
- [ ] Each closed sub-task recorded with `navori plan update`, `cumplido` only after the host ran the exact `A<n>` command.
- [ ] A file outside the approved scope was either recorded as a decision with the user's
      go-ahead, or never dispatched.

If any item fails, fix it and re-run the whole list.
<!-- /navori:managed id="plan-simple" -->

## This repo's level-1 workplans

<!-- user: add here what's specific to your repo — where the `A<n>` commands
     typically live (test runner, lint target), and any local convention for
     naming out-of-scope items. -->
