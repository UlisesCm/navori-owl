"""`_harbor_command` in round mode: flags common to every variant (R8, R10, R11)."""

from pathlib import Path

import pytest

from owl import cli
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
