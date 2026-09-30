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
    assert Variant.load("superpowers").artifacts == [
        "docs/superpowers/specs/",
        "docs/superpowers/plans/",
    ]


# Covers: R9
def test_superpowers_declares_runtime_state() -> None:
    v = Variant.load("superpowers")
    # .superpowers/ is written by the plugin's own scripts, never an artifact (R9).
    assert v.runtime_state == [".superpowers/"]
    assert not set(v.artifacts) & set(v.runtime_state)


# Covers: R7
def test_placebo_command_appends_system_prompt() -> None:
    from pathlib import Path

    from owl import cli

    v = Variant.load("placebo")
    assert v.append_system_prompt == "Keep changes minimal and verify your work."
    cmd = cli._harbor_command(v, Path("tasks/t"), "job", Path("jobs"), "m")
    aks = [cmd[i + 1] for i, c in enumerate(cmd[:-1]) if c == "--ak"]
    assert "append_system_prompt=Keep changes minimal and verify your work." in aks


# Covers: R6, R9
def test_gentle_ai_declares_artifacts() -> None:
    v = Variant.load("gentle-ai")
    assert v.artifacts == ["odd/tasks/", "openspec/"]
    # .atl/ is harness-written state, never an artifact (R9).
    assert v.runtime_state == [".atl/"]
    assert not set(v.artifacts) & set(v.runtime_state)


# Covers: R6, R9
def test_gentle_ai_telemetry_off_in_install_and_run() -> None:
    v = Variant.load("gentle-ai")
    assert v.env == {"GENTLE_AI_TELEMETRY": "0"}
    assert v.init
    lines = [ln.strip() for ln in v.init.splitlines()]
    assert "export GENTLE_AI_TELEMETRY=0" in lines
    install = next(i for i, ln in enumerate(lines) if ln.startswith("gentle-ai install "))
    assert lines.index("export GENTLE_AI_TELEMETRY=0") < install
    assert "--agent claude-code --preset full-gentleman --scope workspace" in lines[install]
    assert "--persona" not in lines[install] and "--sdd-mode" not in lines[install]
    assert 'export CLAUDE_CONFIG_DIR="$OWL_CLAUDE_CONFIG_DIR"' in lines


# Covers: R6
def test_gentle_ai_expect_matches_real_install() -> None:
    v = Variant.load("gentle-ai")
    assert v.expect == {"plugins": ["engram"], "mcp_servers": ["context7", "engram"]}
