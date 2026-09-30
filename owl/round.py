"""Round definition: load and validate `rounds/<id>/round.yaml`, check the tree, build the round record."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from owl.variants import ROOT, Variant

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
        )


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
