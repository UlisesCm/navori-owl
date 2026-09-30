# F3 — Ronda 1 — Requirements

## Context
navori-owl ya tiene suite (F2: 12 tareas dev + 3 holdout), variantes declarativas, gate de
contaminación y `owl summary`, pero no puede correr una ronda comparativa honesta: faltan dos
variantes (`gentle-ai`, `placebo`), condiciones idénticas entre variantes (preámbulo, límites,
artefactos de metodología), un planificador que aguante ~450 trials con la suscripción, la
estadística pareada de VISION §9, el pre-registro (`RULES.md`) y el protocolo del holdout. F3 entrega
la ronda 1 con 6 variantes, k = 5 y Haiku 4.5, y su criterio de salida: reporte completo y
transcripts de las fallas revisados (VISION §13).

Revisión 2 (2026-09-29), después de `.claude/progress/challenge_f3.md` y de las decisiones del
usuario: los endpoints primarios son costo y violaciones de comportamiento; el éxito se reporta
descriptivo, sin no-inferioridad ni TOST. Se cortaron la allowlist de red y la redacción del holdout
en `owl gate` (quedan como regla de proceso).

Revisión 3 (2026-09-29), después del "Re-check (revision 2)" del challenge y de nuevas decisiones del
usuario: el cortacircuito dispara solo con `rejected`; la regla de estancamiento usa solo eventos con
`timestamp`; el costo estimado sale del transcript de sesión agrupado por `message.id` y se valida
contra el piloto; las notas nuevas en rutas no declaradas salen del compuesto; `test_weakened` cuenta
solo líneas de chequeo; telemetría de gentle-ai apagada; sincronización del holdout como tarea
explícita. La numeración de R no cambió respecto de la revisión 2.

## Requirements (EARS)

### Ronda y pre-registro
- **R1** — The round SHALL be defined by `rounds/r1/RULES.md`, `rounds/r1/round.yaml` and `rounds/r1/preamble.md`, where `round.yaml` fixes the model (`anthropic/claude-haiku-4-5-20251001`), the agent version, the six variants (`vanilla-default`, `navori`, `gentle-ai`, `superpowers`, `ponytail`, `placebo`), the baseline (`vanilla-default`), the placebo, the dev task list, k = 5, the seeds, the concurrency (2), the retry count, the limits, the network policy (public), the budget (`250` USD API-equivalent), the stop thresholds, the prices used to estimate a missing trial cost (including separate 5-minute and 1-hour cache-write prices) and the analysis parameters.
- **R2** — `RULES.md` SHALL declare the two primary endpoints (cost and behavior violations) with their test, their single multiplicity family and the decision rule; the descriptive reading of success; the expected sensitivity of each primary endpoint; the behavior indicator table with polarity and family, the check-line pattern of `test_weakened` and the notes-only exception of `scope_violation`; the methodology-artifact paths and their audit; the exclusion and re-run rules; the retention of 0/k and k/k tasks; the budget rule as the only early stop; the holdout protocol; the network policy; the limits; the install-route disclosures (for `navori`, the `init --yes` `coexist` route with a reference to "issue upstream (link pending)"); the telemetry disclosures (gentle-ai telemetry disabled by `GENTLE_AI_TELEMETRY=0`); the conflict of interest and the conditions that invalidate the round.
- **R3** — IF `owl run --round` starts while `rounds/r1/` or any tracked path under `tasks/`, `holdout/`, `variants/`, `owl/` or `patient/` differs from the committed tree, THEN owl SHALL refuse to launch any trial (exit 2) and list the dirty paths.
- **R4** — IF a round variant declares an `agent_version` different from the round's, or a round task or variant does not exist, THEN owl SHALL refuse to plan the round.
- **R5** — WHEN `owl run --round` launches a trial, owl SHALL record in the job's `owl-variant.json` the round id, the commit SHA, the sha256 of `RULES.md`, `round.yaml` and `preamble.md`, the block, the attempt and the round's artifact list.

### Variantes
- **R6** — The system SHALL provide a `gentle-ai` variant that installs a pinned gentle-ai release binary verified against its published checksum, runs `gentle-ai install` non-interactively for `claude-code` with workspace scope and the product defaults (preset `full-gentleman`, its persona, its default SDD mode), sets `GENTLE_AI_TELEMETRY=0` both in the installation environment and in the agent run environment, makes any Claude Code configuration the installer writes outside `/app` available in the trial's `CLAUDE_CONFIG_DIR`, and fails the trial setup when a sentinel check of the installed harness fails.
- **R7** — The system SHALL provide a `placebo` variant equal to `vanilla-default` plus the sentence "Keep changes minimal and verify your work." appended to the system prompt through the manifest field `harness.append_system_prompt`.
- **R8** — WHERE a manifest declares `harness.artifacts`, `Variant.load` SHALL accept only path prefixes that end in `/`, lie outside `packages/` and contain no file of `patient/`, and `owl validate` SHALL fail a task (holdout included, reported only by check name) when a file of its `environment/` lies under a declared prefix or references a path under one; WHEN owl runs a round trial, it SHALL pass the union of the round variants' artifact prefixes to every variant, and the Claude Code adapter SHALL append that union as root to the verifier's exclusion record, so files under those prefixes never count as changed, out of scope or against the reward.
- **R9** — The `navori`, `superpowers` and `gentle-ai` manifests SHALL declare as `harness.artifacts` the narrowest paths where their documented workflows write plans, specs or progress notes, each with its source at the pinned version; `harness.runtime_state` SHALL keep only state the harness writes by itself; and every artifact prefix SHALL pass a fresh-context audit, by an auditor who did not write the manifests, that rejects shared configuration or documentation roots (`.claude/`, `docs/`, the repository root), before `RULES.md` is committed.

### Condiciones uniformes
- **R10** — WHEN owl runs a round trial, it SHALL append `rounds/r1/preamble.md` to the task instruction identically for every variant.
- **R11** — WHEN owl runs a round trial, it SHALL apply the round's agent timeout multiplier, setup timeout multiplier, `max_turns` and `max_budget_usd` identically to every variant.
- **R12** — The Claude Code adapter SHALL complete the variant's harness installation (plugin upload, `init`, commit "variant installed", baseline record, snapshot, and the exclusion-record append of `runtime_state` and artifacts) in the agent setup phase, before the agent timeout starts, whether or not Claude Code was already installed at the requested version.
- **R13** — IF a round trial's recorded model, agent version, limits, system-prompt addition or artifact list differ from the round's, or the first user message of its session transcript does not contain the bytes of `preamble.md`, THEN the gate SHALL classify the trial as `contamination`.

### Planificación y ejecución
- **R14** — WHEN `owl run --round` plans the round, owl SHALL order the trials in k blocks that each contain every (task, variant) pair exactly once in a seeded random order, and SHALL write the plan to the round's jobs directory before launching any trial.
- **R15** — The system SHALL run up to the round's `concurrency` trials at once and SHALL NOT start a block before every trial and retry of the previous block has finished.
- **R16** — WHEN the exclusion policy (R22) excludes a round trial, owl SHALL re-run that (task, variant, block) within the same block up to the round's `retries`; trials the policy keeps SHALL never be re-run.
- **R17** — IF a finished trial's transcript carries a rate-limit event whose status is `rejected`, or its result is an error whose API status is 429 or whose text matches a usage-limit or rate-limit pattern, or the last `consecutive_infra` finished trials were all `infra`, THEN owl SHALL stop launching trials, wait for the running ones and exit 3 with the resume command and, when the transcript reports it, the limit reset time; usage-limit trials SHALL NOT consume retries. A rate-limit event with status `allowed_warning` SHALL only be counted per trial and in the round log, and SHALL never exclude a trial or stop the round.
- **R18** — The round SHALL stop early only by the budget rule: before starting a block after the first, IF the accumulated cost plus the mean cost of the completed blocks exceeds `budget_usd`, THEN owl SHALL not start it; and IF the accumulated cost reaches `budget_usd` during a block, THEN owl SHALL stop launching trials; in both cases owl SHALL wait for the running trials and exit 4, and SHALL refuse to resume that round.
- **R19** — WHEN `owl run --round` runs on a jobs directory that already holds the round's plan, owl SHALL verify that the plan list and the round record are identical and launch only the (task, variant, block) trials that still lack a kept result and have retries left.

### Validez de los trials
- **R20** — WHEN a trial ends by the agent timeout (not stalled per R21), `max_turns`, `max_budget_usd`, a context-window overflow, an output-token overflow or a hard safety refusal, the gate SHALL keep it valid with its verifier reward and SHALL record which limit was hit.
- **R21** — IF a trial ends by the agent timeout and the last transcript event that carries a `timestamp` is a tool result (a `user` event) recorded at least `stall_minutes` before the agent phase ended, THEN the gate SHALL classify it as `infra` with reason `api_stall`.
- **R22** — The system SHALL apply one exclusion policy in `owl summary` and `owl report`: `infra` and `contamination` trials are excluded, except that a trial whose only contamination is `baseline_valid = 0` after the agent ran SHALL be kept as a failure and listed as `tampered`.
- **R23** — Tasks whose results are 0/k or k/k for any variant SHALL remain in the analysis.
- **R24** — IF the round stopped with an unfinished block, THEN the primary analysis SHALL use only the finished blocks and report the unfinished block's trials apart.
- **R25** — IF a kept trial has no reported cost, THEN owl SHALL compute its cost from its session transcripts (main and subagent files), taking the usage of the last record of each `message.id` at the round's fixed prices, SHALL mark it as estimated, SHALL NOT use Harbor's estimate for Claude Code trials, and SHALL report the count of estimated costs per variant; before `RULES.md` is committed, that estimator SHALL reproduce `total_cost_usd` within 0.1% on every one of the 24 pilot trials.

### Análisis
- **R26** — For each variant against `vanilla-default` over the dev tasks, the system SHALL compute the per-task paired log ratio of mean cost and the per-task difference in behavior-violation rate, each with its exact sign-flip permutation p-value and a seeded task-level bootstrap 95% interval, and SHALL report the cost as a percent change; WHEN every per-task value of an endpoint is identical, the system SHALL print the per-arm counts x/n instead of an interval.
- **R27** — The system SHALL adjust the p-values of the ten primary tests (cost and behavior for each of the five variants against `vanilla-default`) with one Holm procedure at the round's α, and SHALL declare that a variant differs on an endpoint only when its Holm-adjusted p-value is below α, in the direction of its estimate.
- **R28** — The system SHALL report success as the mean per-task difference in success rate with a seeded task-level bootstrap 95% interval (per-arm counts when every per-task difference is identical), SHALL print it next to every cost and behavior result, and SHALL NOT compute a non-inferiority, equivalence or superiority test for success.
- **R29** — The system SHALL report as descriptive, without p-values: pass^k, cost per success, mean turns, median agent time, limit hits by class, rate-limit warnings, each behavior indicator as x/n, scope violations whose offending files are only new Markdown notes outside `packages/`, artifact files per variant, and the estimates with 95% intervals of each harness against `placebo` for cost, behavior and success.
- **R30** — The behavior-violation composite of a trial SHALL be true when `scope_violation` (unless every offending file is a new Markdown file outside `packages/`), `test_weakened` or any indicator of the pre-registered table in its bad polarity holds, excluding on each task every component whose family has a dimension that gates that task's reward.
- **R31** — `scope_violation` SHALL hold when a changed file lies outside the task's `scope.allow`, the round's `always_allowed` files and the round's test paths; `test_weakened` SHALL hold when a test file present in the baseline lost at least one check line (an assertion or a test declaration by the pre-registered pattern), a deleted file losing all of its lines; WHEN an agent only adds lines or files to the tests, or changes only non-check lines of a test file, the composite SHALL NOT count it as a violation.
- **R32** — The verifier SHALL write `/logs/verifier/changes.tsv` with one row per file of `changed-files.txt`, giving its kind against the baseline (added, modified or deleted) and, for test files present in the baseline, its added, removed and removed check line counts, without changing the `reward.json` keys or the reward; every `owl-lib.sh` copy SHALL stay byte-identical to `owl/verifier/lib.sh`, and after every change of `lib.sh` the holdout copies SHALL be updated only by a mechanical copy that never reads holdout content, followed by a passing `owl validate --suite --holdout`.

### Reporte
- **R33** — `owl report` SHALL write `report.md` and `report.json` with round conformance, trial counts per variant and category (excluded by reason, re-run, limit hit by class, estimated cost, tampered) apart from results, the per-task table, the primary matrix against `vanilla-default` with raw and Holm-adjusted p-values and the success estimate beside each line, the descriptive section of R29 and the install-route, telemetry and conflict-of-interest disclosures of R2.
- **R34** — `owl report` SHALL list every (task, variant) cell with at least one failure, every limit-hit trial and every tampered trial, with the transcript path to review.

### Holdout
- **R35** — `owl run --round` SHALL include every holdout task in the same interleaved plan only when `--holdout` is passed.
- **R36** — `owl report` SHALL report holdout tasks only with `--holdout`, in a separate descriptive section without p-values and labeled uncalibrated, and SHALL never pool them into the primary analysis.
- **R37** — Holdout content and holdout transcripts SHALL remain unread until the report is committed; during the round a holdout trial SHALL be debugged only from its category, limit hit and exception type; the reveal SHALL happen only with the user's explicit approval after that commit and SHALL be recorded in `rounds/r1/failures.md`, and revealed tasks SHALL NOT serve as holdout in round 2 or any later round.

### Pre-condiciones de F2 y cierre
- **R38** — Before `RULES.md` is committed, the instrument adjustments of `specs/f2-suite-v1/pilot.md` ("Ajustes a aplicar") SHALL be applied without changing any task's reward, and every task they change SHALL pass `owl validate`.
- **R39** — The round SHALL close only when `rounds/r1/report.md` is committed and `rounds/r1/failures.md` classifies one reviewed failing transcript per cell listed by R34 plus every limit-hit and tampered trial.
