# Runbook: `opsdesk stats`

`opsdesk stats` and `GET /stats` (`packages/api/src/stats.ts`) must always agree, because on-call
reads whichever one is faster to reach. Both compute "today" from the same UTC day boundary
(`Date.UTC(year, month, date)` on the clock's current instant) — never the host's local timezone,
which would move midnight earlier or later than UTC and silently under- or over-count incidents
opened near the boundary.

If the two ever disagree, check `packages/api/src/stats.ts` and `packages/cli/src/commands.ts`
(`stats`) for a boundary computed differently between them before assuming the data is wrong.
