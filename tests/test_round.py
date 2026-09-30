import hashlib
import subprocess
from pathlib import Path

import pytest
import yaml

from owl import round as rnd
from owl import variants as variants_mod

PRICES = {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0}


def _variant(vdir: Path, vid: str, version: str = "1.0", artifacts: list[str] | None = None) -> None:
    harness = {"artifacts": artifacts} if artifacts else {}
    (vdir / f"{vid}.yaml").write_text(
        yaml.safe_dump({"id": vid, "agent_version": version, "harness": harness})
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path
    (root / "variants").mkdir()
    (root / "tasks" / "t1").mkdir(parents=True)
    (root / "rounds" / "r1").mkdir(parents=True)
    monkeypatch.setattr(variants_mod, "VARIANTS_DIR", root / "variants")
    _variant(root / "variants", "a", artifacts=[".claude/"])
    _variant(root / "variants", "b", artifacts=[".claude/", ".b/"])
    return root


def _write_round(root: Path, **over) -> Path:
    data = {
        "id": "r1",
        "agent_version": "1.0",
        "variants": ["a", "b"],
        "baseline": "a",
        "placebo": "b",
        "tasks": ["tasks/t1"],
        "prices_usd_per_mtok": dict(PRICES),
    }
    data.update(over)
    rdir = root / "rounds" / "r1"
    (rdir / "round.yaml").write_text(yaml.safe_dump(data))
    return rdir


# Covers: R1, R3, R4, R5
def test_load_rejects_mismatched_agent_version(env):
    _variant(env / "variants", "b", version="2.0")
    rdir = _write_round(env)
    with pytest.raises(SystemExit, match="agent_version"):
        rnd.Round.load(rdir, root=env)


# Covers: R1, R3, R4, R5
def test_load_rejects_unknown_task_or_variant(env):
    with pytest.raises(SystemExit, match="unknown task"):
        rnd.Round.load(_write_round(env, tasks=["tasks/nope"]), root=env)
    with pytest.raises(SystemExit, match="Unknown variant"):
        rnd.Round.load(_write_round(env, variants=["a", "b", "ghost"]), root=env)


# Covers: R1, R3, R4, R5
def test_load_requires_split_cache_prices(env):
    prices = {k: v for k, v in PRICES.items() if k != "cache_write_1h"}
    prices["cache_write"] = 1.25
    with pytest.raises(SystemExit, match="cache_write_1h"):
        rnd.Round.load(_write_round(env, prices_usd_per_mtok=prices), root=env)


# Covers: R1, R3, R4, R5
def test_artifacts_union(env):
    loaded = rnd.Round.load(_write_round(env), root=env)
    assert loaded.artifacts == [".claude/", ".b/"]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


# Covers: R1, R3, R4, R5
def test_dirty_tree_refused_with_paths(tmp_path, capsys):
    root = tmp_path
    for rel in ("rounds/r1/round.yaml", "tasks/t/a.txt", "owl/m.py", "elsewhere/x.txt"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    rdir = root / "rounds" / "r1"
    rnd.require_clean_tree(rdir, root)  # clean: no exit
    (root / "owl/m.py").write_text("changed")
    (root / "elsewhere/x.txt").write_text("ignored")
    (root / "tasks/t/new.txt").write_text("untracked")
    with pytest.raises(SystemExit) as exc:
        rnd.require_clean_tree(rdir, root)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "owl/m.py" in err and "elsewhere" not in err
    assert "tasks/t/new.txt" not in err  # R3: tracked paths only


# Covers: R1, R3, R4, R5
def test_round_record_hashes(tmp_path):
    root = tmp_path
    rdir = root / "rounds" / "r1"
    rdir.mkdir(parents=True)
    contents = {"RULES.md": b"rules", "round.yaml": b"id: r1\n", "preamble.md": b"pre"}
    for name, body in contents.items():
        (rdir / name).write_bytes(body)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    rec = rnd.round_record(rdir, [".claude/"], root)
    assert rec["id"] == "r1" and rec["commit"] == sha and rec["artifacts"] == [".claude/"]
    assert rec["sha256"] == {
        "rules": hashlib.sha256(b"rules").hexdigest(),
        "round": hashlib.sha256(b"id: r1\n").hexdigest(),
        "preamble": hashlib.sha256(b"pre").hexdigest(),
    }
