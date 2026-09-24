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

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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
    env: dict[str, str] = field(default_factory=dict)
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
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            agent=data.get("agent", "claude-code"),
            agent_version=data.get("agent_version"),
            plugins=plugins,
            init=harness.get("init"),
            bare=bool(harness.get("bare", False)),
            env={k: str(v) for k, v in (harness.get("env") or {}).items()},
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
