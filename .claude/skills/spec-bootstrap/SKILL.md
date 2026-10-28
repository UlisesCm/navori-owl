---
name: spec-bootstrap
description: Use when starting a real-scope feature before writing code — scaffolds a complete SDD spec (requirements/design/tasks) with EARS and R<n>↔test traceability.
metadata:
  type: reference
  # #892: model invocation re-enabled (dropped `disable-model-invocation`) so
  # accepting a proposal in prose can trigger scaffolding without asking the
  # user to also type `/spec-bootstrap`. The opt-in gate moves into the body
  # below as a blocking precondition instead — the host has no frontmatter
  # field for "invocable but must confirm first" (audited against the
  # official skills doc, ticket 892). That precondition costs ~50 words the
  # 650 cap didn't have room for (647/650 before this change), so the cap
  # goes up explicitly rather than shrinking unrelated prose to make space —
  # the override is loud, not silent (skill-meta.ts). 720 leaves a real
  # margin (697/720) instead of reproducing the same 3-word squeeze.
  # Spec 0044 T10 (R10): E/M/A/T grammar added (delivery/milestone/acceptance/task
  # structure), +~150 words measured; 1050 = 981 actual + 7% margin.
  # #1273: re-measured at 823 after the Covers convention moved in; ceil(823 × 1.10)
  # = 906 (the 1050 above had drifted slack).
  maxWords: 906
  # Spec 0026 T16 (R35): the critical-areas challenge interpolates
  # auth, permissions, payments, data integrity INSIDE the managed zone, same defect as
  # review-diff (#683) — a verbose repo config pushes the composed file past
  # the asset's own cap with no plugin involved. Margin measured against the
  # skill-caps-composed.test.ts fixture. Spec 0044: +100 words margin
  # for composition with project config.
  maxWordsComposed: 1006
---

<!-- navori:managed id="spec-bootstrap" hash="3d07394f" version="0.12.3" source="@navori/core" fmkeys="name,description,metadata" -->
# spec-bootstrap — kickoff of an SDD spec

## Before scaffolding — blocking precondition

Do not write anything under `specs` unless the user has explicitly accepted starting a spec in THIS thread — either by running `/spec-bootstrap` directly, or by accepting a proposal you made. No acceptance yet? Propose it and wait for the answer; never scaffold speculatively.

## When to use this skill

When SDD work meets its threshold; **the threshold and its opt-in gate live in ONE place**: the **Spec Driven Development** block in `CLAUDE.md`. Before asking acceptance, give the compact `resumen de decisión` in chat per `formato-respuesta.md`; a proposal or summary is not authorization to scaffold.

Produces `specs/<feature>/{requirements.md, design.md, tasks.md}`. `orchestrator` scaffolds, not a nested subagent.

**Challenge on critical areas.** WHEN the spec touches `auth, permissions, payments, data integrity`, a fresh-context `auditor` challenges it with `solution-design`'s falsification brief before handoff. One round, no verdict — `orchestrator` decides.

## Order

1. **requirements.md first.** No clear requirements, no design. Derive from the ticket/request; each requirement is EARS with id `R<n>`.
2. **design.md** — how to meet those `R<n>`: affected components, contracts, decisions and trade-offs. Reference the `R<n>` each decision satisfies. Design BEFORE decomposing: an architecture decision (e.g. a contract or a migration path) moves task boundaries, so tasks written first get rewritten. The `architect` writes `design.md`, applying `solution-design`.
3. **tasks.md** — structured by deliveries `E<n>` (one PR each), milestones `M<n>` (one verification/commit each), acceptance criteria `A<n>` per milestone, and tasks `T<n>` that declare the `R<n>` they cover; see the grammar below. A spec without deliveries opens with `workplan: <feature>`; a delivery's workplan is level 3 (`"level": 3`), one per delivery `<spec>-e<n>` with phases = milestones, and its encargo is `spec: <spec> E<n> M<n>`.
4. **`evals.md` — optional, rare.** Only when the feature ships a new **always-on layer** (context every session pays for), where prose can't prove behavior moved: `specs/<feature>/evals.md` tabulates RED (without the layer) / GREEN (with it) over ONE isolated variable — same ticket, same repo, same model — with named scenarios, each failure against its evidence, and inverted results kept exactly as they came out. The raw transcript dies with the session; the distilled table survives in git.

The reasoning that fills `design.md` is the `solution-design` skill — also the lighter home for an R2-architectural change that skips a full spec.

## Templates

`requirements.md`:
```md
# <Feature> — Requirements

## Context
<1-2 lines: what problem it solves and for whom.>

## Requirements (EARS)
- **R1** — The system SHALL <observable action>.
- **R2** — WHEN <event>, the system SHALL <action>.
- **R3** — IF <undesired condition> THEN the system SHALL <containment action>.
```

`design.md` — the first three sections always; the rest ONLY when the feature
raises them (an empty section is noise, not rigor):
```md
# <Feature> — Design

## Approach
<Chosen architecture and why. Discarded trade-offs.>

## Components
- <file/module> — <responsibility> — covers R<n>.

## Decisions
- <non-obvious decision> — <reason>.

## Contracts            ← if it touches an API/DTO/schema/event
## Failure modes        ← if it has partial failure, retries, concurrency
## Migration            ← if data or an existing contract changes shape
## Testing strategy     ← each test answers a risk named above, not a coverage quota
## NOT in scope         ← deferred work + why, so nobody "improves things along the way"
```

`tasks.md` — E/M/A/T grammar (`navori spec check` parses this):
```md
# <Feature> — Tasks

## E1 — <title> (optional ' (foundation)')
Estimated LOC: <n>

### M1 — <title>
- **A1** [observable] — <desc> · `<command>` → <expected>
- [ ] **T1** (R<a>, R<b>) — <what> · effect: behavior|docs|tests|schema · test: <file>::<case>

### M2 — <title>
- **A2** — <desc> · `<command>` → <expected>
- [ ] **T2** (R<c>) — <what> · effect: behavior · test: <file>::<case>
- [ ] **T3** (R<d>, R<e>) — <what> · effect: docs · test: <file>::<heading>
```

## Hard rules

- **Zero unresolved placeholders.** Don't leave `<...>`; an unknown value is a question for the user, not a hole. Same rule inside a task: "TBD", "implement later" or "similar to T<n>" describe nothing — name the observable behavior and the evidence expected. That is NOT a licence to dictate the code line by line; the implementer keeps its judgment.
- **Cite a stable anchor, not a line number:** `file` + symbol name, heading, or managed-block id — never `file:line`. Lines drift before implementation; a stale one skips real sites.
- **Every `R<n>` ends in ≥1 task and ≥1 test**, and each test references its requirements with a `// Covers: R<n>` comment above the case. A requirement with no task or test isn't traceable → it doesn't enter the spec; without full traceability the feature is not done.
- **Tracking lives in `tasks.md`, not in `TaskCreate`.** Duplicating it makes the board drift from the spec; ignore the TaskList reminder in SDD sessions.
- **Self-review before closing the scaffolding:** is each `R<n>` a single testable action? does each task point to real `R<n>`? does the design cover all the `R<n>`? If something fails, fix it before handing the spec off.
<!-- /navori:managed id="spec-bootstrap" -->
