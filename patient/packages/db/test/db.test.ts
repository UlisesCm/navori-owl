import assert from "node:assert/strict";
import { test } from "node:test";
import { FixedClock } from "@opsdesk/core";
import { openDb } from "../src/db.ts";
import { IncidentsRepo } from "../src/incidents-repo.ts";
import { CommentsRepo } from "../src/comments-repo.ts";

function setup() {
  const db = openDb(":memory:");
  db.prepare("INSERT INTO tenants (id, name) VALUES (?, ?)").run("t1", "Tenant One");
  db.prepare("INSERT INTO tenants (id, name) VALUES (?, ?)").run("t2", "Tenant Two");
  const clock = new FixedClock(new Date("2026-01-01T00:00:00.000Z"));
  return { db, clock, incidents: new IncidentsRepo(db, clock), comments: new CommentsRepo(db, clock) };
}

test("create + get round-trips an incident", () => {
  const { incidents } = setup();
  incidents.create("i1", { tenantId: "t1", service: "api", severity: "SEV2", title: "slow" });
  const got = incidents.get("t1", "i1");
  assert.equal(got?.status, "open");
  assert.equal(got?.severity, "SEV2");
});

test("get is scoped by tenant: another tenant's id reads as null, never a cross-tenant hit", () => {
  const { incidents } = setup();
  incidents.create("i1", { tenantId: "t1", service: "api", severity: "SEV2", title: "slow" });
  assert.equal(incidents.get("t2", "i1"), null);
});

test("list paginates by cursor without skipping or repeating rows", () => {
  const { incidents, db } = setup();
  for (let i = 0; i < 5; i++) {
    db.prepare(
      "INSERT INTO incidents (id, tenant_id, service, severity, status, title, created_at, updated_at, version) VALUES (?, 't1', 'api', 'SEV3', 'open', ?, ?, ?, 1)"
    ).run(`i${i}`, `incident ${i}`, `2026-01-0${i + 1}T00:00:00.000Z`, `2026-01-0${i + 1}T00:00:00.000Z`);
  }
  const page1 = incidents.list({ tenantId: "t1", limit: 2 });
  assert.equal(page1.incidents.length, 2);
  assert.equal(page1.incidents[0]?.id, "i0");
  assert.ok(page1.nextCursor);

  const page2 = incidents.list({ tenantId: "t1", limit: 2, after: page1.nextCursor! });
  assert.deepEqual(page2.incidents.map((i) => i.id), ["i2", "i3"]);

  const page3 = incidents.list({ tenantId: "t1", limit: 2, after: page2.nextCursor! });
  assert.deepEqual(page3.incidents.map((i) => i.id), ["i4"]);
  assert.equal(page3.nextCursor, null);
});

test("list combines status and service filters (both must hold, never just the last one)", () => {
  const { incidents, db } = setup();
  db.prepare(
    "INSERT INTO incidents (id, tenant_id, service, severity, status, title, created_at, updated_at, version) VALUES ('a', 't1', 'api', 'SEV3', 'open', 'a', '2026-01-01T00:00:00.000Z', '2026-01-01T00:00:00.000Z', 1)"
  ).run();
  db.prepare(
    "INSERT INTO incidents (id, tenant_id, service, severity, status, title, created_at, updated_at, version) VALUES ('b', 't1', 'web', 'SEV3', 'open', 'b', '2026-01-02T00:00:00.000Z', '2026-01-02T00:00:00.000Z', 1)"
  ).run();
  db.prepare(
    "INSERT INTO incidents (id, tenant_id, service, severity, status, title, created_at, updated_at, version) VALUES ('c', 't1', 'api', 'SEV3', 'closed', 'c', '2026-01-03T00:00:00.000Z', '2026-01-03T00:00:00.000Z', 1)"
  ).run();
  const result = incidents.list({ tenantId: "t1", status: "open", service: "api" });
  assert.deepEqual(result.incidents.map((i) => i.id), ["a"]);
});

test("transition rejects a stale version (optimistic concurrency)", () => {
  const { incidents } = setup();
  incidents.create("i1", { tenantId: "t1", service: "api", severity: "SEV2", title: "slow" });
  incidents.transition("t1", "i1", "investigating", 1);
  assert.throws(() => incidents.transition("t1", "i1", "resolved", 1), /stale version/);
});

test("transition to resolved sets resolvedAt once", () => {
  const { incidents } = setup();
  incidents.create("i1", { tenantId: "t1", service: "api", severity: "SEV2", title: "slow" });
  const resolved = incidents.transition("t1", "i1", "resolved", 1);
  assert.ok(resolved.resolvedAt);
});

test("comments are scoped by tenant", () => {
  const { incidents, comments } = setup();
  incidents.create("i1", { tenantId: "t1", service: "api", severity: "SEV2", title: "slow" });
  comments.create("c1", "t1", "i1", "u1", "looking into it");
  assert.equal(comments.get("t2", "c1"), null);
  assert.equal(comments.get("t1", "c1")?.body, "looking into it");
});
