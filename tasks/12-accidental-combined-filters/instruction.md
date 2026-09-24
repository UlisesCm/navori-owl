A support engineer filed this against opsdesk:

> Filtering the incident list by status AND service returns incidents that don't match the status.
> For example, `GET /incidents?status=open&service=payments` (same with
> `opsdesk incidents list --status open --service payments`) comes back with `resolved` and
> `closed` payments incidents mixed in with the `open` ones. Filtering by `status=open` alone, or
> by `service=payments` alone, both work correctly — it's only when the two are combined that
> `status` gets ignored.

Fix the incident list filtering so that passing both `status` and `service` returns only incidents
that match both.
