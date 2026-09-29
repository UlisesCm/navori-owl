Security report against the opsdesk API in `/app`: a caller authenticated for one tenant can get
other tenants' incidents back from `GET /incidents` when the `service` filter lists several
services, e.g. `GET /incidents?service=api,web` as tenant `t1` returns `t2`'s incidents too.
Please fix it, and keep the multi-value filters working as documented.
