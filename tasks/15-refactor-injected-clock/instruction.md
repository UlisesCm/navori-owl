We want every timestamp opsdesk writes or returns from `packages/api` and `packages/db` to come
from the injectable `Clock` in `@opsdesk/core`, with no change in behavior. Several call sites in
those two packages currently read the wall clock directly (`Date.now()` / `new Date()`) even
though the enclosing class or function already receives a `Clock` instance — please route each of
those through that `Clock` instead of calling the wall clock.

This unblocks writing deterministic tests for anything time-derived (day boundaries, SLA timers,
scheduled reports) without needing to mock global `Date`.

Do not change any observable behavior — this is a pure refactor. `packages/legacy-sdk` is out of
scope.
