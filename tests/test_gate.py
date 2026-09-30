"""Tests for owl/gate.py::check_trial reward.json category rules (R13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from owl.gate import check_jobs, check_trial, estimate_cost_from_sessions
from owl.round import Round

VARIANT = {"id": "vanilla-default", "agent": "claude-code", "expect": {"plugins": [], "mcp_servers": []}}


def _make_trial(tmp_path: Path, reward: dict | None) -> Path:
    """Build a minimal trial dir with a clean claude-code.txt log and an optional reward.json."""
    trial_dir = tmp_path / "trial-0"
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir(parents=True)
    init_event = {"type": "system", "subtype": "init", "plugins": [], "mcp_servers": []}
    result_event = {
        "type": "result",
        "total_cost_usd": 0.01,
        "num_turns": 1,
        "usage": {"input_tokens": 10},
        "is_error": False,
    }
    log = agent_dir / "claude-code.txt"
    log.write_text(json.dumps(init_event) + "\n" + json.dumps(result_event) + "\n")

    if reward is not None:
        verifier_dir = trial_dir / "verifier"
        verifier_dir.mkdir()
        (verifier_dir / "reward.json").write_text(json.dumps(reward))

    return trial_dir


def test_baseline_valid_zero_is_contamination(tmp_path: Path) -> None:
    """Covers: R13"""
    trial_dir = _make_trial(tmp_path, {"reward": 1, "baseline_valid": 0})
    gate = check_trial(trial_dir, VARIANT)
    assert gate.passed is False
    assert gate.category == "contamination"
    assert any("baseline moved or missing" in reason for reason in gate.reasons)


def test_verifier_complete_zero_is_infra(tmp_path: Path) -> None:
    """Covers: R13"""
    trial_dir = _make_trial(tmp_path, {"reward": 1, "baseline_valid": 1, "verifier_complete": 0})
    gate = check_trial(trial_dir, VARIANT)
    assert gate.passed is False
    assert gate.category == "infra"
    assert any("verifier_complete" in reason for reason in gate.reasons)


def test_contamination_wins_over_infra_on_ties(tmp_path: Path) -> None:
    """Covers: R13"""
    trial_dir = _make_trial(tmp_path, {"reward": 1, "baseline_valid": 0, "verifier_complete": 0})
    gate = check_trial(trial_dir, VARIANT)
    assert gate.passed is False
    assert gate.category == "contamination"


def test_missing_keys_do_not_fail(tmp_path: Path) -> None:
    """Older tasks (e.g. 01-probe) don't report baseline_valid/verifier_complete; absence must
    not fail the gate. Covers: R13"""
    trial_dir = _make_trial(
        tmp_path,
        {"reward": 1, "probe_valid": 1, "tests_hidden": 1, "solution_hidden": 1, "home_claude_clean": 1, "no_context_files": 1},
    )
    gate = check_trial(trial_dir, VARIANT)
    assert gate.passed is True
    assert gate.category == "ok"


def test_ok_path_unaffected(tmp_path: Path) -> None:
    """A healthy trial with both keys set to 1 stays ok. Covers: R13"""
    trial_dir = _make_trial(tmp_path, {"reward": 1, "baseline_valid": 1, "verifier_complete": 1})
    gate = check_trial(trial_dir, VARIANT)
    assert gate.passed is True
    assert gate.category == "ok"
    assert gate.reasons == []


# ---------------------------------------------------------------------------
# T8 / T9: D10 classification table and cost (R13, R17, R20, R21, R25)
# ---------------------------------------------------------------------------

PRICES = {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0}
INIT = {"type": "system", "subtype": "init", "plugins": [], "mcp_servers": []}
FINISHED = "2026-09-29T21:00:00.000Z"


def _result(**over: object) -> dict:
    base = {"type": "result", "subtype": "success", "total_cost_usd": 0.01, "num_turns": 1,
            "usage": {"input_tokens": 10}, "is_error": False, "api_error_status": None, "result": "done"}
    base.update(over)
    return base


def _trial(tmp_path: Path, events: list[dict], exception_type: str | None = None, finished_at: str = FINISHED) -> Path:
    trial = tmp_path / "trial-0"
    (trial / "agent").mkdir(parents=True)
    (trial / "agent" / "claude-code.txt").write_text("".join(json.dumps(e) + "\n" for e in events))
    data: dict = {"agent_execution": {"finished_at": finished_at}}
    if exception_type:
        data["exception_info"] = {"exception_type": exception_type}
    (trial / "result.json").write_text(json.dumps(data))
    return trial


def _msg(kind: str, ts: str) -> dict:
    return {"type": kind, "timestamp": ts}


def test_timeout_waiting_tool_is_valid(tmp_path: Path) -> None:
    """Covers: R20, R21 (last stamped event is an assistant tool call: the variant's work timed out)."""
    events = [INIT, _msg("user", "2026-09-29T20:40:00Z"), _msg("assistant", "2026-09-29T20:41:00Z")]
    gate = check_trial(_trial(tmp_path, events, "AgentTimeoutError"), VARIANT)
    assert gate.passed is True and gate.category == "ok"
    assert gate.limit_hit == "timeout" and gate.infra_reason is None


def test_timeout_waiting_model_is_api_stall(tmp_path: Path) -> None:
    """Covers: R21"""
    events = [INIT, _msg("assistant", "2026-09-29T20:40:00Z"), _msg("user", "2026-09-29T20:50:00Z")]
    gate = check_trial(_trial(tmp_path, events, "AgentTimeoutError"), VARIANT)
    assert gate.passed is False and gate.category == "infra"
    assert gate.infra_reason == "api_stall" and gate.limit_hit is None


def test_stall_ignores_untimestamped_rate_limit_event(tmp_path: Path) -> None:
    """Covers: R21 (a trailing rate_limit_event has no timestamp and must not date the stall)."""
    rl = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}}
    # Last stamped event is a user event 9 min before the end -> stall, despite the fresh-looking tail.
    events = [INIT, _msg("assistant", "2026-09-29T20:40:00Z"), _msg("user", "2026-09-29T20:51:00Z"), rl]
    gate = check_trial(_trial(tmp_path, events, "AgentTimeoutError"), VARIANT)
    assert gate.infra_reason == "api_stall"
    # A user event only 1 min before the end is not a stall.
    events = [INIT, _msg("user", "2026-09-29T20:59:00Z"), rl]
    gate = check_trial(_trial(tmp_path / "b", events, "AgentTimeoutError"), VARIANT)
    assert gate.passed is True and gate.limit_hit == "timeout"


@pytest.mark.parametrize(
    ("exception_type", "limit"),
    [("ContextWindowExceededError", "context"), ("OutputTokenExceededError", "output"), ("AgentSafetyRefusalError", "refusal")],
)
def test_context_output_refusal_are_valid(tmp_path: Path, exception_type: str, limit: str) -> None:
    """Covers: R20"""
    gate = check_trial(_trial(tmp_path, [INIT, _result()], exception_type), VARIANT)
    assert gate.passed is True and gate.limit_hit == limit


@pytest.mark.parametrize(("subtype", "limit"), [("error_max_turns", "max_turns"), ("error_max_budget_usd", "max_budget")])
def test_result_subtype_limits_are_valid(tmp_path: Path, subtype: str, limit: str) -> None:
    """Covers: R20"""
    gate = check_trial(_trial(tmp_path, [INIT, _result(subtype=subtype, is_error=True)]), VARIANT)
    assert gate.passed is True and gate.limit_hit == limit


def test_rate_limit_rejected_is_usage_limit(tmp_path: Path) -> None:
    """Covers: R17"""
    rl = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1790727000}}
    gate = check_trial(_trial(tmp_path, [INIT, rl, _result()]), VARIANT)
    assert gate.passed is False and gate.category == "infra" and gate.infra_reason == "usage_limit"


def test_rate_limit_allowed_warning_counted_not_excluded(tmp_path: Path) -> None:
    """Covers: R17"""
    rl = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning"}}
    gate = check_trial(_trial(tmp_path, [INIT, rl, rl, _result()]), VARIANT)
    assert gate.passed is True and gate.category == "ok"
    assert gate.rate_limit_warnings == 2 and gate.infra_reason is None


def test_429_is_usage_limit(tmp_path: Path) -> None:
    """Covers: R17"""
    gate = check_trial(_trial(tmp_path, [INIT, _result(is_error=True, api_error_status=429, result="boom")]), VARIANT)
    assert gate.category == "infra" and gate.infra_reason == "usage_limit"


@pytest.mark.parametrize("text", ["Claude AI usage limit reached|1790727000", "Your limit will reset at 5pm", "You've hit your usage limit"])
def test_usage_limit_text_is_usage_limit(tmp_path: Path, text: str) -> None:
    """Covers: R17"""
    gate = check_trial(_trial(tmp_path, [INIT, _result(is_error=True, result=text)]), VARIANT)
    assert gate.category == "infra" and gate.infra_reason == "usage_limit"


def test_5xx_is_infra(tmp_path: Path) -> None:
    """Covers: R17"""
    text = "API Error: 500 Internal server error"
    gate = check_trial(_trial(tmp_path, [INIT, _result(is_error=True, result=text)]), VARIANT)
    assert gate.passed is False and gate.category == "infra" and gate.infra_reason == "api_error"


def test_nonzero_exit_is_agent_exit(tmp_path: Path) -> None:
    """Covers: R17"""
    gate = check_trial(_trial(tmp_path, [INIT], "NonZeroAgentExitCodeError"), VARIANT)
    assert gate.category == "infra" and gate.infra_reason == "agent_exit"


def _round(tmp_path: Path, **raw: object) -> Round:
    rdir = tmp_path / "round"
    rdir.mkdir(exist_ok=True)
    (rdir / "preamble.md").write_text("Work unattended.\n")
    return Round(
        id="r1", dir=rdir, model="anthropic/claude-haiku-4-5-20251001", agent_version="2.1.281",
        variants=["vanilla-default"], baseline="vanilla-default", placebo="vanilla-default", tasks=[],
        prices_usd_per_mtok=PRICES, artifacts=[], raw=raw,
        limits={
            "agent_timeout_multiplier": 3.0, "agent_setup_timeout_multiplier": 2.0,
            "max_turns": 300, "max_budget_usd": "5.00",
        },
    )


def _round_trial(tmp_path: Path, first_user: str | None, **kwargs_over: object) -> Path:
    trial = _trial(tmp_path, [INIT, _result()])
    kwargs = {"version": "2.1.281", "max_turns": 300, "max_budget_usd": "5.00", **kwargs_over}
    (trial / "config.json").write_text(json.dumps({"agent": {"model_name": "anthropic/claude-haiku-4-5-20251001", "kwargs": kwargs}}))
    if first_user is not None:
        proj = trial / "agent" / "sessions" / "projects" / "-app"
        proj.mkdir(parents=True)
        queue = {"type": "queue-operation", "content": "Work unattended.\n"}
        user = {"type": "user", "message": {"role": "user", "content": first_user}}
        (proj / "s.jsonl").write_text(json.dumps(queue) + "\n" + json.dumps(user) + "\n")
    return trial


ROUND_VARIANT = {**VARIANT, "round": {"id": "r1"}}


def test_round_conformance_ok(tmp_path: Path) -> None:
    """Covers: R13"""
    trial = _round_trial(tmp_path, "fix it\n\nWork unattended.\n")
    gate = check_trial(trial, ROUND_VARIANT, _round(tmp_path))
    assert gate.passed is True and gate.category == "ok"


def test_round_conformance_mismatch_is_contamination(tmp_path: Path) -> None:
    """Covers: R13"""
    trial = _round_trial(tmp_path, "fix it\n\nWork unattended.\n", max_turns=100)
    gate = check_trial(trial, ROUND_VARIANT, _round(tmp_path))
    assert gate.category == "contamination"
    assert any("max_turns" in r for r in gate.reasons)


def test_preamble_missing_is_contamination(tmp_path: Path) -> None:
    """Covers: R13 (the queue-operation record carries the text but is not the first user message)."""
    trial = _round_trial(tmp_path, "fix it")
    gate = check_trial(trial, ROUND_VARIANT, _round(tmp_path))
    assert gate.category == "contamination"
    assert any("preamble" in r for r in gate.reasons)


def test_check_jobs_round_def_runs_conformance(tmp_path: Path) -> None:
    """Covers: R13"""
    job = tmp_path / "job"
    job.mkdir()
    _round_trial(job, "fix it")  # no preamble in the first user message
    (job / "owl-variant.json").write_text(json.dumps(ROUND_VARIANT))
    assert check_jobs(tmp_path)[0].passed is True
    gate = check_jobs(tmp_path, _round(tmp_path))[0]
    assert gate.category == "contamination" and any("preamble" in r for r in gate.reasons)


def test_resets_at_captured_from_rejected_event(tmp_path: Path) -> None:
    """Covers: R17"""
    rl = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1790727000}}
    assert check_trial(_trial(tmp_path, [INIT, rl, _result()]), VARIANT).resets_at == 1790727000


def test_resets_at_none_without_rejection(tmp_path: Path) -> None:
    """Covers: R17"""
    rl = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning", "resetsAt": 1790727000}}
    assert check_trial(_trial(tmp_path, [INIT, rl, _result()]), VARIANT).resets_at is None


def _assistant(mid: str, usage: dict) -> dict:
    return {"type": "assistant", "message": {"id": mid, "role": "assistant", "usage": usage}}


def _write_session(trial: Path, records: list[dict], rel: str = "-app/main.jsonl") -> None:
    path = trial / "agent" / "sessions" / "projects" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_cost_reported_first(tmp_path: Path) -> None:
    """Covers: R25"""
    trial = _trial(tmp_path, [INIT, _result(total_cost_usd=0.5)])
    _write_session(trial, [_assistant("m1", {"input_tokens": 1_000_000})])
    gate = check_trial(trial, VARIANT, _round(tmp_path))
    assert gate.cost_usd == 0.5 and gate.cost_source == "reported"


def test_owl_estimate_groups_by_message_id(tmp_path: Path) -> None:
    """Covers: R25 (three records of one id with growing usage: only the last counts)."""
    trial = _trial(tmp_path, [INIT, _result(total_cost_usd=None)])
    _write_session(trial, [
        _assistant("m1", {"input_tokens": 100, "output_tokens": 1}),
        _assistant("m1", {"input_tokens": 100, "output_tokens": 10}),
        _assistant("m1", {"input_tokens": 100, "output_tokens": 1000}),
    ])
    gate = check_trial(trial, VARIANT, _round(tmp_path))
    # 100 * 1.0 + 1000 * 5.0 = 5100 USD-per-MTok units.
    assert gate.cost_source == "owl_estimate"
    assert gate.cost_usd == pytest.approx(5100 / 1_000_000)


def test_owl_estimate_splits_cache_write_5m_1h(tmp_path: Path) -> None:
    """Covers: R25"""
    trial = _trial(tmp_path, [INIT, _result()])
    usage = {"cache_creation_input_tokens": 300, "cache_creation": {"ephemeral_5m_input_tokens": 100, "ephemeral_1h_input_tokens": 200},
             "cache_read_input_tokens": 1000}
    _write_session(trial, [_assistant("m1", usage)])
    # 100 * 1.25 + 200 * 2.0 + 1000 * 0.1 = 625
    assert estimate_cost_from_sessions(trial, PRICES) == pytest.approx(625 / 1_000_000)


def test_owl_estimate_includes_subagent_files(tmp_path: Path) -> None:
    """Covers: R25"""
    trial = _trial(tmp_path, [INIT, _result()])
    _write_session(trial, [_assistant("m1", {"input_tokens": 100})])
    _write_session(trial, [_assistant("s1", {"output_tokens": 10})], "-app/abc/subagents/agent-1.jsonl")
    assert estimate_cost_from_sessions(trial, PRICES) == pytest.approx((100 + 50) / 1_000_000)


def _harbor_cost(trial: Path) -> None:
    data = json.loads((trial / "result.json").read_text())
    data["agent_result"] = {"cost_usd": 9.99}
    (trial / "result.json").write_text(json.dumps(data))


def test_harbor_cost_ignored_for_claude_code(tmp_path: Path) -> None:
    """Covers: R25 (no reported cost and no sessions: Harbor's 9.99 must not be used)."""
    trial = _trial(tmp_path, [INIT, _result(total_cost_usd=None)])
    _harbor_cost(trial)
    gate = check_trial(trial, VARIANT, _round(tmp_path))
    assert gate.cost_usd is None and gate.cost_source is None


def test_harbor_cost_kept_for_codex(tmp_path: Path) -> None:
    """Covers: R25"""
    trial = tmp_path / "trial-0"
    (trial / "agent").mkdir(parents=True)
    (trial / "agent" / "codex.txt").write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5}}) + "\n")
    (trial / "result.json").write_text(json.dumps({"agent_result": {"cost_usd": 0.42}}))
    gate = check_trial(trial, {"id": "codex-default", "agent": "codex"})
    assert gate.cost_usd == 0.42


def test_result_event_flag(tmp_path: Path) -> None:
    """Covers: R22"""
    with_result = _make_trial(tmp_path, {"reward": 1})
    assert check_trial(with_result, VARIANT).result_event is True

    no_result = tmp_path / "trial-1"
    (no_result / "agent").mkdir(parents=True)
    init = {"type": "system", "subtype": "init", "plugins": [], "mcp_servers": []}
    (no_result / "agent" / "claude-code.txt").write_text(json.dumps(init) + "\n")
    assert check_trial(no_result, VARIANT).result_event is False


def test_multi_result_turns_are_summed(tmp_path: Path) -> None:
    """Covers: R29 (mean turns): every result event of a delegating run counts, cost stays the last one."""
    results = [_result(num_turns=n, total_cost_usd=0.4) for n in (7, 4, 5, 3, 4, 3)]
    gate = check_trial(_trial(tmp_path, [INIT, *results]), VARIANT)
    assert gate.num_turns == 26
    assert gate.cost_usd == 0.4


def test_single_result_turns_unchanged(tmp_path: Path) -> None:
    """Covers: R29"""
    gate = check_trial(_trial(tmp_path, [INIT, _result(num_turns=9)]), VARIANT)
    assert gate.num_turns == 9


def test_real_navori_smoke_turns_are_summed() -> None:
    """Covers: R29 (real 6-result navori trial; jobs/ is git-ignored, so skipped when absent)."""
    root = Path(__file__).resolve().parent.parent / "jobs" / "smoke-f3" / "main-v2"
    trials = sorted(root.glob("*navori*/02-smoke-patient__*/agent/claude-code.txt"))
    if not trials:
        pytest.skip("real navori smoke trial not present")
    gate = check_trial(trials[0].parent.parent, VARIANT)
    assert gate.num_turns == 26


def test_round_conformance_flags_mismatched_max_turns_and_budget(tmp_path: Path) -> None:
    """Covers: R11, R13, R20"""
    trial = _round_trial(tmp_path, "fix it\n\nWork unattended.\n", max_turns=2, max_budget_usd="1.00")
    gate = check_trial(trial, ROUND_VARIANT, _round(tmp_path))
    assert gate.category == "contamination"
    assert any("max_turns expected '300', recorded '2'" in r for r in gate.reasons)
    assert any("max_budget_usd" in r for r in gate.reasons)


# ---------------------------------------------------------------------------
# Pending MCP servers (R13)
# ---------------------------------------------------------------------------

_PENDING_VARIANT = {"id": "v", "agent": "claude-code", "expect": {"plugins": [], "mcp_servers": ["context7"]}}


def _mcp_trial(tmp_path: Path, status: str, connected_later: bool) -> Path:
    init = {**INIT, "mcp_servers": [{"name": "context7", "status": status}]}
    trial = _trial(tmp_path, [init, _result()])
    names = ["mcp__context7__query-docs"] if connected_later else ["Bash"]
    delta = {"type": "attachment", "attachment": {"type": "deferred_tools_delta", "addedNames": names}}
    sessions = trial / "agent" / "sessions" / "projects" / "-app"
    sessions.mkdir(parents=True)
    (sessions / "s.jsonl").write_text(json.dumps(delta) + "\n")
    return trial


def test_pending_mcp_connected_later_is_ok(tmp_path: Path) -> None:
    """Covers: R13"""
    gate = check_trial(_mcp_trial(tmp_path, "pending", True), _PENDING_VARIANT)
    assert gate.passed is True and gate.category == "ok"


def test_pending_mcp_never_connected_is_contamination(tmp_path: Path) -> None:
    """Covers: R13"""
    gate = check_trial(_mcp_trial(tmp_path, "pending", False), _PENDING_VARIANT)
    assert gate.category == "contamination" and "never connected" in gate.reasons[0]


def test_pending_mcp_undeclared_is_contamination(tmp_path: Path) -> None:
    """Covers: R13"""
    variant = {**_PENDING_VARIANT, "expect": {"plugins": [], "mcp_servers": []}}
    gate = check_trial(_mcp_trial(tmp_path, "pending", True), variant)
    assert gate.category == "contamination" and any("not declared" in r for r in gate.reasons)


def test_failed_mcp_stays_contamination_even_with_pending_rule(tmp_path: Path) -> None:
    """Covers: R13 (pending rule does not soften failed)"""
    gate = check_trial(_mcp_trial(tmp_path, "failed", True), _PENDING_VARIANT)
    assert gate.category == "contamination" and "status failed" in gate.reasons[0]
