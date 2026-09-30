"""``owl run --round``: execute a round's plan with bounded concurrency, in-block retries and stop rules.

Design: specs/f3-ronda1/design.md, D9 (R15-R19). The harbor subprocess is injected (``Launch``)
so tests run the whole executor without Harbor or a model.

Exit codes: 0 complete, 2 refusal, 3 usage limit or infra streak, 4 budget.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from owl.gate import TrialGate, check_job
from owl.round import Round, build_plan, plan_round, round_jobs_dir
from owl.summary import _exclusion
from owl.tasks import HOLDOUT_DIR
from owl.variants import ROOT, Variant

# Runs one trial (variant, task dir, job name) and returns the harbor exit code.
Launch = Callable[[Variant, Path, str], int]

EXIT_FAILED, EXIT_REFUSED, EXIT_STOPPED, EXIT_BUDGET = 1, 2, 3, 4
PLAN_FILE = "owl-plan.json"
BUDGET_MARKER = "owl-budget-stop.json"
ROUND_LOG = "owl-round.log"
_JOB_ATTEMPT = re.compile(r"b(\d+)-a(\d+)")

Key = tuple[str, str, int]  # (task name, variant, block)


@dataclass
class _Slot:
    """Progress of one (task, variant, block)."""

    launched: int = 0  # highest attempt number used (keeps job names unique)
    consumed: int = 0  # attempts the exclusion policy spent (usage_limit ones don't count)
    kept: bool = False


def _parse_job(name: str) -> tuple[Key, int] | None:
    """(key, attempt) from ``<round>-<stamp>__<task>__<variant>__b<block>-a<attempt>``, else None."""
    parts = name.split("__")
    match = _JOB_ATTEMPT.fullmatch(parts[3]) if len(parts) == 4 else None
    return ((parts[1], parts[2], int(match[1])), int(match[2])) if match else None


class _Executor:
    def __init__(
        self, round_def: Round, variants: dict[str, Variant], launch: Launch, plan: dict[str, Any],
        jobs_dir: Path, holdout: bool, root: Path,
    ) -> None:
        raw = round_def.raw
        self.round_def, self.variants, self.launch, self.plan = round_def, variants, launch, plan
        self.jobs_dir, self.holdout, self.root = jobs_dir, holdout, root
        self.concurrency = int(raw.get("concurrency", 2))
        self.max_attempts = 1 + int(raw.get("retries", 2))
        self.budget = float(raw["budget_usd"]) if "budget_usd" in raw else None
        streak = int((raw.get("stop") or {}).get("consecutive_infra", 3))
        self.recent: deque[bool] = deque(maxlen=streak)  # completion order: was the trial infra?
        self.slots: dict[Key, _Slot] = defaultdict(_Slot)
        self.block_cost: dict[int, float] = defaultdict(float)
        self.stop: int | None = None
        self.stop_message = ""
        self.resets_at: int | None = None

    def load_history(self) -> None:
        """Rebuild slots and costs from the jobs already on disk (resume, R19)."""
        for manifest in sorted(self.jobs_dir.glob("*/owl-variant.json")):
            parsed = _parse_job(manifest.parent.name)
            if parsed is not None:
                key, attempt = parsed
                self._record(key, attempt, check_job(manifest.parent, self.round_def)[0])

    def _record(self, key: Key, attempt: int, gate: TrialGate) -> None:
        slot = self.slots[key]
        slot.launched = max(slot.launched, attempt)
        self.block_cost[key[2]] += gate.cost_usd or 0.0
        if _exclusion(gate) is None:
            slot.kept = True
        elif gate.infra_reason != "usage_limit":
            slot.consumed += 1

    def _needs_run(self, key: Key) -> bool:
        slot = self.slots[key]
        return not slot.kept and slot.consumed < self.max_attempts

    def _halt(self, code: int, message: str) -> None:
        if self.stop is None or code == EXIT_BUDGET:  # the budget rule is final: it overrides any other stop
            self.stop, self.stop_message = code, message

    def _check_budget(self, gate: TrialGate | None = None) -> None:
        """Budget rule (R18). A kept trial with unknown cost fails closed: spend can't be tracked."""
        if self.budget is None:
            return
        spent = sum(self.block_cost.values())
        if gate is not None and gate.cost_usd is None and _exclusion(gate) is None:
            self._halt(EXIT_BUDGET, f"cost of a kept trial is unknown (${spent:.2f} known of ${self.budget:.2f})")
        elif spent >= self.budget:
            self._halt(EXIT_BUDGET, f"budget reached: ${spent:.2f} of ${self.budget:.2f}")

    def _run_trial(self, key: Key, attempt: int, task: str) -> TrialGate:
        task_name, variant_id, block = key
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        job_name = f"{self.round_def.id}-{stamp}__{task_name}__{variant_id}__b{block}-a{attempt}"
        variant = self.variants[variant_id]
        print(f"▶ {job_name}", flush=True)
        code = self.launch(variant, self.root / task, job_name)
        job_dir = self.jobs_dir / job_name
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "owl-variant.json").write_text(
            json.dumps(
                {
                    **variant.raw, "model": self.round_def.model,
                    "auth": self.round_def.raw.get("auth", "oauth"), "harbor_exit_code": code,
                    "round": self.plan["round"], "block": block, "attempt": attempt,
                    "artifacts": self.plan["artifacts"],
                },
                indent=2,
            )
        )
        gate = check_job(job_dir, self.round_def)[0]
        if gate.rate_limit_warnings:  # allowed_warning: logged, never a stop or an exclusion (R17)
            with (self.jobs_dir / ROUND_LOG).open("a") as log:
                log.write(f"{job_name} rate_limit_warnings={gate.rate_limit_warnings}\n")
        return gate

    def _finish(self, key: Key, attempt: int, gate: TrialGate) -> bool:
        """Account a finished trial, apply the stop rules; True when it must be retried (R16)."""
        self._record(key, attempt, gate)
        if gate.cost_usd is None and _exclusion(gate) is not None:  # counts 0 toward the budget
            with (self.jobs_dir / ROUND_LOG).open("a") as log:
                log.write(f"{gate.trial} b{key[2]}-a{attempt} cost unknown\n")
        category = _exclusion(gate)
        self.recent.append(category == "infra")
        if gate.infra_reason == "usage_limit":
            self.resets_at = gate.resets_at
            self._halt(EXIT_STOPPED, "usage limit reached")
        elif len(self.recent) == self.recent.maxlen and all(self.recent):
            self._halt(EXIT_STOPPED, f"last {self.recent.maxlen} finished trials were all infra")
        self._check_budget(gate)
        return self.stop is None and self._needs_run(key)

    def _run_block(self, pool: ThreadPoolExecutor, pending: deque[dict[str, Any]]) -> None:
        running: dict[Future[TrialGate], tuple[Key, int, dict[str, Any]]] = {}
        while True:
            while pending and self.stop is None and len(running) < self.concurrency:
                trial = pending.popleft()
                key = (Path(trial["task"]).name, trial["variant"], trial["block"])
                slot = self.slots[key]
                slot.launched += 1
                running[pool.submit(self._run_trial, key, slot.launched, trial["task"])] = (key, slot.launched, trial)
            if not running:
                return
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                key, attempt, trial = running.pop(future)
                try:
                    gate = future.result()
                except Exception as exc:  # noqa: BLE001 - drain the running trials instead of escaping mid-round
                    self._halt(EXIT_FAILED, f"launch failed: {exc!r}")
                    continue
                if self._finish(key, attempt, gate):
                    pending.append(trial)

    def run(self) -> int:
        blocks = sorted({t["block"] for t in self.plan["trials"]})
        self._check_budget()  # a resumed round already over budget launches nothing
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            for block in blocks:
                pending = deque(
                    t for t in self.plan["trials"]
                    if t["block"] == block and self._needs_run((Path(t["task"]).name, t["variant"], block))
                )
                if not pending:
                    continue
                if block > 1 and self.budget is not None:
                    spent = sum(self.block_cost.values())
                    mean = sum(self.block_cost[b] for b in range(1, block)) / (block - 1)
                    if spent + mean > self.budget:
                        self._halt(EXIT_BUDGET, f"block {block} would exceed the budget: "
                                                f"${spent:.2f} spent + ${mean:.2f} mean block > ${self.budget:.2f}")
                        break
                self._run_block(pool, pending)
                if self.stop is not None:
                    break
        return self._close()

    def _close(self) -> int:
        if self.stop is None:
            return 0
        print(f"Round stopped: {self.stop_message}", file=sys.stderr)
        if self.stop == EXIT_BUDGET:
            self.jobs_dir.mkdir(parents=True, exist_ok=True)
            (self.jobs_dir / BUDGET_MARKER).write_text(json.dumps({"reason": self.stop_message}, indent=2))
            print("This round will not resume.", file=sys.stderr)
        else:
            if self.resets_at is not None:
                reset = datetime.fromtimestamp(self.resets_at, UTC).isoformat()
                print(f"Limit resets at {reset} (resetsAt={self.resets_at})", file=sys.stderr)
            holdout = " --holdout" if self.holdout else ""
            print(f"Resume with: owl run --round {self.round_def.dir}{holdout}", file=sys.stderr)
        return self.stop


def execute_round(
    round_def: Round, variants: dict[str, Variant], launch: Launch, *, holdout: bool = False,
    root: Path = ROOT, holdout_dir: Path = HOLDOUT_DIR,
) -> int:
    """Run (or resume) the round's plan; returns the exit code (0, 2, 3 or 4)."""
    jobs_dir = round_jobs_dir(round_def, root)
    if (jobs_dir / BUDGET_MARKER).is_file():
        print(f"Refusing to resume: the round was stopped by the budget rule ({jobs_dir / BUDGET_MARKER}).",
              file=sys.stderr)
        return EXIT_REFUSED
    plan_file = jobs_dir / PLAN_FILE
    if plan_file.is_file():
        plan = build_plan(round_def, holdout, root, holdout_dir)
        if json.loads(plan_file.read_text()) != plan:
            print(f"Refusing to resume: the plan or round record differ from {plan_file}.", file=sys.stderr)
            return EXIT_REFUSED
    else:
        plan = plan_round(round_def, holdout, root, holdout_dir)
    executor = _Executor(round_def, variants, launch, plan, jobs_dir, holdout, root)
    executor.load_history()
    return executor.run()
