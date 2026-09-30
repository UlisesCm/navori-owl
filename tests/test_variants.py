"""Tests for owl/variants.py (T4): `append_system_prompt` and `artifacts` manifest fields."""

from __future__ import annotations

from pathlib import Path

import pytest

import owl.variants as variants_module
from owl.variants import Variant


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "variants").mkdir()
    (tmp_path / "patient" / "docs" / "guides").mkdir(parents=True)
    (tmp_path / "patient" / "docs" / "guides" / "a.md").write_text("x")
    monkeypatch.setattr(variants_module, "VARIANTS_DIR", tmp_path / "variants")
    monkeypatch.setattr(variants_module, "PATIENT_DIR", tmp_path / "patient")
    return tmp_path


def _write(repo: Path, harness: str) -> None:
    (repo / "variants" / "v.yaml").write_text(f"id: v\nharness:\n{harness}")


# Covers: R7, R8, R9
def test_append_system_prompt_field_loads(fake_repo: Path) -> None:
    _write(fake_repo, "  append_system_prompt: Keep changes minimal.\n  artifacts:\n    - notes/\n")
    v = Variant.load("v")
    assert v.append_system_prompt == "Keep changes minimal."
    assert v.artifacts == ["notes/"]
    _write(fake_repo, "  bare: true\n")
    v = Variant.load("v")
    assert v.append_system_prompt is None and v.artifacts == []


# Covers: R7, R8, R9
@pytest.mark.parametrize(
    "prefix", ["notes", "packages/core/", "docs/guides/"], ids=["no-slash", "under-packages", "patient-file"]
)
def test_artifacts_prefix_rules(fake_repo: Path, prefix: str) -> None:
    _write(fake_repo, f"  artifacts:\n    - {prefix}\n")
    with pytest.raises(SystemExit, match="artifacts prefix"):
        Variant.load("v")


# Covers: R7, R8, R9
def test_navori_progress_is_artifact() -> None:
    v = Variant.load("navori")
    assert ".claude/progress/" in v.artifacts
    assert ".claude/progress/" not in v.runtime_state
    assert ".claude/worktrees/" in v.runtime_state


# Covers: R7, R8, R9
def test_superpowers_declares_artifacts() -> None:
    assert Variant.load("superpowers").artifacts == ["docs/superpowers/"]
