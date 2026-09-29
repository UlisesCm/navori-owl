// FROZEN: published and pinned by external consumers (see patient CLAUDE.md, "packages/legacy-sdk
// is frozen"). Predates the Clock abstraction in @opsdesk/core, so it still reads Date.now()
// directly. Do not "fix" it as a drive-by change.
export interface LegacyTimestamp {
  epochMs: number;
}

export function currentLegacyTimestamp(): LegacyTimestamp {
  return { epochMs: Date.now() };
}
