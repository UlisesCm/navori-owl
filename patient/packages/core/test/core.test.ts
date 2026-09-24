import assert from "node:assert/strict";
import { test } from "node:test";
import { FixedClock } from "../src/clock.ts";
import { toCsv } from "../src/csv.ts";
import { canTransition, isSeverity, nextResolvedAt } from "../src/incident.ts";
import { canWrite } from "../src/tenant.ts";
import { AppError, NotFoundError } from "../src/errors.ts";

test("FixedClock returns the fixed instant", () => {
  const d = new Date("2026-01-01T00:00:00.000Z");
  assert.equal(new FixedClock(d).now().toISOString(), d.toISOString());
});

test("toCsv quotes fields with commas, quotes and newlines (RFC 4180)", () => {
  const csv = toCsv(["a", "b"], [["plain", 'has "quote", and\ncomma']]);
  assert.equal(csv, 'a,b\r\nplain,"has ""quote"", and\ncomma"\r\n');
});

test("isSeverity accepts only SEV1..SEV4", () => {
  assert.equal(isSeverity("SEV1"), true);
  assert.equal(isSeverity("Sev1"), false);
});

test("incident state machine forbids leaving closed", () => {
  assert.equal(canTransition("open", "investigating"), true);
  assert.equal(canTransition("closed", "open"), false);
});

test("nextResolvedAt sets resolvedAt once and keeps it on repeated resolve", () => {
  const now = new Date("2026-01-01T00:00:00.000Z");
  assert.equal(nextResolvedAt("resolved", now, null), now.toISOString());
  assert.equal(nextResolvedAt("resolved", now, "earlier"), "earlier");
  assert.equal(nextResolvedAt("investigating", now, "earlier"), null);
});

test("role write checks", () => {
  assert.equal(canWrite("viewer"), false);
  assert.equal(canWrite("responder"), true);
});

test("NotFoundError is an AppError with statusCode 404", () => {
  const err = new NotFoundError();
  assert.ok(err instanceof AppError);
  assert.equal(err.statusCode, 404);
});
