"""Variant manifests: load them and materialize their harness sources locally."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
VARIANTS_DIR = ROOT / "variants"
CACHE_DIR = ROOT / ".owl-cache"
PATIENT_DIR = ROOT / "patient"

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _check_artifact_prefix(variant_id: str, prefix: str) -> None:
    """R8: an artifact prefix ends in `/`, lies outside `packages/` and covers no patient file.

    The last rule keeps the exemption from ever hiding an edit to the patient's code or docs.
    """
    problem = None
    if not prefix.endswith("/"):
        problem = "does not end in '/'"
    elif prefix.startswith("packages/"):
        problem = "is under packages/"
    else:
        under = PATIENT_DIR / prefix
        if under.is_file() or (under.is_dir() and any(p.is_file() for p in under.rglob("*"))):
            problem = "contains a file of patient/"
    if problem:
        raise SystemExit(f"Variant '{variant_id}': artifacts prefix '{prefix}' {problem}.")


@dataclass
class Plugin:
    name: str
    git: str
    ref: str


@dataclass
class Variant:
    id: str
    description: str
    agent: str
    agent_version: str | None
    plugins: list[Plugin] = field(default_factory=list)
    init: str | None = None
    bare: bool = False
    runtime_state: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    append_system_prompt: str | None = None
    artifacts: list[str] = field(default_factory=list)
    expect: dict[str, list[str]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, variant_id: str) -> Variant:
        path = VARIANTS_DIR / f"{variant_id}.yaml"
        if not path.is_file():
            known = ", ".join(sorted(p.stem for p in VARIANTS_DIR.glob("*.yaml")))
            raise SystemExit(f"Unknown variant '{variant_id}'. Known: {known}")
        data = yaml.safe_load(path.read_text())
        harness = data.get("harness") or {}
        plugins = [Plugin(**p) for p in harness.get("plugins") or []]
        for plugin in plugins:
            if not _FULL_SHA_RE.match(plugin.ref):
                raise SystemExit(
                    f"Variant '{variant_id}', plugin '{plugin.name}': ref '{plugin.ref}' is not "
                    f"a full 40-char lowercase hex commit SHA. Pin plugins to a commit, not a branch/tag."
                )
        artifacts = [str(p) for p in (harness.get("artifacts") or [])]
        for prefix in artifacts:
            _check_artifact_prefix(variant_id, prefix)
        append_prompt = harness.get("append_system_prompt")
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            agent=data.get("agent", "claude-code"),
            agent_version=data.get("agent_version"),
            plugins=plugins,
            init=harness.get("init"),
            bare=bool(harness.get("bare", False)),
            runtime_state=[str(p) for p in (harness.get("runtime_state") or [])],
            env={k: str(v) for k, v in (harness.get("env") or {}).items()},
            append_system_prompt=str(append_prompt) if append_prompt is not None else None,
            artifacts=artifacts,
            expect={k: list(v or []) for k, v in (data.get("expect") or {}).items()},
            raw=data,
        )

    def materialize_plugins(self) -> list[Path]:
        """Clone each plugin at its pinned ref into the local cache and return the paths."""
        paths = []
        for plugin in self.plugins:
            target = CACHE_DIR / "plugins" / f"{plugin.name}@{plugin.ref}" / plugin.name
            if not target.is_dir():
                partial = target.with_name(target.name + ".partial")
                if partial.exists():
                    shutil.rmtree(partial)
                partial.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["git", "clone", "-q", plugin.git, str(partial)], check=True)
                subprocess.run(["git", "-C", str(partial), "checkout", "-q", plugin.ref], check=True)
                partial.rename(target)
            paths.append(target)
        return paths
