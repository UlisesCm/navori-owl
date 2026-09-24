"""Task catalog: read a task's ``[metadata]``, decide if it's holdout, and list the suite.

Design: specs/f2-suite-v1/design.md, Components (``owl/tasks.py``) and D10 (holdout).
Requirements covered: R4, R5, R14, R15.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
HOLDOUT_DIR = ROOT / "holdout"

#: R5 categories a suite task's ``owl_type`` must be one of (design.md Catálogo de tareas /
#: Contracts `task.toml [metadata]`). "smoke" and "infra-probe" are valid `owl_type` values
#: for non-suite fixtures (tasks/00-smoke, tasks/01-probe) but never count toward R4/R5.
SUITE_CATEGORIES = frozenset(
    {
        "trivial",
        "bugfix-seeded",
        "bugfix-accidental",
        "feature-cross-package",
        "refactor-invariant",
        "security",
        "tooling",
        "test-repro",
        "behavior",
        "overengineering-trap",
        "hidden-root-cause",
    }
)
NON_SUITE_TYPES = frozenset({"smoke", "infra-probe"})


@dataclass
class TaskInfo:
    """The ``[metadata]`` block of a task's ``task.toml`` (Contracts, design.md)."""

    path: Path
    owl_type: str
    owl_dimensions: list[str] = field(default_factory=list)
    owl_reward: list[str] = field(default_factory=list)
    owl_holdout: bool = False
    owl_target_dimension: str | None = None
    owl_promise: str = ""
    owl_notes: str = ""

    @classmethod
    def load(cls, path: Path) -> TaskInfo:
        """Read ``<path>/task.toml``'s ``[metadata]`` table. Raises FileNotFoundError if the
        task.toml is missing (a caller asking for a task's info on a non-task directory)."""
        path = Path(path)
        toml_path = path / "task.toml"
        if not toml_path.is_file():
            raise FileNotFoundError(f"not a task directory (no task.toml): {path}")
        data = tomllib.loads(toml_path.read_text())
        meta = data.get("metadata", {})
        return cls(
            path=path,
            owl_type=str(meta.get("owl_type", "")),
            owl_dimensions=[str(d) for d in meta.get("owl_dimensions", [])],
            owl_reward=[str(d) for d in meta.get("owl_reward", [])],
            owl_holdout=bool(meta.get("owl_holdout", False)),
            owl_target_dimension=meta.get("owl_target_dimension"),
            owl_promise=str(meta.get("owl_promise", "")),
            owl_notes=str(meta.get("owl_notes", "")),
        )


def _by_path_signal(path: Path) -> bool:
    """True if ``path`` lives under a ``holdout/`` directory (any ancestor named ``holdout``)."""
    return "holdout" in Path(path).resolve().parts


def holdout_signals(path: Path) -> tuple[bool, bool]:
    """The two independent holdout signals (D10): ``(by_path, by_metadata)``.

    Used both by `is_holdout` (fails closed: either signal is enough) and by `owl validate`'s
    static "holdout coherence" check, which flags when they disagree instead of silently
    picking one.
    """
    by_path = _by_path_signal(path)
    try:
        by_metadata = TaskInfo.load(path).owl_holdout
    except FileNotFoundError:
        by_metadata = False
    return by_path, by_metadata


def is_holdout(path: Path) -> bool:
    """A task counts as holdout if *either* signal says so (D10: "falla cerrado").

    Guards (`owl run`, `owl validate`) call this before launching anything; a task whose
    path and metadata disagree is still refused without ``--holdout``, and the disagreement
    itself is a separate static-check failure (`holdout_signals`), never a silent pass.
    """
    by_path, by_metadata = holdout_signals(path)
    return by_path or by_metadata


def refuse_holdout(tasks: list[Path], allowed: bool) -> list[Path]:
    """Return the subset of `tasks` that must be refused (R15).

    ``allowed`` is the caller's ``--holdout`` flag: when True nothing is refused; when False,
    every holdout task in `tasks` comes back so the caller can reject the whole run (exit 2)
    instead of silently dropping just those tasks.
    """
    if allowed:
        return []
    return [t for t in tasks if is_holdout(t)]


def resolve_task_args(task: list[str] | None, suite: bool, holdout: bool) -> list[Path]:
    """Shared CLI resolution for `-t/--task` vs `--suite`, plus the R15 refuse-holdout guard.

    Used by both `owl run` and `owl validate` (D9/D10 share the same guard). Raises
    SystemExit on misuse (neither `-t` nor `--suite`) or when a holdout task would run
    without `--holdout` — the whole call is refused, not just the offending task.
    """
    if suite:
        task_paths = suite_tasks(include_holdout=holdout)
        if not task_paths:
            raise SystemExit("--suite: no suite tasks found under tasks/ (or holdout/ with --holdout).")
    elif task:
        task_paths = [Path(t).resolve() for t in task]
    else:
        raise SystemExit("pass -t/--task at least once, or --suite.")

    refused = refuse_holdout(task_paths, allowed=holdout)
    if refused:
        names = ", ".join(str(t) for t in refused)
        raise SystemExit(f"Refusing to run holdout task(s) without --holdout: {names}")
    return task_paths


def suite_tasks(include_holdout: bool = False) -> list[Path]:
    """List suite task directories under `tasks/` (and `holdout/` when `include_holdout`).

    Excludes non-suite fixtures (`owl_type` in `NON_SUITE_TYPES`, e.g. tasks/00-smoke,
    tasks/01-probe) and any directory without a `task.toml`. Sorted for reproducibility.
    """
    bases = [(TASKS_DIR, False)]
    if include_holdout:
        bases.append((HOLDOUT_DIR, True))

    found: list[Path] = []
    for base, _ in bases:
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or not (child / "task.toml").is_file():
                continue
            info = TaskInfo.load(child)
            if info.owl_type in NON_SUITE_TYPES:
                continue
            found.append(child)
    return found
