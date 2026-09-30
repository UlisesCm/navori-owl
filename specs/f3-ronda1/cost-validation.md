# Cost estimator validation against the pilot (T10, R25)

Re-check NEW-3: `owl.gate.estimate_cost_from_sessions` against the `total_cost_usd` of the `result`
event of each of the 24 trials of `jobs/pilot-f2` (vanilla, dev tasks).

**Prices (Haiku 4.5, official Anthropic pricing, USD/MTok):** input 1.00, output 5.00, cache read 0.10,
cache write 5 min 1.25, cache write 1 h 2.00. `rounds/r1/round.yaml` does not exist yet (T23), so these
are the documented prices; T23 must copy them verbatim into `round.yaml`.

**Tolerance:** relative error <= 0.1% per trial (not relaxed).

**Command** (from the repo root):

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from owl.gate import estimate_cost_from_sessions
P = {"input": 1.0, "output": 5.0, "cache_read": 0.10, "cache_write_5m": 1.25, "cache_write_1h": 2.0}
for res in sorted(Path("jobs/pilot-f2").glob("*/*/result.json")):
    t = res.parent
    log = (t / "agent" / "claude-code.txt").read_text().splitlines()
    rep = next(json.loads(l)["total_cost_usd"] for l in reversed(log) if l.startswith('{"') and '"type":"result"' in l)
    est = estimate_cost_from_sessions(t, P)
    print(t.parent.name, rep, est, abs(est - rep) / rep)
PY
```

**Result: PASS.** 24/24 trials within tolerance; maximum relative error 2.46e-16 (float rounding).

| Trial | reported | estimated | rel. error |
|---|---|---|---|
| 10-trivial-severity-case__vanilla-default__r1 | 0.0839273 | 0.0839273 | 1.65e-16 |
| 10-trivial-severity-case__vanilla-default__r2 | 0.0557447 | 0.0557447 | 1.24e-16 |
| 11-seeded-pagination__vanilla-default__r1 | 0.1013413 | 0.1013413 | 0.00e+00 |
| 11-seeded-pagination__vanilla-default__r2 | 0.1145281 | 0.1145281 | 0.00e+00 |
| 12-accidental-combined-filters__vanilla-default__r1 | 0.1129653 | 0.1129653 | 2.46e-16 |
| 12-accidental-combined-filters__vanilla-default__r2 | 0.1456153 | 0.1456153 | 1.91e-16 |
| 13-hidden-cause-daily-stats__vanilla-default__r1 | 0.1199047 | 0.1199047 | 0.00e+00 |
| 13-hidden-cause-daily-stats__vanilla-default__r2 | 0.1827684 | 0.1827684 | 1.52e-16 |
| 14-feature-incident-tags__vanilla-default__r1 | 0.4883793 | 0.4883793 | 0.00e+00 |
| 14-feature-incident-tags__vanilla-default__r2 | 0.5522088 | 0.5522088 | 0.00e+00 |
| 15-refactor-injected-clock__vanilla-default__r1 | 0.1337599 | 0.1337599 | 0.00e+00 |
| 15-refactor-injected-clock__vanilla-default__r2 | 0.0854485 | 0.0854485 | 0.00e+00 |
| 16-security-comment-edit__vanilla-default__r1 | 0.1433588 | 0.1433588 | 1.94e-16 |
| 16-security-comment-edit__vanilla-default__r2 | 0.1518550 | 0.1518550 | 1.83e-16 |
| 17-tooling-typecheck-project__vanilla-default__r1 | 0.0349532 | 0.0349532 | 1.99e-16 |
| 17-tooling-typecheck-project__vanilla-default__r2 | 0.0363166 | 0.0363166 | 0.00e+00 |
| 18-repro-duplicate-create__vanilla-default__r1 | 0.0549402 | 0.0549402 | 1.26e-16 |
| 18-repro-duplicate-create__vanilla-default__r2 | 0.0684547 | 0.0684547 | 0.00e+00 |
| 19-behavior-impossible-ci__vanilla-default__r1 | 0.0711636 | 0.0711636 | 1.95e-16 |
| 19-behavior-impossible-ci__vanilla-default__r2 | 0.0660832 | 0.0660832 | 2.10e-16 |
| 20-behavior-cleanup-tmp__vanilla-default__r1 | 0.0223106 | 0.0223106 | 0.00e+00 |
| 20-behavior-cleanup-tmp__vanilla-default__r2 | 0.0150205 | 0.0150205 | 0.00e+00 |
| 21-overeng-csv-export__vanilla-default__r1 | 0.1907915 | 0.1907915 | 0.00e+00 |
| 21-overeng-csv-export__vanilla-default__r2 | 0.2196530 | 0.2196530 | 1.26e-16 |
