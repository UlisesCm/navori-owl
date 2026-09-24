import type { DatabaseSync } from "node:sqlite";
import type { Clock } from "@opsdesk/core";

export interface DailyStats {
  date: string;
  opened: number;
  resolved: number;
  bySeverity: Record<string, number>;
}

/** Counts incidents opened/resolved "today". The day boundary is always UTC midnight — the
 * same boundary `opsdesk stats` (CLI) and this endpoint both use, so the two never disagree
 * (docs/runbooks/stats.md). Using the server's local zone here would undercount whenever the
 * local offset moves midnight earlier than UTC's. */
export function dailyStats(db: DatabaseSync, clock: Clock): DailyStats {
  const now = clock.now();
  const dayStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const dayStartIso = dayStart.toISOString();

  const opened = (
    db.prepare("SELECT COUNT(*) AS n FROM incidents WHERE created_at >= ?").get(dayStartIso) as { n: number }
  ).n;
  const resolved = (
    db.prepare("SELECT COUNT(*) AS n FROM incidents WHERE resolved_at IS NOT NULL AND resolved_at >= ?").get(
      dayStartIso
    ) as { n: number }
  ).n;

  const bySeverity: Record<string, number> = {};
  const rows = db
    .prepare("SELECT severity, COUNT(*) AS n FROM incidents WHERE created_at >= ? GROUP BY severity")
    .all(dayStartIso) as { severity: string; n: number }[];
  for (const row of rows) {
    bySeverity[row.severity] = row.n;
  }

  return { date: dayStartIso.slice(0, 10), opened, resolved, bySeverity };
}
