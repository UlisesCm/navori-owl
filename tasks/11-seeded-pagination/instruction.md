`GET /incidents` pagination is returning duplicate rows across pages.

Repro: create three incidents, in order, titled "db timeout", "disk full" and "api 500" (any
tenant, service, severity). Call `GET /incidents?limit=1`; it correctly returns "db timeout" and
a `nextCursor`. Call `GET /incidents?limit=1&cursor=<that nextCursor>`; it should return "disk
full", but it returns "db timeout" again — the last incident of the previous page leaks into the
next one.

Fix the pagination in `packages/db` so no incident is ever returned on more than one page,
regardless of page size or how many incidents exist.
