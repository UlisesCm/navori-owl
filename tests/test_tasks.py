"""Tests for owl/tasks.py: TaskInfo, is_holdout, refuse_holdout, suite_tasks (T6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from owl.tasks import (
    NON_SUITE_TYPES,
    SUITE_CATEGORIES,
    TaskInfo,
    holdout_signals,
    is_holdout,
    refuse_holdout,
    resolve_task_args,
)


def _write_task(base: Path, name: str, *, owl_type: str = "security", owl_holdout: bool = False) -> Path:
    task_dir = base / name
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        f"""
[metadata]
owl_type = "{owl_type}"
owl_dimensions = ["reward", "f2p"]
owl_reward = ["f2p"]
owl_holdout = {"true" if owl_holdout else "false"}
"""
    )
    return task_dir


# Covers: R14, R15
def test_task_info_load_reads_metadata(tmp_path: Path) -> None:
    task_dir = _write_task(tmp_path, "16-security-x", owl_type="security")
    info = TaskInfo.load(task_dir)
    assert info.owl_type == "security"
    assert info.owl_dimensions == ["reward", "f2p"]
    assert info.owl_reward == ["f2p"]
    assert info.owl_holdout is False


# Covers: R14, R15
def test_task_info_load_missing_task_toml_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        TaskInfo.load(tmp_path / "does-not-exist")


# Covers: R14, R15
def test_is_holdout_true_by_path(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    task_dir = _write_task(holdout_root, "30-security-x", owl_holdout=False)
    assert is_holdout(task_dir) is True


# Covers: R14, R15
def test_is_holdout_true_by_metadata(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "16-security-x", owl_holdout=True)
    assert is_holdout(task_dir) is True


# Covers: R14, R15
def test_is_holdout_false_when_neither_signal(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "16-security-x", owl_holdout=False)
    assert is_holdout(task_dir) is False


# Covers: R14, R15
def test_holdout_signals_flags_incoherence(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    task_dir = _write_task(holdout_root, "30-security-x", owl_holdout=False)
    by_path, by_metadata = holdout_signals(task_dir)
    assert by_path is True
    assert by_metadata is False


# Covers: R14, R15
def test_refuse_holdout_rejects_without_flag(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    tasks_root = tmp_path / "tasks"
    holdout_task = _write_task(holdout_root, "30-security-x")
    dev_task = _write_task(tasks_root, "16-security-x")

    refused = refuse_holdout([holdout_task, dev_task], allowed=False)
    assert refused == [holdout_task]


# Covers: R14, R15
def test_refuse_holdout_accepts_with_flag(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    holdout_task = _write_task(holdout_root, "30-security-x")

    refused = refuse_holdout([holdout_task], allowed=True)
    assert refused == []


# Covers: R14, R15
def test_resolve_task_args_rejects_holdout_task_without_flag(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    holdout_task = _write_task(holdout_root, "30-security-x")

    with pytest.raises(SystemExit):
        resolve_task_args([str(holdout_task)], suite=False, holdout=False)


# Covers: R14, R15
def test_resolve_task_args_accepts_holdout_task_with_flag(tmp_path: Path) -> None:
    holdout_root = tmp_path / "holdout"
    holdout_task = _write_task(holdout_root, "30-security-x")

    result = resolve_task_args([str(holdout_task)], suite=False, holdout=True)
    assert result == [holdout_task.resolve()]


# Covers: R14, R15
def test_resolve_task_args_requires_task_or_suite() -> None:
    with pytest.raises(SystemExit):
        resolve_task_args(None, suite=False, holdout=False)


# Covers: R4, R5
def test_suite_tasks_excludes_non_suite_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import owl.tasks as tasks_module

    tasks_root = tmp_path / "tasks"
    monkeypatch.setattr(tasks_module, "TASKS_DIR", tasks_root)
    monkeypatch.setattr(tasks_module, "HOLDOUT_DIR", tmp_path / "holdout")

    smoke = _write_task(tasks_root, "00-smoke", owl_type="smoke")
    suite_task = _write_task(tasks_root, "16-security-x", owl_type="security")

    result = tasks_module.suite_tasks(include_holdout=False)
    assert smoke not in result
    assert suite_task in result


# Covers: R4, R5
def test_suite_tasks_includes_holdout_only_when_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import owl.tasks as tasks_module

    tasks_root = tmp_path / "tasks"
    holdout_root = tmp_path / "holdout"
    monkeypatch.setattr(tasks_module, "TASKS_DIR", tasks_root)
    monkeypatch.setattr(tasks_module, "HOLDOUT_DIR", holdout_root)

    dev_task = _write_task(tasks_root, "16-security-x", owl_type="security")
    holdout_task = _write_task(holdout_root, "30-security-y", owl_type="security", owl_holdout=True)

    without = tasks_module.suite_tasks(include_holdout=False)
    assert dev_task in without
    assert holdout_task not in without

    with_holdout = tasks_module.suite_tasks(include_holdout=True)
    assert dev_task in with_holdout
    assert holdout_task in with_holdout


def test_suite_categories_and_non_suite_types_disjoint() -> None:
    assert SUITE_CATEGORIES.isdisjoint(NON_SUITE_TYPES)
