"""Tests for owl/validate.py (T8): static checks, oracle/nop/cheat evaluation (D8), and the
holdout report redaction (D10). No Docker, no model calls — job directories are synthetic.

# Covers: R2, R6, R8, R9, R10, R11
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from owl.tasks import NON_SUITE_TYPES, SUITE_CATEGORIES
from owl.validate import (
    _CANARY_GLOBS,
    CANARY_GUID,
    CANONICAL_LIB,
    CHEAT_ATTACKS,
    evaluate_cheat,
    evaluate_dimensions,
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
owl_target_dimension = "security"
owl_holdout = {"true" if owl_holdout else "false"}
"""
    )
    (task_dir / "instruction.md").write_text("Do the thing. No canary here on purpose.")
    (task_dir / "environment" / "Dockerfile").write_text(canary + "FROM scratch\n")
    (task_dir / "tests" / "owl-lib.sh").write_text(canary + CANONICAL_LIB_TEXT)
    (task_dir / "tests" / "test.sh").write_text(canary + "#!/bin/bash\n")
    (task_dir / "tests" / "sub" / "helper.sh").write_text(canary + "# helper\n")
    (task_dir / "solution" / "solve.sh").write_text(canary + "#!/bin/bash\n")
    (task_dir / "tests" / "scope.allow").write_text(canary + "src/\n")
    (task_dir / "cheat").mkdir()
    (task_dir / "cheat" / "hardcode.sh").write_text(canary + "#!/bin/bash\n")
    for script in ("solution/solve.sh", "tests/test.sh", "cheat/hardcode.sh"):
        (task_dir / script).chmod(0o755)
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
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1, "f2p": 1, "p2p": 1, "security": 1})
    nop_cheat_job = tmp_path / "jobs" / "nop-cheat-job"
    _write_trial(nop_cheat_job, "nop", {"name": "nop"}, {"reward": 0, "p2p": 1})

    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job, "-nop-cheat": nop_cheat_job})

    entry = validate_task(task_dir, tmp_path / "jobs", ["static", "oracle", "nop"], [])

    assert entry["holdout"] is True
    serialized = json.dumps(entry)
    assert "reward" not in serialized  # no reward.json content, no free-text key named "reward"
    assert str(task_dir) in serialized  # the task path itself is fine, it's not "content"
    for section in ("static", "oracle", "dimensions", "nop"):
        assert set(entry[section].keys()) == {"ok", "reasons"}
        for reason in entry[section]["reasons"]:
            # Holdout reasons are check names only, e.g. "oracle" — never a sentence quoting values.
            assert " " not in reason


# Covers: R14
def test_validate_task_holdout_redacts_failing_dimensions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing `dimensions` check on a holdout task exposes only the check name, never the key diff."""
    task_dir = _write_fixture_task(tmp_path / "holdout", name="30-security-x", owl_holdout=True)
    oracle_job = tmp_path / "jobs" / "oracle-job"
    for i in range(5):
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1, "secret_extra_key": 1})
    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job})

    entry = validate_task(task_dir, tmp_path / "jobs", ["oracle"], [])

    assert entry["dimensions"]["ok"] is False
    assert entry["dimensions"]["reasons"] == ["dimensions"]
    assert "secret_extra_key" not in json.dumps(entry)


def test_validate_task_non_holdout_report_keeps_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_dir = _write_fixture_task(tmp_path)

    oracle_job = tmp_path / "jobs" / "oracle-job"
    for i in range(5):
        _write_trial(oracle_job, f"t{i}", {"name": "oracle"}, {"reward": 1, "f2p": 1, "p2p": 1, "security": 1})
    nop_cheat_job = tmp_path / "jobs" / "nop-cheat-job"
    _write_trial(nop_cheat_job, "nop", {"name": "nop"}, {"reward": 0, "p2p": 1})

    _stub_harbor_jobs(monkeypatch, {"-oracle": oracle_job, "-nop-cheat": nop_cheat_job})

    entry = validate_task(task_dir, tmp_path / "jobs", ["static", "oracle", "nop"], [])

    assert entry["holdout"] is False
    assert entry["ok"] is True
    assert len(entry["oracle"]["rewards"]) == 5
    assert entry["nop"]["reward"] == {"reward": 0, "p2p": 1}


# Covers: R6
@pytest.mark.parametrize(
    "rel",
    ["instruction.md", "environment/Dockerfile", "solution/solve.sh", "tests/test.sh",
     "tests/scope.allow", "cheat/hardcode.sh", "tests/owl-lib.sh"],
)
def test_static_check_required_files_fails_when_missing(tmp_path: Path, rel: str) -> None:
    task_dir = _write_fixture_task(tmp_path)
    (task_dir / rel).unlink()
    ok, reason = static_checks(task_dir)["required_files"]
    assert not ok
    assert f"{rel} missing" in reason


# Covers: R6
@pytest.mark.parametrize("rel", ["solution/solve.sh", "tests/test.sh", "cheat/hardcode.sh"])
def test_static_check_required_files_fails_when_not_executable(tmp_path: Path, rel: str) -> None:
    task_dir = _write_fixture_task(tmp_path)
    (task_dir / rel).chmod(0o644)
    ok, reason = static_checks(task_dir)["required_files"]
    assert not ok
    assert f"{rel} not executable" in reason


# Covers: R6
def test_static_check_required_files_non_suite_fixture_needs_no_hardcode_or_scope(tmp_path: Path) -> None:
    task_dir = _write_fixture_task(tmp_path, owl_type="smoke")
    (task_dir / "cheat" / "hardcode.sh").unlink()
    (task_dir / "tests" / "scope.allow").unlink()
    assert static_checks(task_dir)["required_files"][0]


def _rewrite_metadata(task_dir: Path, old: str, new: str) -> None:
    toml = task_dir / "task.toml"
    text = toml.read_text()
    assert old in text
    toml.write_text(text.replace(old, new))


# Covers: R6
@pytest.mark.parametrize(
    ("old", "new", "needle"),
    [
        ('owl_reward = ["f2p", "security"]', "owl_reward = []", "owl_reward missing or empty"),
        ('owl_dimensions = ["reward", "f2p", "p2p", "security"]', "owl_dimensions = []", "owl_dimensions missing or empty"),
        ('owl_target_dimension = "security"\n', "", "owl_target_dimension missing or empty"),
        ('owl_target_dimension = "security"', 'owl_target_dimension = "  "', "owl_target_dimension missing or empty"),
    ],
)
def test_static_check_metadata_rejects_empty_or_missing(tmp_path: Path, old: str, new: str, needle: str) -> None:
    task_dir = _write_fixture_task(tmp_path)
    _rewrite_metadata(task_dir, old, new)
    ok, reason = static_checks(task_dir)["metadata"]
    assert not ok
    assert needle in reason


# Covers: R6
def test_static_check_metadata_target_may_be_a_virtual_dimension(tmp_path: Path) -> None:
    """`cost`/`success` are cross-run metrics, not reward.json keys: allowed as target."""
    task_dir = _write_fixture_task(tmp_path)
    _rewrite_metadata(task_dir, 'owl_target_dimension = "security"', 'owl_target_dimension = "cost"')
    assert static_checks(task_dir)["metadata"][0]


# Covers: R8
def test_evaluate_dimensions_equal_key_set_passes() -> None:
    assert evaluate_dimensions(["reward", "f2p"], [{"f2p": 1, "reward": 1}] * 5) == (True, [])


# Covers: R8
def test_evaluate_dimensions_reports_both_directions() -> None:
    ok, reasons = evaluate_dimensions(["reward", "f2p", "ghost"], [{"reward": 1, "f2p": 1, "extra": 0}])
    assert not ok
    assert "declared only: ['ghost']" in reasons[0]
    assert "reward.json only: ['extra']" in reasons[0]


# Covers: R8
def test_evaluate_dimensions_fails_without_any_reward() -> None:
    ok, reasons = evaluate_dimensions(["reward"], [])
    assert not ok and reasons


# Covers: R31, R32
@pytest.mark.parametrize("attack", ["import-payload", "assert-patch", "forged-frame"])
def test_evaluate_cheat_in_process_attacks_need_f2p_and_p2p_zero(attack: str) -> None:
    """reward 0 alone is not enough: scope (or any other dimension) can zero the reward while the
    hole is still open, so both f2p and p2p must be 0."""
    ok, reasons = evaluate_cheat(attack, {"reward": 0, "f2p": 0, "p2p": 0}, {"reward": 0}, ["f2p", "p2p"])
    assert ok is True, reasons
    for leaked in ({"reward": 0, "f2p": 1, "p2p": 0}, {"reward": 0, "f2p": 0, "p2p": 1}):
        ok, reasons = evaluate_cheat(attack, leaked, {"reward": 0}, ["f2p", "p2p"])
        assert ok is False, leaked
        assert any("expected 0" in r for r in reasons), reasons
    ok, reasons = evaluate_cheat(attack, {"reward": 0, "p2p": 0}, {"reward": 0}, ["f2p", "p2p"])
    assert not ok and "f2p=None" in reasons[0]


# Covers: R10
def test_evaluate_cheat_hardcode_fails_loudly_without_script() -> None:
    ok, reasons = evaluate_cheat("hardcode", {"reward": 0}, {}, ["f2p"], hardcode_script_present=False)
    assert not ok
    assert "hardcode.sh missing" in reasons[0]


# --- docs/task-authoring.md must not drift from what `owl validate` enforces ------------------

_ROOT = Path(__file__).resolve().parent.parent
_AUTHORING_DOC = _ROOT / "docs" / "task-authoring.md"


def _doc_list(name: str) -> set[str]:
    """Backticked tokens inside `<!-- owl-doc:NAME --> ... <!-- /owl-doc:NAME -->` of the doc."""
    text = _AUTHORING_DOC.read_text()
    match = re.search(rf"<!-- owl-doc:{name} -->(.*?)<!-- /owl-doc:{name} -->", text, re.DOTALL)
    assert match, f"docs/task-authoring.md lacks the owl-doc:{name} block"
    return set(re.findall(r"`([^`]+)`", match.group(1)))


# Covers: R2, R5, R6, R14
def test_authoring_doc_prescriptions_match_validate_and_tasks() -> None:
    assert CANARY_GUID in _AUTHORING_DOC.read_text()
    assert _doc_list("suite_categories") == set(SUITE_CATEGORIES)
    assert _doc_list("non_suite_types") == set(NON_SUITE_TYPES)
    assert _doc_list("attacks") == set(CHEAT_ATTACKS)
    assert _doc_list("canary_globs") == {"task.toml", *_CANARY_GLOBS}

    builtin = re.search(r'_OWL_DIM_BUILTIN_KEYS="([^"]+)"', CANONICAL_LIB.read_text())
    assert builtin, "lib.sh no longer declares _OWL_DIM_BUILTIN_KEYS"
    assert _doc_list("builtin_dims") == set(builtin.group(1).split())

    # The static check names the doc lists are the ones validate really reports.
    smoke_checks = static_checks(_ROOT / "tasks" / "00-smoke")
    assert _doc_list("static_checks") == set(smoke_checks)


# Covers: R2, R6
def test_authoring_doc_format_example_passes_static_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The doc points at tasks/00-smoke as the format example: against the REAL canonical
    library (the autouse fixture swaps it out) it must pass every static check."""
    import owl.validate as validate_module

    monkeypatch.setattr(validate_module, "CANONICAL_LIB", CANONICAL_LIB)
    results = static_checks(_ROOT / "tasks" / "00-smoke")
    assert all(ok for ok, _ in results.values()), results


# Covers: R14
def test_authoring_doc_does_not_leak_the_dev_catalog() -> None:
    """The holdout author sees only this doc: no dev-task specifics may appear in it."""
    text = _AUTHORING_DOC.read_text().lower()
    forbidden = [
        "severity", "pagination", "cursor", "timezone", "idor", "idempoten", "csv", "opsdesk",
        "incident", "backup", "injected clock", "combined filter", "daily stat", "tasks/1", "tasks/2",
    ]
    assert [term for term in forbidden if term in text] == []


# --- artifacts_clear (R8, D13) --------------------------------------------------------------


@pytest.fixture
def artifact_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    import owl.validate as validate_module

    variants_dir = tmp_path / "variants-fixture"
    variants_dir.mkdir()
    (variants_dir / "x.yaml").write_text("id: x\nharness:\n  artifacts:\n    - notes/\n")
    monkeypatch.setattr(validate_module, "VARIANTS_DIR", variants_dir)
    return "notes/"


# Covers: R8
def test_artifacts_clear_fails_on_fixture_under_prefix(tmp_path: Path, artifact_prefix: str) -> None:
    task_dir = _write_fixture_task(tmp_path)
    assert static_checks(task_dir)["artifacts_clear"][0]
    (task_dir / "environment" / "app" / "notes").mkdir(parents=True)
    (task_dir / "environment" / "app" / "notes" / "todo.md").write_text("x")
    assert not static_checks(task_dir)["artifacts_clear"][0]


# Covers: R8
@pytest.mark.parametrize("line", ["+++ b/notes/x.md", "cp x /app/notes/x.md", "'notes/x.md'", "notes/x.md"])
def test_artifacts_clear_fails_on_path_named_in_patch_or_script(tmp_path: Path, artifact_prefix: str, line: str) -> None:
    task_dir = _write_fixture_task(tmp_path)
    (task_dir / "environment" / "seed.sh").write_text(line + "\n")
    assert not static_checks(task_dir)["artifacts_clear"][0]
    (task_dir / "environment" / "seed.sh").write_text("cat footnotes/x.md\n")
    assert static_checks(task_dir)["artifacts_clear"][0]


# Covers: R8
def test_artifacts_clear_holdout_reports_name_only(tmp_path: Path, artifact_prefix: str) -> None:
    task_dir = _write_fixture_task(tmp_path / "holdout", name="30-security-x", owl_holdout=True)
    (task_dir / "environment" / "seed.sh").write_text("cp x /app/notes/secret-name.md\n")
    entry = validate_task(task_dir, tmp_path, ["static"], [], holdout=True)
    assert entry["static"]["reasons"] == ["artifacts_clear"]
    assert "secret-name" not in json.dumps(entry)


# Covers: R8
def test_artifacts_clear_passes_dev_suite() -> None:

    root = Path(__file__).resolve().parent.parent / "tasks"
    for task_dir in sorted(p for p in root.iterdir() if (p / "task.toml").is_file()):
        ok, reason = static_checks(task_dir)["artifacts_clear"]
        assert ok, f"{task_dir.name}: {reason}"
