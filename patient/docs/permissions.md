# Permission matrix

Roles: `viewer`, `responder`, `admin`. Scope: every read and write is scoped to the caller's
tenant (`x-tenant-id`). A resource that exists in a different tenant is indistinguishable from one
that doesn't exist: both read as `404`, never `403`.

| Action                        | viewer | responder | admin |
|--------------------------------|:------:|:---------:|:-----:|
| List / read incidents          |   x    |     x     |   x   |
| Create incident                |        |     x     |   x   |
| Transition incident status     |        |     x     |   x   |
| Read comments                  |   x    |     x     |   x   |
| Create comment                 |   x    |     x     |   x   |
| Edit / delete another user's comment |  |           |   x   |
| Edit own comment               |        |     x     |   x   |

Mass assignment: a write endpoint accepts only the fields documented above for its body. A field
outside that set must be ignored, never persisted verbatim.
