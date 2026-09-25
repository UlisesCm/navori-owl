opsdesk needs tag support on incidents, so responders can group and filter them by area without
disturbing the existing status/service workflow.

Add:

1. **Tag an incident.** `POST /incidents/:id/tags` with body `{ "tag": "<value>" }`. Requires the
   same write permission as transitioning an incident (`responder` or `admin`; a `viewer` gets
   `403`). Adding a tag that's already on the incident is a no-op: it is never duplicated and never
   errors. The response body is `{ "id": "<incident id>", "tags": [...] }` with the incident's
   current tags, sorted alphabetically — `201` if the tag was newly added, `200` if it was already
   there.

2. **Remove a tag.** `DELETE /incidents/:id/tags/:tag`. Same write permission. Removing a tag that
   isn't on the incident is also a no-op — always `200` with the incident's current tags (sorted
   alphabetically), never an error.

3. **List an incident's tags.** `GET /incidents/:id/tags` returns `200` with `{ "tags": [...] }`,
   sorted alphabetically. Any authenticated role can call it, same as reading the incident itself.

4. **Show tags on incidents.** `GET /incidents` and `GET /incidents/:id` responses gain a `tags`
   field (sorted alphabetically) on every incident object, alongside the existing fields.

5. **Filter by tag.** `GET /incidents?tag=<value>` returns only incidents carrying that tag. It
   combines with `status` and `service` the same way those two already combine with each other:
   every filter given must hold at once (AND), never just the last one applied.

6. **Tag format.** A tag is normalized before it is stored or matched: trimmed and lowercased (so
   `Prod` and `prod` are the same tag). After normalization it must be 1 to 32 characters, made up
   only of lowercase letters, digits and hyphens (`a-z0-9-`). Anything else — empty, too long, or
   containing another character — is rejected with `400`
   (`{ "error": "validation_error", "message": "..." }`, the same shape every other validation
   error in this API already uses) on `POST /incidents/:id/tags` and on the `?tag=` filter alike.

7. **Tenant isolation.** Every one of these endpoints follows the existing rule
   (`docs/permissions.md`): an incident id from another tenant reads as `404`, never `403`.

8. **CLI.** `opsdesk incidents list` gets a new `--tag <value>` flag, combining with
   `--status`/`--service` the same way (AND). Same normalization and rejection rule as the API: an
   invalid tag value makes the command fail loudly (an error, same as today's `--tenant is
   required` check) instead of silently printing nothing. The existing output format — one
   tab-separated line per incident (id, severity, status, service, title) — is unchanged.

One example, to be concrete: tagging an incident with `Payments-Outage` stores it as
`payments-outage`. A later `GET /incidents?tag=payments-outage` (or
`opsdesk incidents list --tag payments-outage`) returns it, and so does
`GET /incidents?tag=Payments-Outage` (mixed case), because the filter value goes through the same
normalization as the stored tag.
