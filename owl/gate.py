"""Contamination gate: prove each trial loaded exactly what its variant declared.

Reads the Claude Code stream-json log of every trial (``agent/claude-code.txt``) and checks:
- ``system/init``: loaded plugins and MCP servers match the manifest's ``expect`` block.
- the run reached the model: a ``result`` event exists, is not an error, and used tokens.
- for the isolation probe task: the oracle directory was not visible to the agent.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TrialGate:
    trial: str
    variant: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    num_turns: int | None = None
    reward: dict | None = None


def _events(log: Path) -> list[dict]:
    events = []
    for line in log.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def check_trial(trial_dir: Path, variant: dict) -> TrialGate:
    gate = TrialGate(trial=trial_dir.name, variant=variant["id"], passed=True)
    reward_file = trial_dir / "verifier" / "reward.json"
    if reward_file.is_file():
        gate.reward = json.loads(reward_file.read_text())

    log = trial_dir / "agent" / "claude-code.txt"
    if not log.is_file():
        gate.passed = False
        gate.reasons.append("no claude-code.txt: agent never started")
        return gate

    events = _events(log)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)

    if init is None:
        gate.passed = False
        gate.reasons.append("no system/init event")
    else:
        gate.plugins = sorted(p.get("name", "?") for p in init.get("plugins") or [])
        mcp_servers = init.get("mcp_servers") or []
        gate.mcp_servers = sorted(s.get("name", "?") for s in mcp_servers)
        expect = variant.get("expect") or {}
        for key, actual in (("plugins", gate.plugins), ("mcp_servers", gate.mcp_servers)):
            wanted = sorted(expect.get(key) or [])
            if actual != wanted:
                gate.passed = False
                gate.reasons.append(f"{key}: expected {wanted}, loaded {actual}")
        for server in mcp_servers:
            status = server.get("status")
            if status != "connected":
                gate.passed = False
                gate.reasons.append(f"mcp server {server.get('name', '?')}: status {status}")
        for key in ("plugin_errors", "mcp_server_errors"):
            if init.get(key):
                gate.passed = False
                gate.reasons.append(f"{key}: {init[key]}")

    if result is None:
        gate.passed = False
        gate.reasons.append("no result event: run did not finish")
    else:
        gate.cost_usd = result.get("total_cost_usd")
        gate.num_turns = result.get("num_turns")
        usage = result.get("usage") or {}
        tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
        if result.get("is_error"):
            gate.passed = False
            gate.reasons.append(f"result is_error: {str(result.get('result'))[:160]}")
        if not tokens:
            gate.passed = False
            gate.reasons.append("zero tokens used: never reached the model")

    if gate.reward and gate.reward.get("solution_hidden") == 0:
        gate.passed = False
        gate.reasons.append("agent could see /solution")

    return gate


def check_jobs(jobs_dir: Path) -> list[TrialGate]:
    gates = []
    for manifest in sorted(jobs_dir.glob("*/owl-variant.json")):
        variant = json.loads(manifest.read_text())
        trial_dirs = sorted(p for p in manifest.parent.iterdir() if (p / "config.json").is_file())
        if not trial_dirs:
            code = variant.get("harbor_exit_code", "unknown")
            gates.append(
                TrialGate(
                    trial=manifest.parent.name,
                    variant=variant["id"],
                    passed=False,
                    reasons=[f"no trial: harbor exited with {code}"],
                )
            )
            continue
        for trial_dir in trial_dirs:
            gates.append(check_trial(trial_dir, variant))
    return gates


def write_report(gates: list[TrialGate], out: Path) -> None:
    out.write_text(json.dumps([asdict(g) for g in gates], indent=2))
