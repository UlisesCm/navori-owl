"""Round definition: load and validate `rounds/<id>/round.yaml`, check the tree, build the round record."""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from owl.tasks import HOLDOUT_DIR, exit_refused, refuse_holdout
from owl.variants import ROOT, Variant

LIMIT_KEYS = ("agent_timeout_multiplier", "agent_setup_timeout_multiplier", "max_turns", "max_budget_usd")
PRICE_KEYS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")
_ROUND_FILES = ("RULES.md", "round.yaml", "preamble.md")
_CLEAN_DIRS = ("tasks", "holdout", "variants", "owl", "patient")


@dataclass
class Round:
    id: str
    dir: Path
    model: str
    agent_version: str
    variants: list[str]
    baseline: str
    placebo: str
    tasks: list[str]
    prices_usd_per_mtok: dict[str, float]
    artifacts: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, round_dir: Path | str, root: Path = ROOT) -> Round:
        """Read and validate `round.yaml`; exit with a message on any inconsistency."""
        round_dir = Path(round_dir)
        path = round_dir / "round.yaml"
        if not path.is_file():
            raise SystemExit(f"Round file not found: {path}")
        data = yaml.safe_load(path.read_text()) or {}
        for key in ("id", "agent_version", "variants", "baseline", "placebo", "tasks"):
            if key not in data:
                raise SystemExit(f"{path}: missing required key '{key}'")
        agent_version = str(data["agent_version"])
        variant_ids = [str(v) for v in data["variants"]]
        for special in ("baseline", "placebo"):
            if data[special] not in variant_ids:
                raise SystemExit(f"{path}: {special} '{data[special]}' is not in variants")
        tasks = [str(t) for t in data["tasks"]]
        missing_tasks = [t for t in tasks if not (root / t).is_dir()]
        if missing_tasks:
            raise SystemExit(f"{path}: unknown task(s): {', '.join(missing_tasks)}")
        prices = data.get("prices_usd_per_mtok") or {}
        missing_prices = [k for k in PRICE_KEYS if k not in prices]
        if missing_prices:
            raise SystemExit(f"{path}: prices_usd_per_mtok is missing: {', '.join(missing_prices)}")
        for key, value in (
            ("concurrency", data.get("concurrency", 2)),
            ("stop.consecutive_infra", (data.get("stop") or {}).get("consecutive_infra", 3)),
        ):
            if int(value) < 1:
                raise SystemExit(f"{path}: {key} must be >= 1")

        limits = _validate_limits(path, data)
        artifacts: list[str] = []
        for vid in variant_ids:
            variant = Variant.load(vid)  # exits on an unknown variant
            if variant.agent_version != agent_version:
                raise SystemExit(
                    f"{path}: variant '{vid}' agent_version {variant.agent_version!r} "
                    f"differs from the round's {agent_version!r}"
                )
            for prefix in variant.artifacts:
                if prefix not in artifacts:
                    artifacts.append(prefix)
        return cls(
            id=str(data["id"]),
            dir=round_dir,
            model=str(data.get("model", "")),
            agent_version=agent_version,
            variants=variant_ids,
            baseline=str(data["baseline"]),
            placebo=str(data["placebo"]),
            tasks=tasks,
            prices_usd_per_mtok={k: float(v) for k, v in prices.items()},
            artifacts=artifacts,
            raw=data,
            limits=limits,
        )


def _validate_limits(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """The round's ``limits`` mapping with exactly the four LIMIT_KEYS, typed; exit otherwise (R11, R13)."""
    limits = data.get("limits")
    if not isinstance(limits, dict):
        stray = [k for k in LIMIT_KEYS if k in data]
        hint = f" (found at top level: {', '.join(stray)}; nest them under 'limits')" if stray else ""
        raise SystemExit(f"{path}: missing required mapping 'limits'{hint}")
    missing = [k for k in LIMIT_KEYS if k not in limits]
    extra = [k for k in limits if k not in LIMIT_KEYS]
    if missing or extra:
        raise SystemExit(
            f"{path}: limits must have exactly {', '.join(LIMIT_KEYS)}"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; unknown: {', '.join(map(str, extra))}" if extra else "")
        )

    def number(v: object) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0

    for key in ("agent_timeout_multiplier", "agent_setup_timeout_multiplier"):
        if not number(limits[key]):
            raise SystemExit(f"{path}: limits.{key} must be a number > 0")
    turns = limits["max_turns"]
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 1:
        raise SystemExit(f"{path}: limits.max_turns must be an integer >= 1")
    budget = limits["max_budget_usd"]
    try:
        ok = isinstance(budget, str) and Decimal(budget) > 0 and Decimal(budget).is_finite()
    except InvalidOperation:
        ok = False
    if not ok:
        raise SystemExit(f"{path}: limits.max_budget_usd must be a string parseable as a positive decimal (e.g. \"5.00\")")
    return dict(limits)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def dirty_paths(round_dir: Path | str, root: Path = ROOT) -> list[str]:
    """Paths under the round dir and the frozen trees that differ from HEAD (tracked only, per R3)."""
    round_rel = Path(round_dir).resolve().relative_to(root.resolve()).as_posix()
    out = _git(root, "status", "--porcelain", "-z", "-uno", "--", round_rel, *_CLEAN_DIRS)
    return sorted(entry[3:] for entry in out.split("\0") if len(entry) > 3)


def require_clean_tree(round_dir: Path | str, root: Path = ROOT) -> None:
    """Refuse to launch (exit 2) when any frozen path is dirty, listing the paths."""
    dirty = dirty_paths(round_dir, root)
    if dirty:
        print("Refusing to run: dirty paths:\n  " + "\n  ".join(dirty), file=sys.stderr)
        raise SystemExit(2)


def round_record(round_dir: Path | str, artifacts: list[str], root: Path = ROOT) -> dict[str, Any]:
    """Record for `owl-variant.json`: round id, commit and sha256 of RULES.md, round.yaml, preamble.md."""
    round_dir = Path(round_dir)
    sha = {
        Path(name).stem.lower(): hashlib.sha256((round_dir / name).read_bytes()).hexdigest()
        for name in _ROUND_FILES
    }
    data = yaml.safe_load((round_dir / "round.yaml").read_text())
    return {
        "id": str(data["id"]),
        "commit": _git(root, "rev-parse", "HEAD").strip(),
        "sha256": {"rules": sha["rules"], "round": sha["round"], "preamble": sha["preamble"]},
        "artifacts": list(artifacts),
    }


def round_jobs_dir(round_def: Round, root: Path = ROOT) -> Path:
    """Jobs directory of the round: ``jobs_dir`` of round.yaml, default ``jobs/<id>``."""
    return (root / round_def.raw.get("jobs_dir", f"jobs/{round_def.id}")).resolve()


def round_tasks(
    round_def: Round, holdout: bool, root: Path = ROOT, holdout_dir: Path = HOLDOUT_DIR
) -> list[str]:
    """The round's tasks (root-relative); every holdout task joins only with ``holdout`` (R35, F2 R15)."""
    refused = refuse_holdout([root / t for t in round_def.tasks], allowed=holdout)
    if refused:
        exit_refused("run", refused)
    tasks = list(round_def.tasks)
    if holdout:
        found = sorted(p.parent.relative_to(root).as_posix() for p in holdout_dir.glob("*/task.toml"))
        tasks += [t for t in found if t not in tasks]
    return tasks


def build_plan(
    round_def: Round, holdout: bool = False, root: Path = ROOT, holdout_dir: Path = HOLDOUT_DIR
) -> dict[str, Any]:
    """k blocks, each with every (task, variant) pair once in an order drawn from ``plan_seed`` (R14)."""
    raw = round_def.raw
    pairs = [(t, v) for t in round_tasks(round_def, holdout, root, holdout_dir) for v in round_def.variants]
    rng = random.Random(raw.get("plan_seed", 0))
    trials: list[dict[str, Any]] = []
    for block in range(1, int(raw.get("k", 1)) + 1):
        order = pairs[:]
        rng.shuffle(order)
        trials += [{"block": block, "task": t, "variant": v} for t, v in order]
    return {
        "round": round_record(round_def.dir, round_def.artifacts, root),
        "artifacts": list(round_def.artifacts),
        "trials": trials,
    }


def plan_round(
    round_def: Round, holdout: bool = False, root: Path = ROOT, holdout_dir: Path = HOLDOUT_DIR
) -> dict[str, Any]:
    """Build the plan and write it to ``<jobs_dir>/owl-plan.json`` before anything launches (R14)."""
    plan = build_plan(round_def, holdout, root, holdout_dir)
    jobs_dir = round_jobs_dir(round_def, root)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    (jobs_dir / "owl-plan.json").write_text(json.dumps(plan, indent=2))
    return plan
