"""`_harbor_command` in round mode: flags common to every variant (R8, R10, R11)."""

import argparse
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from owl import cli, validate
from owl.round import Round
from owl.variants import Variant

ARTIFACTS = [".claude/progress/", "openspec/", ".gentle/"]
PLACEBO = "Keep changes minimal and verify your work."
# Per-variant options; everything else in the command must be identical across them.
OWN = {
    "vanilla-default": {},
    "placebo": {"append_system_prompt": PLACEBO},
    "navori": {"init": "navori init", "runtime_state": [".claude/x/"], "artifacts": [".claude/progress/"]},
    "superpowers": {"artifacts": ["openspec/"]},
    "gentle-ai": {"init": "gentle-ai install", "artifacts": [".gentle/"]},
    "ponytail": {"runtime_state": [".ponytail/"]},
}


def _variant(vid: str) -> Variant:
    return Variant(
        id=vid, description="", agent="claude-code", agent_version="2.1.0", raw={"id": vid}, **OWN[vid]
    )


@pytest.fixture
def rnd(tmp_path) -> Round:
    return Round(
        id="r1", dir=tmp_path, model="m", agent_version="2.1.0", variants=list(OWN),
        baseline="vanilla-default", placebo="placebo", tasks=[], prices_usd_per_mtok={},
        artifacts=list(ARTIFACTS),
        limits={
            "agent_timeout_multiplier": 3.0, "agent_setup_timeout_multiplier": 2.0,
            "max_turns": 300, "max_budget_usd": "5.00",
        },
    )


def _cmd(vid: str, rnd: Round | None) -> list[str]:
    return cli._harbor_command(_variant(vid), Path("tasks/t"), "job", Path("jobs"), "m", rnd)


def _pairs(cmd: list[str], *keys: str) -> list[str]:
    return [cmd[i + 1] for i, c in enumerate(cmd[:-1]) if c in keys]


# Covers: R8, R10, R11
def test_round_flags_identical_across_variants(rnd):
    common = ("--extra-instruction-path", "--agent-timeout-multiplier", "--agent-setup-timeout-multiplier")
    reference = None
    for vid in OWN:
        cmd = _cmd(vid, rnd)
        flags = {f: _pairs(cmd, f) for f in common}
        aks = [a for a in _pairs(cmd, "--ak") if a.startswith(("max_turns=", "max_budget_usd=", "artifacts="))]
        assert flags["--extra-instruction-path"] == [str(rnd.dir / "preamble.md")]
        assert flags["--agent-timeout-multiplier"] == ["3.0"]
        assert flags["--agent-setup-timeout-multiplier"] == ["2.0"]
        reference = reference or (flags, aks)
        assert (flags, aks) == reference
        own = [a for a in _pairs(cmd, "--ak") if a.startswith("append_system_prompt=")]
        assert own == ([f"append_system_prompt={PLACEBO}"] if vid == "placebo" else [])
    assert "--extra-instruction-path" not in _cmd("placebo", None)


# Covers: R11
def test_max_budget_is_json_string(rnd):
    assert 'max_budget_usd="5.00"' in _pairs(_cmd("vanilla-default", rnd), "--ak")
    assert "max_turns=300" in _pairs(_cmd("vanilla-default", rnd), "--ak")


# Covers: R8
def test_artifacts_union_passed_to_every_variant(rnd):
    for vid in OWN:
        assert "artifacts=" + ",".join(ARTIFACTS) in _pairs(_cmd(vid, rnd), "--ak")
    # Outside round mode the command is unchanged.
    plain = _cmd("navori", None)
    assert not any(a.startswith(("artifacts=", "max_turns=", "max_budget_usd=")) for a in _pairs(plain, "--ak"))


# Covers: R11, R13, R20
def test_round_flags_carry_all_four_limits(rnd):
    cmd = _cmd("vanilla-default", rnd)
    assert _pairs(cmd, "--agent-timeout-multiplier") == ["3.0"]
    assert _pairs(cmd, "--agent-setup-timeout-multiplier") == ["2.0"]
    aks = _pairs(cmd, "--ak")
    assert "max_turns=300" in aks and 'max_budget_usd="5.00"' in aks


# Covers: R5 (r1-refresco)
def test_default_claude_model_is_haiku_5_5():
    assert cli.DEFAULT_MODELS["claude-code"] == "anthropic/claude-haiku-5-5"
    assert cli._effective_model([_variant("vanilla-default")], None) == "anthropic/claude-haiku-5-5"


# Covers: R11 (F3 T29 A)
def test_resource_flags_only_when_declared(rnd):
    cmd = _cmd("vanilla-default", rnd)
    assert "--override-cpus" not in cmd and "--override-memory-mb" not in cmd
    rnd.limits.update(cpus=2, memory_mb=4096)
    cmd = _cmd("vanilla-default", rnd)
    assert _pairs(cmd, "--override-cpus") == ["2"]
    assert _pairs(cmd, "--override-memory-mb") == ["4096"]


# Covers: R6 (r1-refresco: the pilot runs with the round's preamble and limits, no --round)
def test_plain_run_carries_pilot_limit_flags(rnd, tmp_path):
    flags = cli._limit_flags(tmp_path / "pre.md", rnd.limits)
    cmd = cli._harbor_command(_variant("vanilla-default"), Path("tasks/t"), "job", Path("jobs"), "m",
                              limit_flags=flags)
    assert _pairs(cmd, "--extra-instruction-path") == [str(tmp_path / "pre.md")]
    assert _pairs(cmd, "--agent-timeout-multiplier") == ["3.0"]
    assert "max_turns=300" in _pairs(cmd, "--ak")
    assert not any(a.startswith("artifacts=") for a in _pairs(cmd, "--ak"))


# Covers: R10 (F3 T29 H1)
def test_harbor_telemetry_off_in_every_harbor_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HARBOR_TELEMETRY", "1")
    assert cli._auth_env("api-key", [])["HARBOR_TELEMETRY"] == "0"
    assert cli._auth_env("oauth", [_variant("vanilla-default")])["HARBOR_TELEMETRY"] == "0"

    seen = {}

    def fake_run(cmd, cwd=None, env=None, check=False):
        seen["env"] = env
        (tmp_path / "job").mkdir()

        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(validate.subprocess, "run", fake_run)
    validate._run_harbor_job({}, tmp_path, "job", 1)
    assert seen["env"]["HARBOR_TELEMETRY"] == "0"
    assert json.loads((tmp_path / "job.config.json").read_text()) == {}


def _run_args(**over):
    base = {
        "round": None, "variant": ["vanilla-default"], "model": None, "preamble": None, "limits": None,
        "auth": "api-key", "jobs_dir": "jobs", "seed": 0, "task": ["00-smoke"], "suite": False,
        "holdout": False, "k": 1,
    }
    return argparse.Namespace(**{**base, **over})


# Covers: R6 (r1-refresco)
@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"preamble": "p.md"}, "--preamble and --limits go together"),
        ({"limits": "l.yaml"}, "--preamble and --limits go together"),
        ({"round": "r1", "preamble": "p.md", "limits": "l.yaml"}, "apply only without --round"),
    ],
)
def test_run_rejects_partial_pilot_flags(over, message, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.cmd_run(_run_args(**over))
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


# Covers: R6 (r1-refresco)
def test_run_records_pilot_preamble_and_limits(monkeypatch, tmp_path, rnd):
    preamble = tmp_path / "pre.md"
    preamble.write_text("Work unattended.\n")
    limits_file = tmp_path / "limits.yaml"
    limits_file.write_text(yaml.safe_dump({"limits": rnd.limits}))
    calls = []
    monkeypatch.setattr(cli, "ensure_patient_image_for_tasks", lambda paths: None)
    monkeypatch.setattr(cli, "resolve_task_args", lambda *a: [Path("tasks/00-smoke")])
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or type("R", (), {"returncode": 0}))
    args = _run_args(preamble=str(preamble), limits=str(limits_file), jobs_dir=str(tmp_path / "jobs"))
    assert cli.cmd_run(args) == 0

    (cmd, kw), = calls
    assert _pairs(cmd, "--extra-instruction-path") == [str(preamble.resolve())]
    assert kw["env"]["HARBOR_TELEMETRY"] == "0"
    (record,) = (tmp_path / "jobs").glob("*/owl-variant.json")
    data = json.loads(record.read_text())
    assert data["preamble"] == {"path": str(preamble.resolve()),
                                "sha256": hashlib.sha256(b"Work unattended.\n").hexdigest()}
    assert data["limits"] == rnd.limits

    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"limits": {**rnd.limits, "max_turns": 0}}))
    with pytest.raises(SystemExit) as exc:
        cli.cmd_run(_run_args(preamble=str(preamble), limits=str(bad)))
    assert exc.value.code == 2
