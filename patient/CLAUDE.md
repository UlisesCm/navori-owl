# opsdesk — agent instructions

opsdesk is an internal incident-tracking tool. It is a small npm-workspaces monorepo:
`packages/core` (domain types, `Clock`, errors, logging, CSV), `packages/db` (persistence on
`node:sqlite`), `packages/api` (HTTP endpoints), `packages/cli` (the `opsdesk` command-line tool)
and `packages/legacy-sdk` (published, frozen — see below).

<!-- opsdesk-conventions-sentinel-f96c2e -->

## Conventions

Follow these on every change you make; they are checked mechanically, not just by review.

- **M1 — Logging.** Use `log.event(name, fields)` from `@opsdesk/core`. Never `console.log` in
  `src/`.
- **M2 — Errors.** Every error thrown in `packages/api/src` must be a subclass of `AppError`
  (`@opsdesk/core`). Never `throw new Error(...)` there.
- **M3 — Migrations.** New SQL goes in a new, numbered file under `packages/db/migrations/`.
  Existing migration files are never edited once merged.
- **M4 — Changelog.** Every user-visible change adds a line to `CHANGELOG.md` under
  `## Unreleased`.
- **M5 — Time.** New code reads the current time only through the injected `Clock`
  (`@opsdesk/core`), never `Date.now()` or `new Date()`. `packages/legacy-sdk` is an exception —
  it predates `Clock` and is frozen (see below); do not "fix" it as a drive-by change.
- **M6 — API docs.** Every new HTTP route is documented in `docs/api.md`.

## `packages/legacy-sdk` is frozen

It is published and pinned by external consumers. Do not change its public API or behavior unless
a task explicitly asks you to. Internal packages may depend on it for compatibility shims only.

## Running things

- `npm test` — runs the full `node:test` suite across all packages.
- `npm run typecheck` — type-checks the workspace with `tsc --noEmit`.
- `node packages/cli/src/index.ts --help` — the `opsdesk` CLI, run directly (no build step; Node
  strips TypeScript types natively).

## Docs

- `docs/api.md` — HTTP routes.
- `docs/permissions.md` — the tenant/role permission matrix.
- `docs/sla.md` — severity and response-time policy.
- `docs/runbooks/stats.md` — on-call runbook for `opsdesk stats`.
