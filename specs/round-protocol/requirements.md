# Round protocol — Requirements

## Context
F3 builds round 1 by hand: the versions it measures were pinned weeks before the round, the
refresh steps (new spike, prefix audit, price validation, smoke, holdout sync) live only in the F3
spec, and nothing in `owl` stops a round from mixing pins or reusing a revealed holdout task. This
spec turns that knowledge into a reusable protocol so round N only instantiates `rounds/<id>/`: a
declared cutoff date and pin set, conformance checks that enforce them, a burned-holdout registry and
a written refresh procedure with its triggers.

## Requirements (EARS)

### Cutoff and pins
- **R1** — The system SHALL require in `round.yaml` a `cutoff_date` (ISO date) and a `pins` section with the Harbor version and, for every round variant that installs a harness, that harness's version; the model and the agent version stay in their existing top-level keys.
- **R2** — The system SHALL accept in a variant manifest a `harness.version` string naming the installed harness release and a `harness.upstream` source (`pypi:<name>`, `npm:<name>`, `github-release:<owner>/<repo>` or `github-commit:<owner>/<repo>`), and `Variant.load` SHALL require both for every variant that declares a plugin or an `init` step.
- **R3** — IF the installed Harbor version or any round variant's `harness.version` differs from the round's `pins`, or a pin names a variant outside the round, THEN `Round.load` SHALL refuse the round and list every mismatch.
- **R4** — WHEN `owl report` writes a round report, the system SHALL print the round id from `round.yaml`, the `cutoff_date` and every pin in the header, and SHALL NOT hard-code a round id in any report text.

### Freshness
- **R5** — WHEN the user runs `owl pins --round <dir>`, the system SHALL print, for Harbor, the agent version and each harness pin, the pinned value, the latest stable upstream release and its date, and SHALL mark the pins whose upstream major version differs or whose latest release is newer than the pin.
- **R6** — IF an upstream source cannot be reached, THEN `owl pins` SHALL print that pin as unknown and exit 0, without failing the other pins.

### Holdout reuse
- **R7** — The system SHALL keep a registry of revealed holdout tasks at `holdout/burned.yaml`, one entry per task with the round id and the reveal date, written without reading any holdout content.
- **R8** — IF a round is planned with `--holdout` and includes a task listed in `holdout/burned.yaml`, THEN owl SHALL refuse to plan the round and name the burned tasks.

### Refresh procedure
- **R9** — The repository SHALL document in `docs/round-protocol.md` the ordered refresh procedure of a round (cutoff, pins, re-spike, prefix audit, price validation, pilot, smoke, holdout sync and validation, pre-registration) as a table of triggers to required steps, where a major-version change of a harness requires a new spike and a new prefix audit, a model change requires a price validation and a pilot, any `lib.sh` or prefix change requires the holdout sync and `owl validate --suite --holdout`, and any pin change requires the smoke.
- **R10** — IF a pin changes after the round's `cutoff_date`, THEN the procedure SHALL require recording the reason in `RULES.md` and repeating every step its trigger requires before the next trial.
