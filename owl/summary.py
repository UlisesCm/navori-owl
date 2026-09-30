"""``owl summary``: task x variant table over gate-``ok`` trials (R16, R17).

Design: specs/f2-suite-v1/design.md, D12. Only trials the gate leaves in ``ok`` count toward
``n_valid``/``successes``; the rest are counted per category (never silently dropped, never a
defeat). A cell is flagged ``review`` when successes are 0 or n_valid (0/k or k/k): the pilot's
"this task may not discriminate" mark.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from owl.gate import TrialGate, _task_path, check_jobs
from owl.tasks import HOLDOUT_DIR, TaskInfo, exit_refused, is_holdout


@dataclass
class Cell:
    task: str
    variant: str
    n_valid: int = 0
    successes: int = 0
    flag: str | None = None  # "0/k" | "k/k" | None
    mean_cost_usd: float | None = None
    mean_turns: float | None = None
    dims: dict[str, float | None] = field(default_factory=dict)  # None = n/a (not in the task's reward)
    excluded: dict[str, int] = field(default_factory=dict)  # category -> count
    tampered: int = 0  # kept trials whose baseline the agent moved: failures, listed apart (D11)


def task_name(gate: TrialGate) -> str:
    """Task of a trial: its config's task dir name, else the ``stamp__task__variant__rN`` job name."""
    if gate.task_path:
        return Path(gate.task_path).name
    return _task_of_job_name(gate.trial)


def _task_of_job_name(name: str) -> str:
    """Task segment of a ``stamp__task__variant__rN`` name, else the name itself."""
    parts = name.split("__")
    return parts[1] if len(parts) >= 4 else name


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _number(value: object) -> float | None:
    """`value` as a number, or None (bools are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


# Reason owl/gate.py records for ``baseline_valid = 0``.
_BASELINE_REASON = "baseline moved or missing"


def is_tampered(gate: TrialGate) -> bool:
    """D11: ``baseline_valid = 0`` on a trial with a result event and no other reason.

    Only the agent moves the baseline, so the trial stays a failure instead of being excluded.
    """
    return (
        not gate.passed
        and gate.category == "contamination"
        and gate.reasons == [_BASELINE_REASON]
        and (gate.reward or {}).get("baseline_valid") == 0
        and gate.result_event
    )


def exclusion(gate: TrialGate) -> str | None:
    """Category a trial is excluded under, or None when it is a kept trial (R22).

    ``infra`` and ``contamination`` are excluded, except a ``tampered`` trial (`is_tampered`), which is
    kept as a failure. Fail-closed: a kept trial without a numeric ``reward`` has no verdict, so it is
    excluded as ``infra`` instead of being counted as a defeat.
    """
    if not gate.passed and not is_tampered(gate):
        return gate.category
    if _number((gate.reward or {}).get("reward")) is None:
        return "infra"
    return None


def task_info(gate: TrialGate) -> TaskInfo | None:
    """The trial's task metadata (``owl_reward`` ...), or None when its ``task.toml`` is unreadable."""
    if not gate.task_path:
        return None
    try:
        return TaskInfo.load(Path(gate.task_path))
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return None


def summarize(gates: list[TrialGate]) -> list[Cell]:
    """Aggregate gated trials into one `Cell` per (task, variant), sorted by task then variant."""
    groups: dict[tuple[str, str], list[TrialGate]] = defaultdict(list)
    for gate in gates:
        groups[(task_name(gate), gate.variant)].append(gate)

    cells = []
    for (task, variant), members in sorted(groups.items()):
        cell = Cell(task=task, variant=variant)
        valid = []
        for gate in members:
            category = exclusion(gate)
            if category is None:
                valid.append(gate)
                cell.tampered += is_tampered(gate)
            else:
                cell.excluded[category] = cell.excluded.get(category, 0) + 1
        cell.n_valid = len(valid)
        cell.successes = sum((g.reward or {}).get("reward") == 1 for g in valid)
        if valid and cell.successes in (0, cell.n_valid):
            cell.flag = "0/k" if cell.successes == 0 else "k/k"
        cell.mean_cost_usd = _mean([g.cost_usd for g in valid if g.cost_usd is not None])
        cell.mean_turns = _mean([g.num_turns for g in valid if g.num_turns is not None])
        dim_values: dict[str, list[float]] = defaultdict(list)
        for gate in valid:
            for key, value in (gate.reward or {}).items():
                number = _number(value)
                if key != "reward" and number is not None:
                    dim_values[key].append(number)
        cell.dims = {k: sum(v) / len(v) for k, v in sorted(dim_values.items())}
        info = task_info(members[0])
        if info and "f2p" in cell.dims and "f2p" not in info.owl_reward:
            cell.dims["f2p"] = None  # pilot adjustment 6: f2p is 0, not failed, when the task has none
        cells.append(cell)
    return cells


def format_f2p(cell: Cell) -> str:
    """Mean f2p of the cell: ``n/a`` when it is not part of the task's reward, ``-`` when unmeasured."""
    if "f2p" not in cell.dims:
        return "-"
    return "n/a" if cell.dims["f2p"] is None else f"{cell.dims['f2p']:.2f}"


def format_table(cells: list[Cell]) -> str:
    """Plain aligned table, one row per cell."""
    rows = [("task", "variant", "ok", "flag", "cost", "turns", "f2p", "excluded")]
    for c in cells:
        excluded = ",".join([f"{k}:{v}" for k, v in sorted(c.excluded.items())] + ([f"tampered(kept):{c.tampered}"] if c.tampered else [])) or "-"
        rows.append((
            c.task, c.variant, f"{c.successes}/{c.n_valid}", f"review ({c.flag})" if c.flag else "-",
            f"${c.mean_cost_usd:.4f}" if c.mean_cost_usd is not None else "-",
            f"{c.mean_turns:.1f}" if c.mean_turns is not None else "-", format_f2p(c), excluded,
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip() for r in rows)


def _holdout_ref_of(task_path: str | None, trial: str, no_trial: bool) -> str | None:
    """What to list when a trial must be refused without ``--holdout``, else None (R15, fail closed).

    A trial whose task path is unreadable can't be checked with `is_holdout`, so it is refused as
    ``unresolved: <trial>``. The exception is a job with no trial at all (harbor failed before
    producing one): it holds no results, so its task is resolved from the job name instead.
    """
    if task_path:
        return task_path if is_holdout(Path(task_path)) else None
    if no_trial:
        candidate = HOLDOUT_DIR / _task_of_job_name(trial)
        return str(candidate) if candidate.is_dir() else None
    return f"unresolved: {trial}"


def holdout_ref(gate: TrialGate) -> str | None:
    """`_holdout_ref_of` for an already gated trial."""
    return _holdout_ref_of(gate.task_path, gate.trial, bool(gate.reasons) and gate.reasons[0].startswith("no trial:"))


def held_jobs(jobs_dir: Path) -> list[str]:
    """Holdout refs among the jobs of ``jobs_dir``, from each trial's ``config.json`` alone.

    Runs before any trial log is gated, so a refused call never reads holdout results (R15, R36).
    """
    refs: set[str] = set()
    for manifest in sorted(jobs_dir.glob("*/owl-variant.json")):
        job = manifest.parent
        trial_dirs = [p for p in sorted(job.iterdir()) if (p / "config.json").is_file()]
        if not trial_dirs:
            ref = _holdout_ref_of(None, job.name, True)
            refs.update([ref] if ref else [])
        for trial_dir in trial_dirs:
            ref = _holdout_ref_of(_task_path(trial_dir), trial_dir.name, False)
            refs.update([ref] if ref else [])
    return sorted(refs)


def cmd_summary(args: argparse.Namespace) -> int:
    jobs_dirs = [Path(d).resolve() for d in args.jobs_dir]
    held = sorted({ref for d in jobs_dirs for ref in held_jobs(d)})
    if held and not args.holdout:
        # R15: same whole-call refusal as `owl run`/`owl validate`, before any holdout log is read.
        exit_refused("summarize", held)
    gates = [g for d in jobs_dirs for g in check_jobs(d)]
    if not gates:
        print("No owl trials found under: " + ", ".join(args.jobs_dir))
        return 1
    cells = summarize(gates)
    print(format_table(cells))
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(c) for c in cells], indent=2))
    return 0
