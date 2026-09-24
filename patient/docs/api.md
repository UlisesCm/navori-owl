# opsdesk HTTP API

Every request must carry `x-tenant-id`, `x-role` (`viewer` | `responder` | `admin`) and
`x-user-id` — set by the gateway in front of this service (out of scope here).

Tenant isolation: a resource id from another tenant always reads as `404 Not Found`. It is never
`403 Forbidden` — that would confirm the resource exists in someone else's tenant.

## `GET /incidents`

Query params: `status`, `service`, `cursor`, `limit` (default 20). `status` and `service` combine
with AND when both are given. Returns `{ incidents: Incident[], nextCursor: string | null }`.
`cursor` is opaque; pass back the `nextCursor` from the previous page to get the next one.

## `POST /incidents`

Body: `{ service, severity, title }`. `severity` is one of `SEV1`..`SEV4`. Requires `responder` or
`admin`. Returns `201` with the created incident (`status: "open"`).

## `GET /incidents/:id`

Returns the incident or `404`.

## `POST /incidents/:id/transition`

Body: `{ to, expectedVersion }`. Optimistic concurrency: `expectedVersion` must match the
incident's current `version`, or the request fails with `409`. Requires `responder` or `admin`.

## `GET /incidents/:id/comments`

Lists comments for an incident, oldest first.

## `POST /incidents/:id/comments`

Body: `{ body }`. Any authenticated role may comment.

## `GET /stats`

Returns today's counts: `{ date, opened, resolved, bySeverity }`. "Today" is always a UTC day
boundary — see `docs/runbooks/stats.md`.
