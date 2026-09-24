"""Tests for owl/patient.py: patient_hash and ensure_patient_image (D3, D9).

No Docker: subprocess calls to `docker` are mocked (`monkeypatch.setattr`).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from owl.patient import (
    ensure_patient_image,
    ensure_patient_image_for_tasks,
    patient_hash,
    task_needs_patient_image,
)


def _write_patient(base: Path) -> Path:
    patient = base / "patient"
    (patient / "packages" / "core").mkdir(parents=True)
    (patient / "node_modules" / "some-dep").mkdir(parents=True)
    (patient / "data" / "tmp").mkdir(parents=True)
    (patient / "data" / "backups").mkdir(parents=True)
    (patient / "seal.sh").write_text("#!/bin/sh\necho seal\n")
    (patient / "Dockerfile").write_text("FROM node:22\n")
    (patient / "packages" / "core" / "index.ts").write_text("export const x = 1;\n")
    (patient / "node_modules" / "some-dep" / "index.js").write_text("module.exports = {};\n")
    (patient / "data" / "tmp" / ".gitkeep").write_text("")
    (patient / "data" / "backups" / "README.md").write_text("backups readme\n")
    return patient


# Covers: R1, R3
def test_patient_hash_is_stable(tmp_path: Path) -> None:
    patient = _write_patient(tmp_path)
    assert patient_hash(patient) == patient_hash(patient)


# Covers: R1, R3
def test_patient_hash_changes_when_source_changes(tmp_path: Path) -> None:
    patient = _write_patient(tmp_path)
    before = patient_hash(patient)
    (patient / "seal.sh").write_text("#!/bin/sh\necho seal changed\n")
    after = patient_hash(patient)
    assert before != after


# Covers: R1, R3
def test_patient_hash_ignores_node_modules(tmp_path: Path) -> None:
    patient = _write_patient(tmp_path)
    before = patient_hash(patient)
    (patient / "node_modules" / "some-dep" / "index.js").write_text("module.exports = { changed: true };\n")
    (patient / "node_modules" / "another-dep").mkdir(parents=True)
    (patient / "node_modules" / "another-dep" / "index.js").write_text("module.exports = {};\n")
    after = patient_hash(patient)
    assert before == after


# Covers: R1, R3
def test_patient_hash_ignores_data_scratch_dirs(tmp_path: Path) -> None:
    patient = _write_patient(tmp_path)
    before = patient_hash(patient)
    (patient / "data" / "tmp" / "scratch.db").write_text("temp\n")
    (patient / "data" / "backups" / "dump.sql").write_text("dump\n")
    (patient / "data" / "app.db").write_text("db\n")
    after = patient_hash(patient)
    assert before == after


# Covers: R1, R3
def test_ensure_patient_image_builds_when_label_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patient = _write_patient(tmp_path)
    inspect_result = MagicMock(returncode=1, stdout="")
    build_result = MagicMock(returncode=0)
    run = MagicMock(side_effect=[inspect_result, build_result])
    monkeypatch.setattr("owl.patient.subprocess.run", run)

    built = ensure_patient_image(patient)

    assert built is True
    assert run.call_count == 2
    build_cmd = run.call_args_list[1].args[0]
    assert build_cmd[:3] == ["docker", "build", "-t"]
    assert any(arg.startswith("owl.patient_hash=") for arg in build_cmd if isinstance(arg, str))


# Covers: R1, R3
def test_ensure_patient_image_skips_when_label_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patient = _write_patient(tmp_path)
    target = patient_hash(patient)
    inspect_result = MagicMock(returncode=0, stdout=f"{target}\n")
    run = MagicMock(return_value=inspect_result)
    monkeypatch.setattr("owl.patient.subprocess.run", run)

    built = ensure_patient_image(patient)

    assert built is False
    assert run.call_count == 1


# Covers: R1, R3
def test_ensure_patient_image_raises_on_build_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patient = _write_patient(tmp_path)
    inspect_result = MagicMock(returncode=1, stdout="")
    build_result = MagicMock(returncode=1)
    run = MagicMock(side_effect=[inspect_result, build_result])
    monkeypatch.setattr("owl.patient.subprocess.run", run)

    with pytest.raises(SystemExit):
        ensure_patient_image(patient)


# Covers: R3
def test_task_needs_patient_image_true_for_from_owl_patient(tmp_path: Path) -> None:
    task_dir = tmp_path / "10-example"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM owl-patient:local\nCOPY seed.patch /tmp/\n")
    assert task_needs_patient_image(task_dir) is True


# Covers: R3
def test_task_needs_patient_image_false_for_smoke_task(tmp_path: Path) -> None:
    task_dir = tmp_path / "00-smoke"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM node:22-bookworm-slim\n")
    assert task_needs_patient_image(task_dir) is False


# Covers: R3
def test_task_needs_patient_image_false_when_no_dockerfile(tmp_path: Path) -> None:
    task_dir = tmp_path / "no-env"
    task_dir.mkdir()
    assert task_needs_patient_image(task_dir) is False


# Covers: R3
def test_ensure_patient_image_for_tasks_skips_when_none_need_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke_dir = tmp_path / "00-smoke"
    (smoke_dir / "environment").mkdir(parents=True)
    (smoke_dir / "environment" / "Dockerfile").write_text("FROM node:22-bookworm-slim\n")
    called = MagicMock()
    monkeypatch.setattr("owl.patient.ensure_patient_image", called)

    ensure_patient_image_for_tasks([smoke_dir])

    called.assert_not_called()


# Covers: R3
def test_ensure_patient_image_for_tasks_runs_when_one_needs_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke_dir = tmp_path / "00-smoke"
    (smoke_dir / "environment").mkdir(parents=True)
    (smoke_dir / "environment" / "Dockerfile").write_text("FROM node:22-bookworm-slim\n")
    task_dir = tmp_path / "10-example"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM owl-patient:local\n")
    called = MagicMock()
    monkeypatch.setattr("owl.patient.ensure_patient_image", called)

    ensure_patient_image_for_tasks([smoke_dir, task_dir], patient_dir=tmp_path / "patient")

    called.assert_called_once_with(tmp_path / "patient")
