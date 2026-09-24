import type { DatabaseSync } from "node:sqlite";
import { ConflictError, NotFoundError, type Clock, type Incident, type IncidentStatus, type Severity } from "@opsdesk/core";
import { canTransition, nextResolvedAt } from "@opsdesk/core";
import { decodeCursor, encodeCursor, type Cursor } from "./pagination.ts";

export interface CreateIncidentInput {
  tenantId: string;
  service: string;
  severity: Severity;
  title: string;
}

export interface ListIncidentsFilter {
  tenantId: string;
  status?: IncidentStatus;
  service?: string;
  limit?: number;
  after?: string;
}

export interface ListIncidentsResult {
  incidents: Incident[];
  nextCursor: string | null;
}

interface Row {
  id: string;
  tenant_id: string;
  service: string;
  severity: string;
  status: string;
  title: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  version: number;
}

function toIncident(row: Row): Incident {
  return {
    id: row.id,
    tenantId: row.tenant_id,
    service: row.service,
    severity: row.severity as Severity,
    status: row.status as IncidentStatus,
    title: row.title,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    resolvedAt: row.resolved_at,
    version: row.version,
  };
}

export class IncidentsRepo {
  private readonly db: DatabaseSync;
  private readonly clock: Clock;

  constructor(db: DatabaseSync, clock: Clock) {
    this.db = db;
    this.clock = clock;
  }

  create(id: string, input: CreateIncidentInput): Incident {
    const now = this.clock.now().toISOString();
    this.db
      .prepare(
        `INSERT INTO incidents (id, tenant_id, service, severity, status, title, created_at, updated_at, resolved_at, version)
         VALUES (?, ?, ?, ?, 'open', ?, ?, ?, NULL, 1)`
      )
      .run(id, input.tenantId, input.service, input.severity, input.title, now, now);
    return this.get(input.tenantId, id)!;
  }

  get(tenantId: string, id: string): Incident | null {
    const row = this.db
      .prepare("SELECT * FROM incidents WHERE tenant_id = ? AND id = ?")
      .get(tenantId, id) as Row | undefined;
    return row ? toIncident(row) : null;
  }

  /** Seek pagination, ordered by (created_at, id): a stable, index-backed key tuple, never an
   * OFFSET (which repeats or skips rows under concurrent inserts). `limit + 1` rows are fetched
   * to know whether there is a next page without a separate COUNT query. */
  list(filter: ListIncidentsFilter): ListIncidentsResult {
    const limit = filter.limit ?? 20;
    const conditions: string[] = ["tenant_id = ?"];
    const params: unknown[] = [filter.tenantId];

    if (filter.status) {
      conditions.push("status = ?");
      params.push(filter.status);
    }
    if (filter.service) {
      conditions.push("service = ?");
      params.push(filter.service);
    }
    let cursor: Cursor | null = null;
    if (filter.after) {
      cursor = decodeCursor(filter.after);
      conditions.push("(created_at, id) > (?, ?)");
      params.push(cursor.createdAt, cursor.id);
    }

    const sql = `SELECT * FROM incidents WHERE ${conditions.join(" AND ")} ORDER BY created_at, id LIMIT ?`;
    params.push(limit + 1);
    const rows = this.db.prepare(sql).all(...(params as [])) as Row[];

    const hasMore = rows.length > limit;
    const page = hasMore ? rows.slice(0, limit) : rows;
    const last = page[page.length - 1];
    const nextCursor = hasMore && last ? encodeCursor({ createdAt: last.created_at, id: last.id }) : null;

    return { incidents: page.map(toIncident), nextCursor };
  }

  /** Optimistic concurrency (design D1: "concurrencia por version"): the caller must supply the
   * version it last read; a stale write is rejected instead of silently overwritten. */
  transition(tenantId: string, id: string, to: IncidentStatus, expectedVersion: number): Incident {
    const current = this.get(tenantId, id);
    if (!current) {
      throw new NotFoundError(`incident not found: ${id}`);
    }
    if (current.version !== expectedVersion) {
      throw new ConflictError(`stale version: expected ${expectedVersion}, have ${current.version}`);
    }
    if (!canTransition(current.status, to)) {
      throw new ConflictError(`cannot transition from ${current.status} to ${to}`);
    }
    const now = this.clock.now();
    const resolvedAt = nextResolvedAt(to, now, current.resolvedAt);
    const result = this.db
      .prepare(
        `UPDATE incidents SET status = ?, resolved_at = ?, updated_at = ?, version = version + 1
         WHERE tenant_id = ? AND id = ? AND version = ?`
      )
      .run(to, resolvedAt, now.toISOString(), tenantId, id, expectedVersion);
    if (result.changes === 0) {
      throw new ConflictError("concurrent update lost the race");
    }
    return this.get(tenantId, id)!;
  }
}
