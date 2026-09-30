"""Contamination gate: prove each trial loaded exactly what its variant declared.

Dispatches by the variant's ``agent``:
- ``claude-code``: reads the stream-json log (``agent/claude-code.txt``) and checks
  ``system/init`` plugins/MCP servers against the manifest's ``expect`` block, plus a
  ``result`` event that is not an error and used tokens.
- ``codex``: reads the ``codex exec --json`` log (``agent/codex.txt``) and checks there is
  no ``error``/``turn.failed`` event and a ``turn.completed`` event that used tokens.
  Plugin/MCP ``expect`` is not verifiable from this log (Codex has no harness yet).

Both agents share:
- cost: ``total_cost_usd`` from the ``result`` event (claude-code, ``reported``), else an estimate
  from the session transcripts at the round's prices (``owl_estimate``); Harbor's own
  ``result.json`` cost is used only for agents whose log carries none (codex).
- for the isolation probe task: the oracle directory was not visible to the agent (``reward.json``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from harbor.agents.installed import base as harbor_base

from owl.round import Round

DEFAULT_STALL_MINUTES = 5
# Owl's own subscription-limit text (anthropics/claude-code#5977), on top of Harbor's patterns.
_SUBSCRIPTION_LIMIT = re.compile(r"usage limit|limit will reset", re.IGNORECASE)
_USAGE_LIMIT_ERRORS = {"ApiUsageLimitError", "ApiRateLimitError"}
# Exceptions that end a trial with a valid verdict: the treatment provoked them (D10).
_LIMIT_BY_EXCEPTION = {
    "AgentTimeoutError": "timeout",
    "ContextWindowExceededError": "context",
    "OutputTokenExceededError": "output",
    "AgentSafetyRefusalError": "refusal",
}
# ``result`` subtypes Claude Code emits when a run limit is reached.
_LIMIT_BY_SUBTYPE = {"error_max_turns": "max_turns", "error_max_budget_usd": "max_budget"}


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
    # Task directory the trial ran (Harbor ``config.json`` ``task.path``); None if unreadable.
    task_path: str | None = None
    # Valid trial that ended on a run limit: timeout | max_turns | max_budget | context | output | refusal.
    limit_hit: str | None = None
    # Harbor ``exception_info.exception_type`` from the trial's result.json, if any.
    exception_type: str | None = None
    # Why an infra trial was excluded: usage_limit | api_stall | api_error | agent_exit | setup | other.
    infra_reason: str | None = None
    # "reported" (result event), "owl_estimate" (session transcripts) or "harbor" (codex only).
    cost_source: str | None = None
    # rate_limit_event records with status allowed_warning: counted, never an exclusion (R17).
    rate_limit_warnings: int = 0
    # ``resetsAt`` (epoch seconds) of the rejected rate_limit_event, when the transcript reports it.
    resets_at: int | None = None
    # True when the agent log has a ``result`` event (claude-code) or a ``turn.completed`` (codex).
    result_event: bool = False


def _fail(gate: TrialGate, reason: str, category: str, infra_reason: str | None = None) -> None:
    """Record a failure reason under a bucket; contamination is sticky (never downgraded).

    ``infra_reason``: the first one recorded wins, except ``usage_limit`` which always wins
    (first row of the D10 table).
    """
    gate.passed = False
    gate.reasons.append(reason)
    if gate.category != "contamination":
        gate.category = category
    if category == "infra" and infra_reason and (gate.infra_reason is None or infra_reason == "usage_limit"):
        gate.infra_reason = infra_reason


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


def classify_error_text(text: str) -> str | None:
    """Harbor error class name for a failure text, or None.

    Reuses ``BaseInstalledAgent.ERROR_PATTERNS`` (case-insensitive, latest match wins, as
    Harbor's ``_classify_exec_error``) plus owl's subscription-limit pattern.
    """
    best: tuple[int, str] | None = None
    candidates = [(p.pattern, p.exception.__name__) for p in harbor_base.BaseInstalledAgent.ERROR_PATTERNS]
    candidates.append((_SUBSCRIPTION_LIMIT.pattern, "ApiUsageLimitError"))
    for pattern, name in candidates:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if best is None or match.end() > best[0]:
                best = (match.end(), name)
    return best[1] if best else None


def _is_api_error_class(name: str) -> bool:
    """True for Harbor's classified agent errors (API, auth, model, network, unknown)."""
    cls = getattr(harbor_base, name, None)
    base = harbor_base.NonZeroAgentExitCodeError
    return isinstance(cls, type) and issubclass(cls, base) and cls is not base


def _result_json(trial_dir: Path) -> dict:
    try:
        data = json.loads((trial_dir / "result.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_api_stall(events: list[dict], finished_at: object, stall_minutes: float) -> bool:
    """R21: last event carrying a ``timestamp`` is a tool result, at least ``stall_minutes`` before the end.

    Only ``assistant``/``user`` events carry a timestamp; ``rate_limit_event``, ``system`` and
    ``result`` have none and are ignored on purpose.
    """
    end = _parse_ts(finished_at)
    stamped = [e for e in events if e.get("type") in ("assistant", "user") and _parse_ts(e.get("timestamp"))]
    if end is None or not stamped:
        return False
    last = stamped[-1]
    last_ts = _parse_ts(last["timestamp"])
    return last["type"] == "user" and last_ts is not None and (end - last_ts).total_seconds() >= stall_minutes * 60


def _classify_failure(gate: TrialGate, name: str, has_result: bool, events: list[dict], finished_at: object,
                      stall_minutes: float, detail: str = "") -> None:
    """Apply the D10 table to one Harbor error class name (from result text or ``exception_type``)."""
    suffix = f": {detail}" if detail else ""
    if name in _USAGE_LIMIT_ERRORS:
        _fail(gate, f"usage/rate limit: {name}{suffix}", "infra", "usage_limit")
    elif name == "AgentTimeoutError" and _is_api_stall(events, finished_at, stall_minutes):
        _fail(gate, "api_stall: timeout while waiting for the model", "infra", "api_stall")
    elif name in _LIMIT_BY_EXCEPTION:
        gate.limit_hit = _LIMIT_BY_EXCEPTION[name]
    elif name == "NonZeroAgentExitCodeError" and not has_result:
        _fail(gate, "agent exited non-zero without a result", "infra", "agent_exit")
    elif _is_api_error_class(name):
        _fail(gate, f"api error: {name}{suffix}", "infra", "api_error")
    elif name != "NonZeroAgentExitCodeError":
        _fail(gate, f"trial exception: {name}{suffix}", "infra", "other")


def _mcp_connected_later(trial_dir: Path, server: str) -> bool:
    """True when the session transcript shows ``server`` connected after init.

    Signal: a ``deferred_tools_delta`` attachment whose ``addedNames`` lists ``mcp__<server>__*``
    tools. Claude Code adds a server's tools only once it connects (real gentle-ai trial: context7,
    an npx/stdio server, pending at init, tools added ~6 s later with ``pendingMcpServers: []``).
    A server that never connects never adds tools, so it stays contamination.
    """
    prefix = f"mcp__{server}__"
    for path in sorted((trial_dir / "agent" / "sessions" / "projects").rglob("*.jsonl")):
        for line in path.read_text(errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            attachment = record.get("attachment") if isinstance(record, dict) else None
            is_delta = isinstance(attachment, dict) and attachment.get("type") == "deferred_tools_delta"
            if is_delta and any(str(n).startswith(prefix) for n in attachment.get("addedNames") or []):
                return True
    return False


def _check_claude_code(gate: TrialGate, trial_dir: Path, variant: dict, stall_minutes: float) -> None:
    log = trial_dir / "agent" / "claude-code.txt"
    exc = gate.exception_type
    finished_at = ((_result_json(trial_dir).get("agent_execution")) or {}).get("finished_at")
    if not log.is_file():
        if exc:
            _classify_failure(gate, exc, False, [], finished_at, stall_minutes)
        _fail(gate, "no claude-code.txt: agent never started", "infra", "setup")
        return

    events = _events(log)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)

    # Signal 1 (circuit breaker): rate-limit events. Only ``rejected`` excludes; warnings are counted.
    for event in (e for e in events if e.get("type") == "rate_limit_event"):
        info = event.get("rate_limit_info") or {}
        if info.get("status") == "allowed_warning":
            gate.rate_limit_warnings += 1
        elif info.get("status") == "rejected":
            _fail(gate, "rate_limit_event rejected", "infra", "usage_limit")
            gate.resets_at = info.get("resetsAt")

    limit_from_result = False
    gate.result_event = result is not None
    if result is not None:
        gate.cost_usd = result.get("total_cost_usd")
        if gate.cost_usd is not None:
            gate.cost_source = "reported"
        # A delegating harness ends a turn per wait, so the stream carries several result events,
        # each with its own num_turns: the trial's turns are their sum (cost stays session-wide on the last).
        gate.num_turns = sum(e.get("num_turns") or 0 for e in events if e.get("type") == "result")
        subtype_limit = _LIMIT_BY_SUBTYPE.get(str(result.get("subtype")))
        if subtype_limit:
            gate.limit_hit = subtype_limit
            limit_from_result = True
        elif result.get("is_error"):
            # is_error covers transport/auth failures, rate limits and the model erroring out
            # mid-run; none means the run loaded the wrong harness, so it is infra, not contamination.
            text = str(result.get("result"))
            if result.get("api_error_status") == 429:
                name = "ApiUsageLimitError"
            else:
                name = classify_error_text(text) or "UnknownApiError"
            _classify_failure(gate, name, True, events, finished_at, stall_minutes, f"result is_error: {text[:160]}")
            limit_from_result = name in _LIMIT_BY_EXCEPTION

    if exc and not limit_from_result and not (result is not None and result.get("is_error")):
        _classify_failure(gate, exc, result is not None, events, finished_at, stall_minutes)

    if init is None:
        _fail(gate, "no system/init event", "infra", "setup")
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
        declared_mcp = set(expect.get("mcp_servers") or [])
        for server in mcp_servers:
            status, name = server.get("status"), server.get("name", "?")
            if status == "connected":
                continue
            if status == "pending" and name in declared_mcp:
                if _mcp_connected_later(trial_dir, name):
                    continue
                _fail(gate, f"mcp server {name}: pending at init and never connected in the session", "contamination")
            elif status == "pending":
                _fail(gate, f"mcp server {name}: pending at init and not declared in expect.mcp_servers", "contamination")
            else:
                _fail(gate, f"mcp server {name}: status {status}", "contamination")
        for key in ("plugin_errors", "mcp_server_errors"):
            if init.get(key):
                _fail(gate, f"{key}: {init[key]}", "contamination")

    if result is None:
        # A timeout or a killed agent legitimately leaves no result; only an unexplained absence is infra.
        if not exc:
            _fail(gate, "no result event: run did not finish", "infra", "other")
    else:
        usage = result.get("usage") or {}
        tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
        if not tokens:
            _fail(gate, "zero tokens used: never reached the model", "infra", "other")


def _check_codex(gate: TrialGate, trial_dir: Path, variant: dict, stall_minutes: float) -> None:
    log = trial_dir / "agent" / "codex.txt"
    if not log.is_file():
        _fail(gate, "no codex.txt: agent never started", "infra", "setup")
        return

    expect = variant.get("expect") or {}
    if expect.get("plugins") or expect.get("mcp_servers"):
        _fail(gate, "plugins/mcp_servers expectation not verifiable for agent 'codex' (no harness yet)", "contamination")

    events = _events(log)
    errors = [e for e in events if e.get("type") in ("error", "turn.failed")]
    if errors:
        for error in errors:
            detail = error.get("error") or error.get("message") or error
            _fail(gate, f"{error.get('type')}: {str(detail)[:160]}", "infra", "api_error")

    completed = [e for e in events if e.get("type") == "turn.completed"]
    if not completed:
        _fail(gate, "no turn.completed event: run did not finish", "infra", "other")
        return

    gate.result_event = True
    gate.num_turns = len(completed)
    usage = completed[-1].get("usage") or {}
    tokens = sum(v for v in usage.values() if isinstance(v, (int, float)))
    if not tokens:
        _fail(gate, "zero tokens used: never reached the model", "infra", "other")


_AGENT_CHECKS = {
    "claude-code": _check_claude_code,
    "codex": _check_codex,
}


def _overlay_cost_from_result_json(gate: TrialGate, trial_dir: Path) -> None:
    """Take Harbor's own cost (``result.json``) for agents whose log carries none (codex).

    Never applied to ``claude-code``: Harbor's per-step LiteLLM estimate uses one cache-write
    price and lands at 0.83-0.94 of the reported cost (D10).
    """
    agent_result = _result_json(trial_dir).get("agent_result") or {}
    if agent_result.get("cost_usd") is not None:
        gate.cost_usd = agent_result["cost_usd"]
        gate.cost_source = "harbor"


def estimate_cost_from_sessions(trial_dir: Path, prices: dict[str, float]) -> float | None:
    """Owl's cost estimate from the session transcripts (R25); None when there are no usable records.

    Reads every ``agent/sessions/projects/**/*.jsonl`` (main and subagent files), groups
    ``assistant`` records by ``message.id`` and prices the ``usage`` of the last record of each id.
    Cache writes are priced at the 5 min and 1 h rates separately. Prices are USD per MTok.
    """
    last_usage: dict[str, dict] = {}
    for path in sorted((trial_dir / "agent" / "sessions" / "projects").rglob("*.jsonl")):
        for line in path.read_text(errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message") if isinstance(record, dict) else None
            if record.get("type") != "assistant" or not isinstance(message, dict):
                continue
            if message.get("id") and isinstance(message.get("usage"), dict):
                last_usage[message["id"]] = message["usage"]
    if not last_usage:
        return None
    total = 0.0
    for usage in last_usage.values():
        creation = usage.get("cache_creation") or {}
        w5 = creation.get("ephemeral_5m_input_tokens")
        w1 = creation.get("ephemeral_1h_input_tokens")
        if w5 is None and w1 is None:
            # No 5m/1h split: the whole write is priced at the 5 min rate.
            w5, w1 = usage.get("cache_creation_input_tokens") or 0, 0
        total += (
            (usage.get("input_tokens") or 0) * prices["input"]
            + (usage.get("output_tokens") or 0) * prices["output"]
            + (usage.get("cache_read_input_tokens") or 0) * prices["cache_read"]
            + (w5 or 0) * prices["cache_write_5m"]
            + (w1 or 0) * prices["cache_write_1h"]
        )
    return total / 1_000_000


def _first_user_text(trial_dir: Path) -> str | None:
    """Text of the first ``user`` message of the session transcript; falls back to ``trajectory.json``."""
    for path in sorted((trial_dir / "agent" / "sessions" / "projects").glob("*/*.jsonl")):
        for line in path.read_text(errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("type") == "user":
                content = (record.get("message") or {}).get("content")
                if isinstance(content, list):
                    content = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
                return content if isinstance(content, str) else ""
    try:
        steps = json.loads((trial_dir / "agent" / "trajectory.json").read_text()).get("steps") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    step = next((x for x in steps if isinstance(x, dict) and x.get("source") == "user"), None)
    return str(step.get("message", "")) if step else None


def _check_round_conformance(gate: TrialGate, trial_dir: Path, variant: dict, round_def: Round) -> None:
    """R13: recorded model, version, limits, artifacts, system-prompt addition and preamble match the round."""
    try:
        agent = json.loads((trial_dir / "config.json").read_text()).get("agent") or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        _fail(gate, "round conformance: config.json unreadable", "contamination")
        return
    kwargs = agent.get("kwargs") or {}
    limits = round_def.limits

    def strip(model: object) -> str:
        return str(model).removeprefix("anthropic/")

    checks: list[tuple[str, object, object]] = [
        ("model", strip(round_def.model), strip(agent.get("model_name"))),
        ("version", round_def.agent_version, str(kwargs.get("version"))),
        ("append_system_prompt", (variant.get("harness") or {}).get("append_system_prompt"), kwargs.get("append_system_prompt")),
    ]
    # Harbor's trial config.json does not record the timeout multipliers: only these two are comparable.
    checks.append(("max_turns", str(limits["max_turns"]), str(kwargs.get("max_turns"))))
    checks.append(("max_budget_usd", str(limits["max_budget_usd"]), str(kwargs.get("max_budget_usd"))))
    if round_def.artifacts:
        got = kwargs.get("artifacts")
        got_list = got.split(",") if isinstance(got, str) else list(got or [])
        checks.append(("artifacts", sorted(round_def.artifacts), sorted(got_list)))
    for name, expected, actual in checks:
        if expected != actual:
            _fail(gate, f"round conformance: {name} expected {expected!r}, recorded {actual!r}", "contamination")

    preamble = (round_def.dir / "preamble.md").read_text()
    first_user = _first_user_text(trial_dir)
    if first_user is None or preamble not in first_user:
        _fail(gate, "round conformance: preamble missing from the first user message", "contamination")


def _task_path(trial_dir: Path) -> str | None:
    """Task directory from the trial's Harbor ``config.json``; None if missing or malformed."""
    try:
        path = json.loads((trial_dir / "config.json").read_text()).get("task", {}).get("path")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return path if isinstance(path, str) else None


def check_trial(trial_dir: Path, variant: dict, round_def: Round | None = None) -> TrialGate:
    """Gate one trial. ``round_def`` enables the round-only checks: conformance (R13, when the
    variant manifest carries a ``round`` block), ``stall_minutes`` and the owl cost estimate."""
    gate = TrialGate(trial=trial_dir.name, variant=variant["id"], passed=True)
    reward_file = trial_dir / "verifier" / "reward.json"
    if reward_file.is_file():
        try:
            reward = json.loads(reward_file.read_text())
        except json.JSONDecodeError:
            reward = None
        if isinstance(reward, dict):
            gate.reward = reward
        else:
            _fail(gate, "invalid reward.json", "infra", "other")
    gate.task_path = _task_path(trial_dir)
    exception_info = _result_json(trial_dir).get("exception_info") or {}
    gate.exception_type = exception_info.get("exception_type") if isinstance(exception_info, dict) else None
    stall_minutes = float(round_def.raw.get("stall_minutes", DEFAULT_STALL_MINUTES)) if round_def else DEFAULT_STALL_MINUTES

    agent = variant.get("agent", "claude-code")
    check = _AGENT_CHECKS.get(agent)
    if check is None:
        _fail(gate, f"gate: agent '{agent}' not supported", "infra", "other")
    else:
        check(gate, trial_dir, variant, stall_minutes)

    if agent == "claude-code":
        if gate.cost_usd is None and round_def is not None:
            estimate = estimate_cost_from_sessions(trial_dir, round_def.prices_usd_per_mtok)
            if estimate is not None:
                gate.cost_usd, gate.cost_source = estimate, "owl_estimate"
    else:
        _overlay_cost_from_result_json(gate, trial_dir)

    if round_def is not None and variant.get("round"):
        _check_round_conformance(gate, trial_dir, variant, round_def)

    if gate.reward and gate.reward.get("solution_hidden") == 0:
        _fail(gate, "agent could see /solution", "contamination")

    if gate.reward and gate.reward.get("baseline_valid") == 0:
        _fail(gate, "baseline moved or missing", "contamination")

    if gate.reward and gate.reward.get("verifier_complete") == 0:
        _fail(gate, "verifier_complete=0: verifier did not finish", "infra", "other")

    return gate


def check_job(job_dir: Path, round_def: Round | None = None) -> list[TrialGate]:
    """Gate the trials of one job dir (its ``owl-variant.json`` names the variant)."""
    variant = json.loads((job_dir / "owl-variant.json").read_text())
    trial_dirs = sorted(p for p in job_dir.iterdir() if (p / "config.json").is_file())
    if not trial_dirs:
        code = variant.get("harbor_exit_code", "unknown")
        return [
            TrialGate(
                trial=job_dir.name,
                variant=variant["id"],
                passed=False,
                reasons=[f"no trial: harbor exited with {code}"],
                category="infra",
                infra_reason="setup",
            )
        ]
    return [check_trial(trial_dir, variant, round_def) for trial_dir in trial_dirs]


def check_jobs(jobs_dir: Path, round_def: Round | None = None) -> list[TrialGate]:
    """Gate every job under ``jobs_dir``; ``round_def`` enables the round-only checks per trial."""
    return [g for manifest in sorted(jobs_dir.glob("*/owl-variant.json")) for g in check_job(manifest.parent, round_def)]


def write_report(gates: list[TrialGate], out: Path) -> None:
    out.write_text(json.dumps([asdict(g) for g in gates], indent=2))
