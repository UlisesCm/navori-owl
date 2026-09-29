"""``owl summary``: task x variant table over gate-``ok`` trials (R16, R17).

Design: specs/f2-suite-v1/design.md, D12. Only trials the gate leaves in ``ok`` count toward
``n_valid``/``successes``; the rest are counted per category (never silently dropped, never a
defeat). A cell is flagged ``review`` when successes are 0 or n_valid (0/k or k/k): the pilot's
"this task may not discriminate" mark.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from owl.gate import TrialGate, check_jobs
from owl.tasks import HOLDOUT_DIR, exit_refused, is_holdout


@dataclass
class Cell:
    task: str
    variant: str
    n_valid: int = 0
    successes: int = 0
    flag: str | None = None  # "0/k" | "k/k" | None
    mean_cost_usd: float | None = None
    mean_turns: float | None = None
    dims: dict[str, float] = field(default_factory=dict)
    excluded: dict[str, int] = field(default_factory=dict)  # category -> count


def _task_name(gate: TrialGate) -> str:
    """Task of a trial: its config's task dir name, else the ``stamp__task__variant__rN`` job name."""
    if gate.task_path:
        return Path(gate.task_path).name
    parts = gate.trial.split("__")
    return parts[1] if len(parts) >= 4 else gate.trial


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _number(value: object) -> float | None:
    """`value` as a number, or None (bools are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _exclusion(gate: TrialGate) -> str | None:
    """Category a trial is excluded under, or None when it is a valid trial.

    Fail-closed: a gate-``ok`` trial without a numeric ``reward`` has no verdict, so it is
    excluded as ``infra`` instead of being counted as a defeat.
    """
    if not gate.passed:
        return gate.category
    if _number((gate.reward or {}).get("reward")) is None:
        return "infra"
    return None


def summarize(gates: list[TrialGate]) -> list[Cell]:
    """Aggregate gated trials into one `Cell` per (task, variant), sorted by task then variant."""
    groups: dict[tuple[str, str], list[TrialGate]] = defaultdict(list)
    for gate in gates:
        groups[(_task_name(gate), gate.variant)].append(gate)

    cells = []
    for (task, variant), members in sorted(groups.items()):
        cell = Cell(task=task, variant=variant)
        valid = []
        for gate in members:
            category = _exclusion(gate)
            if category is None:
                valid.append(gate)
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
        cells.append(cell)
    return cells


def format_table(cells: list[Cell]) -> str:
    """Plain aligned table, one row per cell."""
    rows = [("task", "variant", "ok", "flag", "cost", "turns", "excluded")]
    for c in cells:
        excluded = ",".join(f"{k}:{v}" for k, v in sorted(c.excluded.items())) or "-"
        rows.append((
            c.task, c.variant, f"{c.successes}/{c.n_valid}", f"review ({c.flag})" if c.flag else "-",
            f"${c.mean_cost_usd:.4f}" if c.mean_cost_usd is not None else "-",
            f"{c.mean_turns:.1f}" if c.mean_turns is not None else "-", excluded,
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip() for r in rows)


def _holdout_ref(gate: TrialGate) -> str | None:
    """What to list when `gate` must be refused without ``--holdout``, else None (R15, fail closed).

    A trial whose task path is unreadable can't be checked with `is_holdout`, so it is refused as
    ``unresolved: <trial>``. The exception is a job with no trial at all (harbor failed before
    producing one): it holds no results, so its task is resolved from the job name instead.
    """
    if gate.task_path:
        return gate.task_path if is_holdout(Path(gate.task_path)) else None
    if gate.reasons and gate.reasons[0].startswith("no trial:"):
        candidate = HOLDOUT_DIR / _task_name(gate)
        return str(candidate) if candidate.is_dir() else None
    return f"unresolved: {gate.trial}"


def cmd_summary(args: argparse.Namespace) -> int:
    gates: list[TrialGate] = []
    for jobs_dir in args.jobs_dir:
        gates += check_jobs(Path(jobs_dir).resolve())
    if not gates:
        print("No owl trials found under: " + ", ".join(args.jobs_dir))
        return 1
    held = sorted({p for g in gates if (p := _holdout_ref(g)) is not None})
    if held and not args.holdout:
        # R15: same whole-call refusal as `owl run`/`owl validate`; holdout results stay unread.
        exit_refused("summarize", held)
    cells = summarize(gates)
    print(format_table(cells))
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(c) for c in cells], indent=2))
    return 0
