"""Tests for owl/summary.py: task x variant table over gate-ok trials (R16, R17)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from owl.gate import check_jobs
from owl.summary import cmd_summary, format_f2p, summarize

# Covers: R16, R17 (whole module)


def _variant(vid: str) -> dict:
    return {"id": vid, "agent": "claude-code", "expect": {"plugins": [], "mcp_servers": []}}


def _trial(
    jobs: Path, task: str, variant: str, rep: int, reward: object | None, *, ok_log: bool = True,
    cost: float = 0.02, task_root: Path | None = None,
) -> None:
    """One job dir (one trial) shaped like `owl run` + Harbor output."""
    job = jobs / f"20260101-000000__{task}__{variant}__r{rep}"
    trial = job / f"{task}__abc{rep}"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir()
    (job / "owl-variant.json").write_text(json.dumps(_variant(variant)))
    task_path = (task_root or jobs / "tasks") / task
    (trial / "config.json").write_text(json.dumps({"task": {"path": str(task_path)}}))
    if ok_log:
        init = {"type": "system", "subtype": "init", "plugins": [], "mcp_servers": []}
        result = {"type": "result", "total_cost_usd": cost, "num_turns": 4, "usage": {"input_tokens": 9}}
        (trial / "agent" / "claude-code.txt").write_text(json.dumps(init) + "\n" + json.dumps(result) + "\n")
    if reward is not None:
        text = reward if isinstance(reward, str) else json.dumps(reward)
        (trial / "verifier" / "reward.json").write_text(text)


def _cells(jobs: Path) -> dict[tuple[str, str], object]:
    return {(c.task, c.variant): c for c in summarize(check_jobs(jobs))}


def test_aggregates_successes_and_marks_extremes(tmp_path: Path) -> None:
    _trial(tmp_path, "t-never", "v1", 1, {"reward": 0})
    _trial(tmp_path, "t-never", "v1", 2, {"reward": 0})
    _trial(tmp_path, "t-always", "v1", 1, {"reward": 1})
    _trial(tmp_path, "t-always", "v1", 2, {"reward": 1})
    _trial(tmp_path, "t-mixed", "v1", 1, {"reward": 1, "style": 0.5})
    _trial(tmp_path, "t-mixed", "v1", 2, {"reward": 0, "style": 1.0})

    cells = _cells(tmp_path)

    never, always, mixed = cells[("t-never", "v1")], cells[("t-always", "v1")], cells[("t-mixed", "v1")]
    assert (never.successes, never.n_valid, never.flag) == (0, 2, "0/k")
    assert (always.successes, always.n_valid, always.flag) == (2, 2, "k/k")
    assert (mixed.successes, mixed.n_valid, mixed.flag) == (1, 2, None)
    assert mixed.dims == {"style": 0.75}
    assert mixed.mean_cost_usd == pytest.approx(0.02)
    assert mixed.mean_turns == 4


def test_multiple_variants_are_separate_cells(tmp_path: Path) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 1})
    _trial(tmp_path, "t", "v2", 1, {"reward": 0})

    cells = _cells(tmp_path)

    assert cells[("t", "v1")].flag == "k/k"
    assert cells[("t", "v2")].flag == "0/k"


def test_excluded_trials_are_counted_not_defeats(tmp_path: Path) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 1})
    _trial(tmp_path, "t", "v1", 2, {"reward": 0}, ok_log=False)  # infra: agent never started
    _trial(tmp_path, "t", "v1", 3, {"reward": 0, "solution_hidden": 0})  # contamination

    cell = _cells(tmp_path)[("t", "v1")]

    assert (cell.successes, cell.n_valid) == (1, 1)
    assert cell.flag == "k/k"
    assert cell.excluded == {"infra": 1, "contamination": 1}


# Covers: R22, R23, R24
def test_tampered_is_kept_as_a_failure_and_listed(tmp_path: Path) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 1})
    _trial(tmp_path, "t", "v1", 2, {"reward": 0, "baseline_valid": 0})  # result event, no other reason

    cell = _cells(tmp_path)[("t", "v1")]

    assert (cell.successes, cell.n_valid, cell.tampered, cell.excluded) == (1, 2, 1, {})
    assert cell.flag is None


# Covers: R22, R23, R24
def test_baseline_invalid_with_another_reason_or_no_result_stays_excluded(tmp_path: Path) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 0, "baseline_valid": 0, "solution_hidden": 0})
    _trial(tmp_path, "t", "v1", 2, {"reward": 0, "baseline_valid": 0}, ok_log=False)

    cell = _cells(tmp_path)[("t", "v1")]

    assert (cell.n_valid, cell.tampered) == (0, 0)
    assert cell.excluded == {"contamination": 2}


# Covers: R22, R23, R24
def test_f2p_is_na_only_when_outside_the_task_reward(tmp_path: Path) -> None:
    for name, reward in (("t-with", '["f2p", "p2p"]'), ("t-without", '["p2p"]')):
        (tmp_path / "tasks" / name).mkdir(parents=True)
        (tmp_path / "tasks" / name / "task.toml").write_text(f"[metadata]\nowl_type = \"behavior\"\nowl_reward = {reward}\n")
        _trial(tmp_path, name, "v1", 1, {"reward": 1, "f2p": 0})

    cells = _cells(tmp_path)

    assert cells[("t-with", "v1")].dims["f2p"] == 0
    assert cells[("t-without", "v1")].dims["f2p"] is None
    assert format_f2p(cells[("t-without", "v1")]) == "n/a" and format_f2p(cells[("t-with", "v1")]) == "0.00"


@pytest.mark.parametrize("reward", [None, "", "{not json", "[]", '"x"', {"reward": "1"}, {}])
def test_missing_or_malformed_reward_fails_closed(tmp_path: Path, reward: object) -> None:
    _trial(tmp_path, "t", "v1", 1, reward)

    cell = _cells(tmp_path)[("t", "v1")]

    assert (cell.successes, cell.n_valid, cell.flag) == (0, 0, None)
    assert cell.excluded == {"infra": 1}


def test_cmd_summary_writes_json_and_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 0})
    out = tmp_path / "s.json"

    code = cmd_summary(argparse.Namespace(jobs_dir=[str(tmp_path)], json=str(out), holdout=False))

    assert code == 0
    assert "review (0/k)" in capsys.readouterr().out
    data = json.loads(out.read_text())
    assert data[0]["task"] == "t" and data[0]["flag"] == "0/k" and data[0]["n_valid"] == 1


def test_cmd_summary_empty_dir_returns_one(tmp_path: Path) -> None:
    assert cmd_summary(argparse.Namespace(jobs_dir=[str(tmp_path)], json=None, holdout=False)) == 1


# Covers: R14, R15
def test_holdout_refused_without_flag_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _trial(tmp_path, "30-sec", "v1", 1, {"reward": 1}, task_root=tmp_path / "holdout")
    args = argparse.Namespace(jobs_dir=[str(tmp_path)], json=None, holdout=False)

    with pytest.raises(SystemExit) as exc:
        cmd_summary(args)

    assert exc.value.code == 2
    assert "30-sec" in capsys.readouterr().err
    args.holdout = True
    assert cmd_summary(args) == 0


# Covers: R15
def test_holdout_job_without_trial_refused_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    holdout = tmp_path / "holdout"
    (holdout / "h1").mkdir(parents=True)
    monkeypatch.setattr("owl.summary.HOLDOUT_DIR", holdout)
    jobs = tmp_path / "jobs"
    job = jobs / "20260101-000000__h1__v1__r1"  # harbor failed before producing a trial
    job.mkdir(parents=True)
    (job / "owl-variant.json").write_text(json.dumps(_variant("v1")))
    args = argparse.Namespace(jobs_dir=[str(jobs)], json=None, holdout=False)

    with pytest.raises(SystemExit) as exc:
        cmd_summary(args)

    assert exc.value.code == 2
    assert str(holdout / "h1") in capsys.readouterr().err
    args.holdout = True
    assert cmd_summary(args) == 0


# Covers: R14, R15
def test_unresolvable_task_refused_fail_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _trial(tmp_path, "t", "v1", 1, {"reward": 1})
    next(tmp_path.glob("*/*/config.json")).write_text("{not json")
    args = argparse.Namespace(jobs_dir=[str(tmp_path)], json=None, holdout=False)

    with pytest.raises(SystemExit) as exc:
        cmd_summary(args)

    assert exc.value.code == 2
    assert "unresolved" in capsys.readouterr().err
    args.holdout = True
    assert cmd_summary(args) == 0


# Covers: R15
def test_holdout_refused_before_any_trial_log_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _trial(tmp_path, "30-sec", "v1", 1, {"reward": 1}, task_root=tmp_path / "holdout")

    def boom(*_: object, **__: object) -> None:
        raise AssertionError("a trial was gated")

    monkeypatch.setattr("owl.gate.check_trial", boom)
    args = argparse.Namespace(jobs_dir=[str(tmp_path)], json=None, holdout=False)

    with pytest.raises(SystemExit) as exc:
        cmd_summary(args)

    assert exc.value.code == 2
