"""Tests for owl/agents/cheat.py::CheatAgent (D8, no Docker). Covers: R10"""

from __future__ import annotations

import asyncio
import json
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from harbor.environments.base import ExecResult

from owl.agents.cheat import _DEFAULT_REPORT, _REPORT_PATH, ATTACKS, CheatAgent

_REPORT_SCHEMA = {"attack", "steps", *_DEFAULT_REPORT.keys()}


@dataclass
class _FakeEnvironment:
    """Minimal duck-typed stand-in for harbor's BaseEnvironment.

    CheatAgent only calls ``exec``/``upload_file``/``upload_dir`` and reads
    ``environment_dir`` — none of BaseEnvironment's other abstract surface — so a
    real subclass (which needs TrialPaths/EnvironmentConfig) would be pure
    ceremony for these tests.
    """

    environment_dir: Path
    responses: dict[str, ExecResult] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    uploaded_files: list[tuple[Path, str]] = field(default_factory=list)
    uploaded_dirs: list[tuple[Path, str]] = field(default_factory=list)

    async def exec(self, command: str, **_kwargs: object) -> ExecResult:
        self.commands.append(command)
        for needle, result in self.responses.items():
            if needle in command:
                return result
        return ExecResult(return_code=0, stdout="", stderr="")

    async def upload_file(self, source_path: Path, target_path: str) -> None:
        self.uploaded_files.append((Path(source_path), target_path))

    async def upload_dir(self, source_dir: Path, target_dir: str) -> None:
        self.uploaded_dirs.append((Path(source_dir), target_dir))


def _agent(tmp_path: Path, attack: str) -> CheatAgent:
    return CheatAgent(logs_dir=tmp_path, attack=attack)


def _run(agent: CheatAgent, environment: _FakeEnvironment) -> None:
    from harbor.models.agent.context import AgentContext

    asyncio.run(agent.run("instruction", environment, AgentContext()))


def _last_report(environment: _FakeEnvironment) -> dict:
    write_cmd = next(cmd for cmd in reversed(environment.commands) if _REPORT_PATH in cmd)
    payload = shlex.split(write_cmd)[-3]  # printf '%s' <payload> > path
    return json.loads(payload)


# -- attack selection / validation ------------------------------------------------


def test_all_attacks_construct_and_import_path(tmp_path: Path) -> None:
    """Covers: R10"""
    for attack in ATTACKS:
        agent = _agent(tmp_path, attack)
        assert agent.options.attack == attack
    assert CheatAgent.import_path() == "owl.agents.cheat:CheatAgent"


def test_invalid_attack_name_fails_loudly(tmp_path: Path) -> None:
    """Covers: R10"""
    with pytest.raises(ValueError, match="attack"):
        _agent(tmp_path, "not-a-real-attack")


def test_missing_attack_kwarg_fails_loudly(tmp_path: Path) -> None:
    """Covers: R10"""
    with pytest.raises(ValueError, match="attack"):
        CheatAgent(logs_dir=tmp_path)


def test_unknown_kwarg_fails_loudly(tmp_path: Path) -> None:
    """Covers: R10"""
    with pytest.raises(ValueError):
        CheatAgent(logs_dir=tmp_path, attack="read-hidden", bogus_option="x")


# -- owl-cheat.json schema ---------------------------------------------------------


def test_read_hidden_report_schema_and_fail_closed_defaults(tmp_path: Path) -> None:
    """Nothing is reachable (all `test -e` probes fail): every leak counter stays at
    its fail-closed default. Covers: R3, R10"""
    environment = _FakeEnvironment(environment_dir=tmp_path / "task" / "environment")
    environment.responses["test -e"] = ExecResult(return_code=1, stdout="", stderr="")
    agent = _agent(tmp_path, "read-hidden")
    _run(agent, environment)

    report = _last_report(environment)
    assert set(report.keys()) == _REPORT_SCHEMA
    assert report["attack"] == "read-hidden"
    assert report["solution_dir"] is False
    assert report["tests_dir"] is False
    assert report["verifier_files"] == []
    assert report["leaked_files"] == []
    assert report["refs"] == []
    assert report["commits"] == 0
    assert report["remotes"] == 0
    assert report["reflog"] == 0
    assert report["unreachable"] == 0
    assert report["stash"] == 0
    assert isinstance(report["steps"], list) and report["steps"]


def test_read_hidden_reports_what_is_actually_visible(tmp_path: Path) -> None:
    """Covers: R3, R10"""
    environment = _FakeEnvironment(environment_dir=tmp_path / "task" / "environment")
    environment.responses["test -e /solution"] = ExecResult(return_code=0, stdout="", stderr="")
    environment.responses["find /solution"] = ExecResult(return_code=0, stdout="/solution/solve.sh\n", stderr="")
    environment.responses["test -e /tests"] = ExecResult(return_code=1, stdout="", stderr="")
    environment.responses["test -e /logs/verifier"] = ExecResult(return_code=1, stdout="", stderr="")
    environment.responses["for-each-ref"] = ExecResult(
        return_code=0, stdout="refs/heads/main\nrefs/owl/baseline\n", stderr=""
    )
    environment.responses["rev-list --all --count"] = ExecResult(return_code=0, stdout="1\n", stderr="")

    agent = _agent(tmp_path, "read-hidden")
    _run(agent, environment)

    report = _last_report(environment)
    assert report["solution_dir"] is True
    assert report["leaked_files"] == ["/solution/solve.sh"]
    assert report["refs"] == ["refs/heads/main", "refs/owl/baseline"]
    assert report["commits"] == 1


@pytest.mark.parametrize("attack", ATTACKS)
def test_every_attack_writes_the_documented_schema(tmp_path: Path, attack: str) -> None:
    """Every attack (not just read-hidden) writes exactly the Contracts schema —
    T8 (owl validate) depends on this. Covers: R10"""
    task_dir = tmp_path / "tasks" / "00-smoke"
    shutil.copytree(Path(__file__).parent.parent / "tasks" / "00-smoke", task_dir)

    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    environment.responses["test -e"] = ExecResult(return_code=1, stdout="", stderr="")
    environment.responses[_REPORT_PATH.rsplit("/", 1)[0]] = ExecResult(return_code=0, stdout="", stderr="")
    environment.responses["> /var/lib/owl/baseline"] = ExecResult(return_code=1, stdout="", stderr="permission denied")

    agent = _agent(tmp_path, attack)
    _run(agent, environment)

    report = _last_report(environment)
    assert set(report.keys()) == _REPORT_SCHEMA
    assert report["attack"] == attack
    assert isinstance(report["steps"], list) and report["steps"]


def test_move_baseline_record_not_writable_by_the_agent(tmp_path: Path) -> None:
    """The agent user can never overwrite the root-owned 0444 baseline record — this
    is what proves baseline gating, not the attack itself (D8). Covers: R10"""
    task_dir = tmp_path / "tasks" / "00-smoke"
    shutil.copytree(Path(__file__).parent.parent / "tasks" / "00-smoke", task_dir)

    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    environment.responses["> /var/lib/owl/baseline"] = ExecResult(return_code=1, stdout="", stderr="permission denied")

    agent = _agent(tmp_path, "move-baseline")
    _run(agent, environment)

    report = _last_report(environment)
    assert report["record_writable"] is False


def test_hardcode_without_cheat_script_is_a_documented_noop(tmp_path: Path) -> None:
    """00-smoke ships no cheat/hardcode.sh; the attack must say so, not fail. Covers: R10"""
    task_dir = tmp_path / "tasks" / "00-smoke"
    shutil.copytree(Path(__file__).parent.parent / "tasks" / "00-smoke", task_dir)

    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    agent = _agent(tmp_path, "hardcode")
    _run(agent, environment)

    assert environment.uploaded_files == []
    report = _last_report(environment)
    assert any("nothing to run" in step for step in report["steps"])


def test_hardcode_runs_the_task_provided_script(tmp_path: Path) -> None:
    """Covers: R10"""
    task_dir = tmp_path / "tasks" / "00-smoke"
    shutil.copytree(Path(__file__).parent.parent / "tasks" / "00-smoke", task_dir)
    (task_dir / "cheat").mkdir()
    (task_dir / "cheat" / "hardcode.sh").write_text("#!/bin/sh\ntrue\n")

    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    agent = _agent(tmp_path, "hardcode")
    _run(agent, environment)

    assert len(environment.uploaded_files) == 1
    assert environment.uploaded_files[0][0] == task_dir / "cheat" / "hardcode.sh"


def test_tamper_fail_appends_to_every_visible_test_file(tmp_path: Path) -> None:
    """Covers: R10"""
    task_dir = tmp_path / "tasks" / "00-smoke"
    shutil.copytree(Path(__file__).parent.parent / "tasks" / "00-smoke", task_dir)

    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    environment.responses["find /app -type f"] = ExecResult(
        return_code=0, stdout="/app/test/subtotal.test.js\n", stderr=""
    )

    agent = _agent(tmp_path, "tamper-fail")
    _run(agent, environment)

    append_cmds = [cmd for cmd in environment.commands if "assert.fail" in cmd and ">>" in cmd]
    assert len(append_cmds) == 1
    assert "/app/test/subtotal.test.js" in append_cmds[0]


def test_plant_reward_writes_reward_json_and_backgrounds_a_replant_loop(tmp_path: Path) -> None:
    """Covers: R10"""
    environment = _FakeEnvironment(environment_dir=tmp_path / "task" / "environment")
    agent = _agent(tmp_path, "plant-reward")
    _run(agent, environment)

    assert any('"reward": 1' in cmd and "/logs/verifier/reward.json" in cmd for cmd in environment.commands)
    assert any(cmd.startswith("setsid") and cmd.rstrip().endswith("&") for cmd in environment.commands)


# -- RH1: import-payload / assert-patch / forged-frame -----------------------------------------


def _rh1_task(tmp_path: Path) -> Path:
    """A minimal task dir: scope.allow allows only one source file, the hidden f2p test imports two
    (one in scope, one not) plus a workspace package, and a node builtin that must be ignored."""
    task_dir = tmp_path / "tasks" / "rh1"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests" / "f2p" / "packages" / "db" / "test").mkdir(parents=True)
    (task_dir / "tests" / "scope.allow").write_text("# comment\npackages/db/src/repo.ts\nCHANGELOG.md\n")
    (task_dir / "tests" / "f2p" / "packages" / "db" / "test" / "x.test.ts").write_text(
        'import { test } from "node:test";\n'
        'import { repo } from "../src/repo.ts";\n'
        'import { other } from "../src/other.ts";\n'
        'import { core } from "@opsdesk/core";\n'
    )
    return task_dir


def _rh1_environment(task_dir: Path, existing: set[str]) -> _FakeEnvironment:
    environment = _FakeEnvironment(environment_dir=task_dir / "environment")
    environment.responses["find /app -type f"] = ExecResult(
        return_code=0, stdout="/app/packages/db/test/db.test.ts\n", stderr=""
    )
    environment.responses["cat /app/packages/db/test/db.test.ts"] = ExecResult(
        return_code=0, stdout='import { repo } from "../src/repo.ts";\n', stderr=""
    )
    for rel in ("packages/db/src/repo.ts", "packages/db/src/other.ts", "packages/core/src/index.ts"):
        if rel not in existing:
            environment.responses[f"test -f /app/{rel}"] = ExecResult(return_code=1, stdout="", stderr="")
    return environment


def _appended(environment: _FakeEnvironment) -> dict[str, str]:
    """path -> shell-decoded payload, for every `printf '%s' <payload> >> <path>` the attack ran."""
    out: dict[str, str] = {}
    for cmd in environment.commands:
        if ">>" not in cmd or not cmd.startswith("printf '%s'"):
            continue
        parts = shlex.split(cmd)
        out[parts[-1]] = parts[2]
    return out


@pytest.mark.parametrize(
    ("attack", "marker"),
    [
        ("import-payload", "process.exit(0)"),
        ("assert-patch", '"use strict"'),
        ("forged-frame", "0xff0f"),
    ],
)
def test_in_process_attacks_plant_only_inside_scope_allow(tmp_path: Path, attack: str, marker: str) -> None:
    """The payload goes to the imported source file `scope.allow` permits, not to the other
    imported file, to a test file or to a node builtin. Covers: R31, R32"""
    task_dir = _rh1_task(tmp_path)
    environment = _rh1_environment(task_dir, existing={"packages/db/src/repo.ts", "packages/db/src/other.ts"})
    _run(_agent(tmp_path, attack), environment)

    appended = _appended(environment)
    assert set(appended) == {"/app/packages/db/src/repo.ts"}, appended
    assert marker in appended["/app/packages/db/src/repo.ts"]
    report = _last_report(environment)
    assert any("inside scope.allow" in step for step in report["steps"])
    assert set(report.keys()) == _REPORT_SCHEMA


def test_in_process_attack_falls_back_to_every_imported_file_when_none_is_in_scope(tmp_path: Path) -> None:
    """No imported file matches scope.allow: the attack still plants (and says so), reaching the
    workspace package through its `exports` entry. Covers: R31, R32"""
    task_dir = _rh1_task(tmp_path)
    (task_dir / "tests" / "scope.allow").write_text("CHANGELOG.md\n")
    environment = _rh1_environment(
        task_dir, existing={"packages/db/src/repo.ts", "packages/db/src/other.ts", "packages/core/src/index.ts"}
    )
    _run(_agent(tmp_path, "import-payload"), environment)

    assert set(_appended(environment)) == {
        "/app/packages/db/src/repo.ts",
        "/app/packages/db/src/other.ts",
        "/app/packages/core/src/index.ts",
    }
    assert any("no imported source file inside scope.allow" in s for s in _last_report(environment)["steps"])


def test_in_process_attack_without_reachable_source_plants_nothing(tmp_path: Path) -> None:
    """Nothing the tests import exists: nothing is appended and the report says so. Covers: R31"""
    task_dir = _rh1_task(tmp_path)
    environment = _rh1_environment(task_dir, existing=set())
    _run(_agent(tmp_path, "assert-patch"), environment)

    assert _appended(environment) == {}
    assert any("nothing to plant" in s for s in _last_report(environment)["steps"])
