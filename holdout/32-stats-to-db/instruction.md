`opsdesk stats` gets its numbers from `dailyStats` in `packages/api/src/stats.ts`, so the CLI package has to depend on the HTTP package just to run a database query. Please fix that layering in `/app`:

- `dailyStats` (and its `DailyStats` type) should live in `@opsdesk/db` and be exported from there, with the same `(db, clock)` signature.
- `opsdesk stats` must no longer depend on `@opsdesk/api`.
- `@opsdesk/api` should keep exporting `dailyStats` and `DailyStats` for now (re-exported, not a second copy), and `GET /stats` should keep working as before.
- Nothing about what either `GET /stats` or `opsdesk stats` reports should change.
- Anything in the docs that points at the old location should be updated.
