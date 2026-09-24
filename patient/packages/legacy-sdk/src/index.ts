// FROZEN: published and pinned by external consumers (see patient CLAUDE.md, "packages/legacy-sdk
// is frozen"). Predates the Clock abstraction in @opsdesk/core, so it still reads Date.now()
// directly — a deliberate decoy for task 15 (refactor packages/api and packages/db onto Clock
// without touching this file). Do not "fix" it as a drive-by change.
export interface LegacyTimestamp {
  epochMs: number;
}

export function currentLegacyTimestamp(): LegacyTimestamp {
  return { epochMs: Date.now() };
}
