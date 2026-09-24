"""Contamination gate: prove each trial loaded exactly what its variant declared.

Dispatches by the variant's ``agent``:
- ``claude-code``: reads the stream-json log (``agent/claude-code.txt``) and checks
  ``system/init`` plugins/MCP servers against the manifest's ``expect`` block, plus a
  ``result`` event that is not an error and used tokens.
- ``codex``: reads the ``codex exec --json`` log (``agent/codex.txt``) and checks there is
  no ``error``/``turn.failed`` event and a ``turn.completed`` event that used tokens.
  Plugin/MCP ``expect`` is not verifiable from this log (Codex has no harness yet).

Both agents share:
- cost/tokens, read from the trial's Harbor ``result.json`` (``agent_result``) when present.
- for the isolation probe task: the oracle directory was not visible to the agent (``reward.json``).
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
    # "ok" (passed), "infra" (the agent/model was never reliably reached: no result event,
    # auth/API error, harbor exit without a trial, invalid reward.json), or "contamination"
    # (the trial ran but loaded something other than what the variant declared: expect
    # mismatch, an MCP not connected, plugin/mcp errors, /solution visible). If a trial hits
    # both, contamination wins: an infra hiccup doesn't excuse a contaminated run.
    category: str = "ok"
    plugins: list[str] = field(default_factory=list)
    builtin_plugins: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    num_turns: int | None = None
    reward: dict | None = None


def _fail(gate: TrialGate, reason: str, category: str) -> None:
    """Record a failure reason under a bucket; contamination is sticky (never downgraded)."""
    gate.passed = False
    gate.reasons.append(reason)
    if gate.category != "contamination":
        gate.category = category


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


def _check_claude_code(gate: TrialGate, trial_dir: Path, variant: dict) -> None:
    log = trial_dir / "agent" / "claude-code.txt"
    if not log.is_file():
        _fail(gate, "no claude-code.txt: agent never started", "infra")
        return

    events = _events(log)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)

    if init is None:
        _fail(gate, "no system/init event", "infra")
    else:
        all_plugins = init.get("plugins") or []
        # Plugins Claude Code ships internally (e.g. "agents-md") aren't harness contamination:
        # they load with path == "builtin" / source == "<name>@builtin" regardless of the variant.
        builtin = [p for p in all_plugins if p.get("path") == "builtin" or str(p.get("source", "")).endswith("@builtin")]
        loaded = [p for p in all_plugins if p not in builtin]
        gate.plugins = sorted(p.get("name", "?") for p in loaded)
        gate.builtin_plugins = sorted(p.get("name", "?") for p in builtin)
        mcp_servers = init.get("mcp_servers") or []
        gate.mcp_servers = sorted(s.get("name", "?") for s in mcp_servers)
        expect = variant.get("expect") or {}
        for key, actual in (("plugins", gate.plugins), ("mcp_servers", gate.mcp_servers)):
            wanted = sorted(expect.get(key) or [])
            if actual != wanted:
                _fail(gate, f"{key}: expected {wanted}, loaded {actual}", "contamination")
        for server in mcp_servers:
            status = server.get("status")
            if status != "connected":
                _fail(gate, f"mcp server {server.get('name', '?')}: status {status}", "contamination")
        for key in ("plugin_errors", "mcp_server_errors"):
            if init.get(key):
                _fail(gate, f"{key}: {init[key]}", "contamination")

    if result is None:
        _fail(gate, "no result event: run did not finish", "infra")
    else:
        gate.cost_usd = result.get("total_cost_usd")
        gate.num_turns = result.get("num_turns")
        usage = result.get("usage") or {}
        tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
        if result.get("is_error"):
            # is_error covers both transport/auth failures (401, rate limits, ...) and the
            # model genuinely erroring out mid-run; neither means the run loaded the wrong
            # harness, so it's infra, not contamination.
            _fail(gate, f"result is_error: {str(result.get('result'))[:160]}", "infra")
        if not tokens:
            _fail(gate, "zero tokens used: never reached the model", "infra")


def _check_codex(gate: TrialGate, trial_dir: Path, variant: dict) -> None:
    log = trial_dir / "agent" / "codex.txt"
    if not log.is_file():
        _fail(gate, "no codex.txt: agent never started", "infra")
        return

    expect = variant.get("expect") or {}
    if expect.get("plugins") or expect.get("mcp_servers"):
        _fail(gate, "plugins/mcp_servers expectation not verifiable for agent 'codex' (no harness yet)", "contamination")

    events = _events(log)
    errors = [e for e in events if e.get("type") in ("error", "turn.failed")]
    if errors:
        for error in errors:
            detail = error.get("error") or error.get("message") or error
            _fail(gate, f"{error.get('type')}: {str(detail)[:160]}", "infra")

    completed = [e for e in events if e.get("type") == "turn.completed"]
    if not completed:
        _fail(gate, "no turn.completed event: run did not finish", "infra")
        return

    gate.num_turns = len(completed)
    usage = completed[-1].get("usage") or {}
    tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
    if not tokens:
        _fail(gate, "zero tokens used: never reached the model", "infra")


_AGENT_CHECKS = {
    "claude-code": _check_claude_code,
    "codex": _check_codex,
}


def _overlay_cost_from_result_json(gate: TrialGate, trial_dir: Path) -> None:
    """Prefer Harbor's own token/cost accounting (``result.json``) when present.

    It's agent-agnostic and the source Harbor itself uses for its own reports, unlike the
    per-agent log which each agent formats differently (or not at all, for tokens/cost).
    """
    result_file = trial_dir / "result.json"
    if not result_file.is_file():
        return
    try:
        agent_result = json.loads(result_file.read_text()).get("agent_result") or {}
    except json.JSONDecodeError:
        return
    if agent_result.get("cost_usd") is not None:
        gate.cost_usd = agent_result["cost_usd"]


def check_trial(trial_dir: Path, variant: dict) -> TrialGate:
    gate = TrialGate(trial=trial_dir.name, variant=variant["id"], passed=True)
    reward_file = trial_dir / "verifier" / "reward.json"
    if reward_file.is_file():
        try:
            gate.reward = json.loads(reward_file.read_text())
        except json.JSONDecodeError:
            _fail(gate, "invalid reward.json", "infra")

    agent = variant.get("agent", "claude-code")
    check = _AGENT_CHECKS.get(agent)
    if check is None:
        _fail(gate, f"gate: agent '{agent}' not supported", "infra")
    else:
        check(gate, trial_dir, variant)

    _overlay_cost_from_result_json(gate, trial_dir)

    if gate.reward and gate.reward.get("solution_hidden") == 0:
        _fail(gate, "agent could see /solution", "contamination")

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
                    category="infra",
                )
            )
            continue
        for trial_dir in trial_dirs:
            gates.append(check_trial(trial_dir, variant))
    return gates


def write_report(gates: list[TrialGate], out: Path) -> None:
    out.write_text(json.dumps([asdict(g) for g in gates], indent=2))
