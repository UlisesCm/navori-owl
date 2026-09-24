import assert from "node:assert/strict";
import { mkdtempSync, existsSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { FixedClock } from "@opsdesk/core";
import { openDb } from "@opsdesk/db";
import { IncidentsRepo } from "@opsdesk/db";
import { cleanupTmp, exportIncidents, incidentsList, type CommandContext } from "../src/commands.ts";

function makeCtx(lines: string[]): CommandContext {
  const db = openDb(":memory:");
  db.prepare("INSERT INTO tenants (id, name) VALUES ('t1', 'Tenant One')").run();
  const clock = new FixedClock(new Date("2026-01-01T00:00:00.000Z"));
  new IncidentsRepo(db, clock).create("i1", { tenantId: "t1", service: "api", severity: "SEV1", title: "down" });
  return {
    db,
    clock,
    stdout: (line) => lines.push(line),
    dataDir: mkdtempSync(join(tmpdir(), "opsdesk-cli-")),
  };
}

test("incidents list prints severity exactly as stored (SEV1, never reformatted)", () => {
  const lines: string[] = [];
  const ctx = makeCtx(lines);
  incidentsList(ctx, "t1", {});
  assert.ok(lines[0]?.includes("SEV1"));
  assert.ok(!lines[0]?.includes("Sev1"));
});

test("export writes a CSV under data/tmp and cleanup removes only that directory's files", () => {
  const lines: string[] = [];
  const ctx = makeCtx(lines);
  const path = exportIncidents(ctx, "t1");
  assert.ok(existsSync(path));
  assert.ok(path.includes(join(ctx.dataDir, "tmp")));

  const backupsDir = join(ctx.dataDir, "backups");
  mkdirSync(backupsDir, { recursive: true });
  writeFileSync(join(backupsDir, "keep-me.txt"), "do not delete");

  const removed = cleanupTmp(ctx);
  assert.ok(removed.length >= 1);
  assert.ok(existsSync(join(backupsDir, "keep-me.txt")), "backups must survive cleanup");
  assert.deepEqual(readdirSync(backupsDir), ["keep-me.txt"]);
});
