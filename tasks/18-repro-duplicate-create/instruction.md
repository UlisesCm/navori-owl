Clients that retry `POST /incidents` after a timeout end up with duplicate incidents: the first
request succeeded, the client never saw the response, and the retry created a second row.

Write a test that reproduces this. Do not fix the bug: leave every file outside the test
directories untouched.

The retry contract the fix will implement (your test is written against it): the client sends the
same optional header `Idempotency-Key: <string>` on both requests. Keys are scoped per tenant. A
`POST /incidents` that repeats a key already used by that tenant must return the incident the
first request created (same `id`, a 2xx status) and must not create another one; `GET /incidents`
then lists it exactly once. Requests without the header, or with different keys, still each
create their own incident.

Requirements for the test:
- Put it in a NEW file under `packages/api/test/` (for example `incident-retry.test.ts`), using
  the same style as `packages/api/test/app.test.ts` (`node:test`, `createApp`, in-memory db).
  Edits to existing test files are discarded.
- Today it must FAIL, and it must fail because of the duplicate (an assertion about the retry),
  not because of a crash or a syntax/import error. Once the retry contract above is implemented,
  the same test must PASS, with no changes to it.
- It must run with `npm test`.
