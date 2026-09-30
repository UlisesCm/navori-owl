"""ClaudeCodeHarness.install()/run() split (design.md D6, D13) against a recording fake."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from harbor.agents.installed.claude_code import ClaudeCode

from owl.agents.claude_code_harness import ClaudeCodeHarness

SHA = "a" * 40


class FakeEnvironment:
    async def upload_dir(self, source, target) -> None:
        return None


def _make(tmp_path: Path, **kwargs) -> tuple[ClaudeCodeHarness, list[tuple[str, str, dict | None]]]:
    agent = ClaudeCodeHarness(logs_dir=tmp_path, **kwargs)
    calls: list[tuple[str, str, dict | None]] = []

    async def as_agent(environment, command, env=None, **_):
        calls.append(("agent", command, env))
        return SimpleNamespace(stdout=SHA if "rev-parse" in command else "")

    async def as_root(environment, command, env=None, **_):
        calls.append(("root", command, env))
        return SimpleNamespace(stdout="")

    agent.exec_as_agent = as_agent  # type: ignore[method-assign]
    agent.exec_as_root = as_root  # type: ignore[method-assign]
    return agent, calls


def _patch_super_install(monkeypatch: pytest.MonkeyPatch, seen: list[str]) -> None:
    async def fake(self, environment) -> None:
        seen.append("super.install")

    monkeypatch.setattr(ClaudeCode, "install", fake)


# Covers: R12
def test_install_runs_harness_steps_not_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    _patch_super_install(monkeypatch, seen)

    async def fake_run(self, instruction, environment, context) -> None:
        seen.append("super.run")

    monkeypatch.setattr(ClaudeCode, "run", fake_run)
    agent, calls = _make(tmp_path, init_command="./init.sh", runtime_state=".claude/progress/")

    asyncio.run(agent.install(FakeEnvironment()))
    assert seen == ["super.install"]
    commands = [c for _, c, _ in calls]
    assert any("./init.sh" in c for c in commands)
    assert any("variant installed" in c for c in commands)
    assert any("update-ref refs/owl/baseline" in c for c in commands)
    assert any("baseline.manifest" in c for c in commands)
    assert any(">> /var/lib/owl/ignore" in c for c in commands)

    calls.clear()
    asyncio.run(agent.run("do it", FakeEnvironment(), None))  # type: ignore[arg-type]
    assert seen == ["super.install", "super.run"]
    assert calls == []


# Covers: R12
def test_install_continues_when_claude_already_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def already(self, environment) -> bool:
        return True

    monkeypatch.setattr(ClaudeCode, "_installed_claude_satisfies_version", already)
    agent, calls = _make(tmp_path, init_command="./init.sh", artifacts="odd/")

    asyncio.run(agent.install(FakeEnvironment()))
    commands = [c for _, c, _ in calls]
    # super().install returned early (no CLI install), harness steps still ran.
    assert not any("claude-code" in c or "bootstrap.sh" in c for c in commands)
    assert any("./init.sh" in c for c in commands)
    assert any("variant installed" in c for c in commands)


# Covers: R8
def test_artifacts_appended_as_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_super_install(monkeypatch, [])
    # No init_command: the append must not depend on it.
    agent, calls = _make(tmp_path, runtime_state=".claude/.stamp", artifacts="odd/,docs/superpowers/")

    asyncio.run(agent.install(FakeEnvironment()))
    appends = [(who, c) for who, c, _ in calls if "/var/lib/owl/ignore" in c]
    assert len(appends) == 1
    who, command = appends[0]
    assert who == "root"
    for pattern in (".claude/.stamp", "odd/", "docs/superpowers/"):
        assert pattern in command


# Covers: R8, R12
def test_init_gets_config_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_super_install(monkeypatch, [])
    agent, calls = _make(tmp_path, init_command="./init.sh")

    asyncio.run(agent.install(FakeEnvironment()))
    init_calls = [(who, env) for who, c, env in calls if "./init.sh" in c]
    assert len(init_calls) == 1
    who, env = init_calls[0]
    assert who == "agent"
    assert env is not None
    assert env["OWL_CLAUDE_CONFIG_DIR"] == (agent.environment_logs_dir / "sessions").as_posix()
