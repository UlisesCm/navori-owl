"""Pin freshness for a round: pinned value against the latest stable upstream release.

Design: specs/round-protocol/design.md (P1, P5). Informational only: it never runs during a round,
never changes a pin and always exits 0. Every upstream lookup goes through one injectable fetcher so
tests never touch the network.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from owl.variants import Variant

Fetcher = Callable[[str], Any]

# Upstream of each agent's CLI, for the round's agent_version (P1).
AGENT_UPSTREAM = {"claude-code": "npm:@anthropic-ai/claude-code", "codex": "npm:@openai/codex"}

_STABLE_RE = re.compile(r"^v?\d+(?:\.\d+)*$")
_TIMEOUT_S = 10


def http_json(url: str) -> Any:
    """Default fetcher: GET ``url`` and parse JSON, with a short timeout per source."""
    request = urllib.request.Request(url, headers={"User-Agent": "navori-owl", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        return json.load(response)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split("."))


def latest(source: str, fetch: Fetcher) -> tuple[str, str] | None:
    """(version, YYYY-MM-DD) of the newest stable release of ``source``; None when unknown."""
    kind, _, name = source.partition(":")
    try:
        if kind == "pypi":
            releases = fetch(f"https://pypi.org/pypi/{name}/json")["releases"]
            stable = [v for v, files in releases.items() if files and _STABLE_RE.match(v)]
            best = max(stable, key=_version_key)
            return best, releases[best][0]["upload_time"][:10]
        if kind == "npm":
            data = fetch(f"https://registry.npmjs.org/{name}")
            best = data["dist-tags"]["latest"]
            return (best, data["time"][best][:10]) if _STABLE_RE.match(best) else None
        if kind == "github-release":
            data = fetch(f"https://api.github.com/repos/{name}/releases/latest")
            return data["tag_name"], data["published_at"][:10]
        if kind == "github-commit":
            data = fetch(f"https://api.github.com/repos/{name}/commits?per_page=1")[0]
            return data["sha"][:8], data["commit"]["committer"]["date"][:10]
    except Exception:  # noqa: BLE001 (R6: any failure of one source is "unknown", never fatal)
        return None
    return None


def _mark(source: str, pinned: str, newest: str | None) -> str:
    if newest is None:
        return "unknown"
    if source.startswith("github-commit:"):
        pinned_sha = pinned.rpartition("@")[2]  # "main@09c434ab" -> "09c434ab"
        same = pinned_sha.startswith(newest) or newest.startswith(pinned_sha)
        return "" if same else "newer"
    core = pinned.partition("@")[0]
    if core.lstrip("v") == newest.lstrip("v"):
        return ""
    try:
        major = _version_key(core)[0] != _version_key(newest)[0]
    except ValueError:
        major = False
    return "major" if major else "newer"


def pin_rows(round_dir: Path | str, fetch: Fetcher | None = None) -> list[dict[str, str]]:
    """One row per pin of ``round_dir/round.yaml``: Harbor, the agent version and each harness."""
    fetch = fetch or http_json
    data = yaml.safe_load((Path(round_dir) / "round.yaml").read_text()) or {}
    pins = data.get("pins") or {}
    variants = [Variant.load(str(v)) for v in data.get("variants") or []]
    wanted: list[tuple[str, str, str]] = []
    if "harbor" in pins:
        wanted.append(("harbor", "pypi:harbor", str(pins["harbor"])))
    agent = variants[0].agent if variants else "claude-code"
    if "agent_version" in data and agent in AGENT_UPSTREAM:
        wanted.append(("agent", AGENT_UPSTREAM[agent], str(data["agent_version"])))
    variant_pins = pins.get("variants") or {}
    for variant in variants:
        if variant.upstream:
            wanted.append((variant.id, variant.upstream, str(variant_pins.get(variant.id, variant.version))))
    rows = []
    for name, source, pinned in wanted:
        found = latest(source, fetch)
        rows.append({
            "pin": name, "pinned": pinned, "latest": found[0] if found else "?",
            "date": found[1] if found else "?", "mark": _mark(source, pinned, found[0] if found else None),
        })
    return rows


def render(rows: list[dict[str, str]]) -> str:
    """Fixed-width table, header first."""
    keys = ("pin", "pinned", "latest", "date", "mark")
    widths = {k: max(len(k), *(len(r[k]) for r in rows)) for k in keys}
    lines = ["  ".join(k.ljust(widths[k]) for k in keys).rstrip()]
    lines += ["  ".join(r[k].ljust(widths[k]) for k in keys).rstrip() for r in rows]
    return "\n".join(lines)
