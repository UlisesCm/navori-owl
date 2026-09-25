On-call filed this against opsdesk:

> `opsdesk stats` is under-counting today's incidents. I run it from the on-call laptop, which
> has `TZ=America/Mexico_City` set (that's our standing on-call timezone per the handoff docs).
> This morning it reported `{"opened": 0, ...}` for today even though `opsdesk incidents list
> --tenant t1` clearly shows a SEV1 that came in a few hours ago with today's timestamp. A
> teammate on a US Eastern machine ran `opsdesk stats` a few minutes later and it showed the
> incident correctly.
>
> Nobody touched the incident's `created_at`, and this isn't the first time the CLI's numbers
> have looked off first thing in the day — we always chalked it up to caching, but it seems to
> track with the operator's timezone more than anything else.

Fix `opsdesk stats` so it reports the correct count regardless of which timezone the machine
running it is set to.
