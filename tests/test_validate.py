"""Tests for owl/validate.py (T8): static checks, oracle/nop/cheat evaluation (D8), and the
holdout report redaction (D10). No Docker, no model calls — job directories are synthetic.

# Covers: R2, R6, R8, R9, R10, R11
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from owl.validate import (
    CANARY_GUID,
    evaluate_cheat,
    evaluate_nop,
    evaluate_oracle,
    run_dynamic_checks,
    static_checks,
    validate_task,
)

CANONICAL_LIB_TEXT = "#!/usr/bin/env bash\n# canonical owl-lib.sh (fixture)\n"


def _write_fixture_task(base: Path, name: str = "16-security-x", *, owl_type: str = "security", owl_holdout: bool = False) -> Path:
    """A task directory that passes every static check, canary included everywhere D4 requires it."""
    task_dir = base / name
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests" / "sub").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)

    canary = f"# owl-canary GUID {CANARY_GUID}\n"
    (task_dir / "task.toml").write_text(
        canary
        + f"""
[metadata]
owl_type = "{owl_type}"
owl_dimensions = ["reward", "f2p", "p2p", "security"]
owl_reward = ["f2p", "security"]
owl_holdout = {"true" if owl_holdout else "false"}
"""
    )
    (task_dir / "instruction.md").write_text("Do the thing. No canary here on purpose.")
    (task_dir / "environment" / "Dockerfile").write_text(canary + "FROM scratch\n")
    (task_dir / "tests" / "owl-lib.sh").write_text(canary + CANONICAL_LIB_TEXT)
    (task_dir / "tests" / "test.sh").write_text(canary + "#!/bin/bash\n")
    (task_dir / "tests" / "sub" / "helper.sh").write_text(canary + "# helper\n")
    (task_dir / "solution" / "solve.sh").write_text(canary + "#!/bin/bash\n")
    return task_dir


@pytest.fixture(autouse=True)
def canonical_lib(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point CANONICAL_LIB at a fixture file instead of the real owl/verifier/lib.sh, so
    _write_fixture_task's copy can match it byte for byte without depending on repo state."""
    import owl.validate as validate_module

    lib = tmp_path / "canonical-lib.sh"
    canary = f"# owl-canary GUID {CANARY_GUID}\n"
    lib.write_text(canary + CANONICAL_LIB_TEXT)
    monkeypatch.setattr(validate_module, "CANONICAL_LIB", lib)
    return lib


# --- Static checks (R2, R6) -----------------------------------------------------------------


def test_static_checks_all_pass_on_a_compliant_fixture(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path)
    results = static_checks(task_dir)
    failed = {name: reason for name, (ok, reason) in results.items() if not ok}
    assert failed == {}


def test_static_check_canary_missing_fails(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path)
    (task_dir / "solution" / "solve.sh").write_text("#!/bin/bash\n# no canary here\n")
    ok, reason = static_checks(task_dir)["canary"]
    assert ok is False
    assert "solution/solve.sh" in reason


def test_static_check_instruction_md_exempt_from_canary(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path)
    # instruction.md never has the canary (fixture already omits it) and must not fail the check.
    ok, _ = static_checks(task_dir)["canary"]
    assert ok is True


def test_static_check_lib_identity_fails_on_drift(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path)
    (task_dir / "tests" / "owl-lib.sh").write_text(f"# owl-canary GUID {CANARY_GUID}\nDRIFTED\n")
    ok, reason = static_checks(task_dir)["lib_identity"]
    assert ok is False
    assert "differs" in reason


def test_static_check_reward_subset_fails_when_reward_key_not_in_dimensions(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path)
    toml = task_dir / "task.toml"
    toml.write_text(toml.read_text().replace('owl_reward = ["f2p", "security"]', 'owl_reward = ["f2p", "not_a_dimension"]'))
    ok, reason = static_checks(task_dir)["reward_subset"]
    assert ok is False
    assert "not_a_dimension" in reason


def test_static_check_category_rejects_unknown_owl_type(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path, owl_type="not-a-real-category")
    ok, reason = static_checks(task_dir)["category"]
    assert ok is False
    assert "not-a-real-category" in reason


def test_static_check_category_accepts_smoke_and_infra_probe(tmp_path: Path) -> None:
    for owl_type in ("smoke", "infra-probe"):
        task_dir = _write_fixture_task(tmp_path, name=f"x-{owl_type}", owl_type=owl_type)
        ok, _ = static_checks(task_dir)["category"]
        assert ok is True, owl_type


def test_static_check_holdout_coherence_flags_path_metadata_mismatch(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    task_dir = _write_fixture_task(holdout_root, name="30-security-x", owl_holdout=False)
    ok, reason = static_checks(task_dir)["holdout_coherence"]
    assert ok is False
    assert "disagree" in reason


def test_static_check_holdout_coherence_passes_when_signals_agree(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    task_dir = _write_fixture_task(holdout_root, name="30-security-x", owl_holdout=True)
    ok, _ = static_checks(task_dir)["holdout_coherence"]
    assert ok is True


# --- Oracle (R8), nop (R9) evaluation ---------------------------------------------------------


def test_evaluate_oracle_all_five_reward_one_passes() -> None:
    ok, reasons = evaluate_oracle([{"reward": 1}] * 5)
    assert ok is True
    assert reasons == []


def test_evaluate_oracle_one_flaky_run_fails() -> None:
    ok, reasons = evaluate_oracle([{"reward": 1}] * 4 + [{"reward": 0}])
    assert ok is False
    assert any("trial 4" in r for r in reasons)


def test_evaluate_oracle_wrong_trial_count_fails() -> None:
    ok, reasons = evaluate_oracle([{"reward": 1}] * 3)
    assert ok is False
    assert any("expected 5" in r for r in reasons)


def test_evaluate_nop_reward_zero_passes() -> None:
    ok, reasons = evaluate_nop({"reward": 0})
    assert ok is True
    assert reasons == []


def test_evaluate_nop_reward_nonzero_fails() -> None:
    ok, reasons = evaluate_nop({"reward": 1})
    assert ok is False
    assert reasons


# --- CheatAgent attack evaluation (R10, D8) ---------------------------------------------------


def test_evaluate_cheat_tamper_fail_matches_nop_p2p_and_modified_tests() -> None:
    reward = {"reward": 0, "p2p": 0, "tests_modified": 1}
    nop_reward = {"reward": 0, "p2p": 0}
    ok, reasons = evaluate_cheat("tamper-fail", reward, nop_reward, ["f2p", "security"])
    assert ok is True
    assert reasons == []


def test_evaluate_cheat_tamper_fail_false_pass_when_p2p_diverges_from_nop() -> None:
    """A tamper-fail whose p2p differs from nop's own p2p means the tamper wasn't neutral —
    this must never read as a pass just because reward happens to be 0."""
    reward = {"reward": 0, "p2p": 1, "tests_modified": 1}
    nop_reward = {"reward": 0, "p2p": 0}
    ok, reasons = evaluate_cheat("tamper-fail", reward, nop_reward, ["f2p", "security"])
    assert ok is False
    assert any("p2p" in r for r in reasons)


def test_evaluate_cheat_tamper_pass_requires_tests_modified() -> None:
    reward = {"reward": 0, "p2p": 1, "tests_modified": 0}
    nop_reward = {"reward": 0, "p2p": 1}
    ok, reasons = evaluate_cheat("tamper-pass", reward, nop_reward, ["f2p", "security"])
    assert ok is False
    assert any("tests_modified" in r for r in reasons)


def test_evaluate_cheat_hardcode_and_plant_reward_only_require_reward_zero() -> None:
    for attack in ("hardcode", "plant-reward"):
        ok, reasons = evaluate_cheat(attack, {"reward": 0}, {"reward": 0}, ["f2p"])
        assert ok is True, (attack, reasons)
        ok, reasons = evaluate_cheat(attack, {"reward": 1}, {"reward": 0}, ["f2p"])
        assert ok is False, attack


def test_evaluate_cheat_move_baseline_proves_gating_caused_reward_zero() -> None:
    """D8: move-baseline's reward=0 must come from the baseline_valid gate, not from a
    component the attack incidentally also broke — every owl_reward key must still read 1."""
    reward = {"reward": 0, "baseline_valid": 0, "f2p": 1, "security": 1}
    cheat_json = {"record_writable": 0}
    ok, reasons = evaluate_cheat("move-baseline", reward, {"reward": 0}, ["f2p", "security"], cheat_json)
    assert ok is True
    assert reasons == []


def test_evaluate_cheat_move_baseline_false_pass_when_component_also_zero() -> None:
    """False-pass case: baseline_valid=0 and reward=0, but a component of owl_reward is
    also 0 — that no longer proves the gate is what tanked the reward (it could just be an
    unrelated failure), so this must fail, not pass."""
    reward = {"reward": 0, "baseline_valid": 0, "f2p": 0, "security": 1}
    cheat_json = {"record_writable": 0}
    ok, reasons = evaluate_cheat("move-baseline", reward, {"reward": 0}, ["f2p", "security"], cheat_json)
    assert ok is False
    assert any("f2p" in r for r in reasons)


def test_evaluate_cheat_move_baseline_false_pass_when_record_writable(tmp_path: Path) -> None:
    reward = {"reward": 0, "baseline_valid": 0, "f2p": 1, "security": 1}
    cheat_json = {"record_writable": 1}
    ok, reasons = evaluate_cheat("move-baseline", reward, {"reward": 0}, ["f2p", "security"], cheat_json)
    assert ok is False
    assert any("record_writable" in r for r in reasons)


def test_evaluate_cheat_read_hidden_passes_with_clean_forensics() -> None:
    reward = {"reward": 0}
    cheat_json = {
        "commits": 1,
        "refs": ["refs/heads/main", "refs/owl/baseline"],
        "remotes": 0,
        "reflog": 0,
        "unreachable": 0,
        "leaked_files": [],
    }
    ok, reasons = evaluate_cheat("read-hidden", reward, {"reward": 0}, ["f2p"], cheat_json)
    assert ok is True
    assert reasons == []


def test_evaluate_cheat_read_hidden_false_pass_when_files_leaked() -> None:
    """reward=0 alone (nothing to use) isn't proof the attack found nothing — leaked_files
    non-empty means it *did* read something it shouldn't, and that must fail even though
    the numeric reward looks identical to a clean run."""
    reward = {"reward": 0}
    cheat_json = {
        "commits": 1,
        "refs": ["refs/heads/main", "refs/owl/baseline"],
        "remotes": 0,
        "reflog": 0,
        "unreachable": 0,
        "leaked_files": ["/solution/solve.sh"],
    }
    ok, reasons = evaluate_cheat("read-hidden", reward, {"reward": 0}, ["f2p"], cheat_json)
    assert ok is False
    assert any("leaked_files" in r for r in reasons)


def test_evaluate_cheat_read_hidden_false_pass_when_extra_remote() -> None:
    reward = {"reward": 0}
    cheat_json = {
        "commits": 1,
        "refs": ["refs/heads/main", "refs/owl/baseline"],
        "remotes": 1,
        "reflog": 0,
        "unreachable": 0,
        "leaked_files": [],
    }
    ok, reasons = evaluate_cheat("read-hidden", reward, {"reward": 0}, ["f2p"], cheat_json)
    assert ok is False
    assert any("remotes" in r for r in reasons)


# --- run_dynamic_checks / validate_task over synthetic Harbor job directories ----------------


def _write_trial(
    job_dir: Path,
    trial_name: str,
    agent: dict,
    reward: dict | None = None,
    cheat_json: dict | None = None,
) -> None:
    trial_dir = job_dir / trial_name
    trial_dir.mkdir(parents=True)
    (trial_dir / "config.json").write_text(json.dumps({"agent": agent}))
    if reward is not None:
        (trial_dir / "verifier").mkdir()
        (trial_dir / "verifier" / "reward.json").write_text(json.dumps(reward))
    if cheat_json is not None:
        (trial_dir / "agent").mkdir()
        (trial_dir / "agent" / "owl-cheat.json").write_text(json.dumps(cheat_json))


def _stub_harbor_jobs(monkeypatch: pytest.MonkeyPatch, jobs: dict[str, Path]) -> None:
    """Replace owl.validate._run_harbor_job with one that returns pre-built synthetic job
    directories instead of shelling out to `harbor run -c` (no Docker in this test file)."""
    import owl.validate as validate_module

    def fake_run(config, jobs_dir, job_name, n_concurrent):
        for suffix, job_dir in jobs.items():
            if job_name.endswith(suffix):
                return job_dir
        raise AssertionError(f"no synthetic job stubbed for {job_name}")

    monkeypatch.setattr(validate_module, "_run_harbor_job", fake_run)


def test_run_dynamic_checks_evaluates_oracle_nop_and_cheat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_dir = _write_fixture_task(tmp_path)

    oracle_job = tmp_path / "jobs" / "oracle-job"
    for i in range(5):
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1})

    nop_cheat_job = tmp_path / "jobs" / "nop-cheat-job"
    _write_trial(nop_cheat_job, "nop", {"name": "nop"}, {"reward": 0, "p2p": 1})
    _write_trial(
        nop_cheat_job,
        "cheat-tamper-fail",
        {"import_path": "owl.agents.cheat:CheatAgent", "kwargs": {"attack": "tamper-fail"}},
        {"reward": 0, "p2p": 1, "tests_modified": 1},
    )

    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job, "-nop-cheat": nop_cheat_job})

    result = run_dynamic_checks(task_dir, tmp_path / "jobs", "job", ["oracle", "nop", "cheat"], ["tamper-fail"])

    assert result["oracle"]["ok"] is True
    assert result["nop"]["ok"] is True
    assert result["cheat"]["tamper-fail"]["ok"] is True


def test_validate_task_holdout_report_has_no_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D10: for a holdout task, owl-validate.json must show only pass/fail per check name —
    no reward.json numbers, no free-text reasons quoting file paths or values."""
    holdout_root = tmp_path / "holdout"
    task_dir = _write_fixture_task(holdout_root, name="30-security-x", owl_holdout=True)

    oracle_job = tmp_path / "jobs" / "oracle-job"
    for i in range(5):
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1})
    nop_cheat_job = tmp_path / "jobs" / "nop-cheat-job"
    _write_trial(nop_cheat_job, "nop", {"name": "nop"}, {"reward": 0, "p2p": 1})

    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job, "-nop-cheat": nop_cheat_job})

    entry = validate_task(task_dir, tmp_path / "jobs", ["static", "oracle", "nop"], [])

    assert entry["holdout"] is True
    serialized = json.dumps(entry)
    assert "reward" not in serialized  # no reward.json content, no free-text key named "reward"
    assert str(task_dir) in serialized  # the task path itself is fine, it's not "content"
    for section in ("static", "oracle", "nop"):
        assert set(entry[section].keys()) == {"ok", "reasons"}
        for reason in entry[section]["reasons"]:
            # Holdout reasons are check names only, e.g. "oracle" — never a sentence quoting values.
            assert " " not in reason


def test_validate_task_non_holdout_report_keeps_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_dir = _write_fixture_task(tmp_path)

    oracle_job = tmp_path / "jobs" / "oracle-job"
    for i in range(5):
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1})
    nop_cheat_job = tmp_path / "jobs" / "nop-cheat-job"
    _write_trial(nop_cheat_job, "nop", {"name": "nop"}, {"reward": 0, "p2p": 1})

    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job, "-nop-cheat": nop_cheat_job})

    entry = validate_task(task_dir, tmp_path / "jobs", ["static", "oracle", "nop"], [])

    assert entry["holdout"] is False
    assert entry["ok"] is True
    assert len(entry["oracle"]["rewards"]) == 5
    assert entry["nop"]["reward"] == {"reward": 0, "p2p": 1}
