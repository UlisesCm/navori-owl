"""Tests for owl/gate.py::check_trial reward.json category rules (R13)."""

from __future__ import annotations

import json
from pathlib import Path

from owl.gate import check_trial

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
