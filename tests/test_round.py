import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest
import yaml

from owl import round as rnd
from owl import runner
from owl import variants as variants_mod
from owl.variants import Variant

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


LIMITS = {
    "agent_timeout_multiplier": 3.0, "agent_setup_timeout_multiplier": 2.0,
    "max_turns": 300, "max_budget_usd": "5.00",
}


def _write_round(root: Path, **over) -> Path:
    data = {
        "id": "r1",
        "agent_version": "1.0",
        "variants": ["a", "b"],
        "baseline": "a",
        "placebo": "b",
        "tasks": ["tasks/t1"],
        "prices_usd_per_mtok": dict(PRICES),
        "limits": dict(LIMITS),
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


# Covers: R3
def test_dirty_paths_lists_both_sides_of_a_rename(tmp_path):
    root = tmp_path
    for rel in ("rounds/r1/round.yaml", "tasks/t/old.txt"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("same content, long enough for rename detection\n")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    _git(root, "mv", "tasks/t/old.txt", "tasks/t/new.txt")
    assert rnd.dirty_paths(root / "rounds" / "r1", root) == ["tasks/t/new.txt", "tasks/t/old.txt"]


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


# ---------------------------------------------------------------------------
# T15-T17: planner and executor (fake launcher, no harbor, no model)
# ---------------------------------------------------------------------------

def _commit_all(root: Path) -> None:
    if not (root / ".git").exists():
        _git(root, "init", "-q")
    _git(root, "add", ".")
    if subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"], check=False).returncode:
        _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")


@pytest.fixture
def plan_env(env):
    """Two variants, two dev tasks, one holdout task; a committed round dir."""
    (env / "tasks" / "t2").mkdir()
    (env / "holdout" / "h1").mkdir(parents=True)
    (env / "holdout" / "h1" / "task.toml").write_text("")
    (env / ".gitignore").write_text("jobs/\n")
    (env / "rounds" / "r1" / "RULES.md").write_text("rules")
    (env / "rounds" / "r1" / "preamble.md").write_text("Work unattended.")
    return env


def _plan_round(root: Path, **over) -> rnd.Round:
    over = {"tasks": ["tasks/t1", "tasks/t2"], "k": 3, "plan_seed": 7, "model": "claude-haiku", **over}
    loaded = rnd.Round.load(_write_round(root, **over), root=root)
    _commit_all(root)
    return loaded


# Covers: R14, R35
def test_plan_blocks_balanced(plan_env):
    round_def = _plan_round(plan_env)
    plan = rnd.plan_round(round_def, root=plan_env, holdout_dir=plan_env / "holdout")
    pairs = sorted((t, v) for t in round_def.tasks for v in round_def.variants)
    for block in (1, 2, 3):
        in_block = [(t["task"], t["variant"]) for t in plan["trials"] if t["block"] == block]
        assert sorted(in_block) == pairs
    assert [t["block"] for t in plan["trials"]] == sorted(t["block"] for t in plan["trials"])
    on_disk = json.loads((plan_env / "jobs" / "r1" / "owl-plan.json").read_text())
    assert on_disk == plan and plan["artifacts"] == [".claude/", ".b/"] and plan["round"]["id"] == "r1"


# Covers: R14, R35
def test_plan_deterministic_by_seed(plan_env):
    kw = {"root": plan_env, "holdout_dir": plan_env / "holdout"}
    first = rnd.build_plan(_plan_round(plan_env), **kw)
    assert rnd.build_plan(_plan_round(plan_env), **kw)["trials"] == first["trials"]
    other = [rnd.build_plan(_plan_round(plan_env, plan_seed=s), **kw)["trials"] for s in range(1, 6)]
    assert any(trials != first["trials"] for trials in other)


# Covers: R14, R35
def test_plan_holdout_requires_flag(plan_env):
    round_def = _plan_round(plan_env)
    kw = {"root": plan_env, "holdout_dir": plan_env / "holdout"}
    assert "holdout/h1" not in {t["task"] for t in rnd.build_plan(round_def, **kw)["trials"]}
    with_holdout = rnd.build_plan(round_def, holdout=True, **kw)["trials"]
    assert sum(t["task"] == "holdout/h1" for t in with_holdout) == 2 * 3
    listed = _plan_round(plan_env, tasks=["tasks/t1", "holdout/h1"])
    with pytest.raises(SystemExit) as exc:
        rnd.build_plan(listed, **kw)
    assert exc.value.code == 2


class FakeHarbor:
    """Stands in for `harbor run`: writes the trial a real run would leave, per a scripted outcome."""

    def __init__(self, jobs_dir: Path, outcome=None, delay: float = 0.0) -> None:
        self.jobs_dir = jobs_dir
        self.outcome = outcome or (lambda call, n: "ok")
        self.delay = delay
        self.calls: list[tuple[str, str, int, int]] = []  # (task, variant, block, attempt)
        self.jobs: list[str] = []
        self.running: list[int] = []  # block of each trial in flight
        self.peak = 0
        self.violations = 0  # launches while an earlier block still had a trial in flight
        self.lock = threading.Lock()

    def __call__(self, variant: Variant, task: Path, job_name: str) -> int:
        _, task_name, variant_id, tail = job_name.split("__")
        block, attempt = (int(x) for x in tail.replace("b", "").replace("a", "").split("-"))
        with self.lock:
            call = (task_name, variant_id, block, attempt)
            self.calls.append(call)
            self.jobs.append(job_name)
            self.violations += any(b < block for b in self.running)
            self.running.append(block)
            self.peak = max(self.peak, len(self.running))
            n = len(self.calls)
        time.sleep(self.delay)
        self._write_trial(job_name, self.outcome(call, n))
        with self.lock:
            self.running.remove(block)
        return 0

    def _write_trial(self, job_name: str, outcome: str | tuple[str, float]) -> None:
        kind, cost = outcome if isinstance(outcome, tuple) else (outcome, 0.1)
        trial = self.jobs_dir / job_name / "trial-0"
        (trial / "agent" / "sessions" / "projects" / "-app").mkdir(parents=True)
        (trial / "verifier").mkdir()
        (trial / "config.json").write_text(json.dumps({
            "task": {"path": "x"},
            "agent": {"model_name": "claude-haiku", "kwargs": {"version": "1.0", "artifacts": ".claude/,.b/",
                                              "max_turns": 300, "max_budget_usd": "5.00"}},
        }))
        user = {"type": "user", "message": {"role": "user", "content": "fix\n\nWork unattended."}}
        (trial / "agent" / "sessions" / "projects" / "-app" / "s.jsonl").write_text(json.dumps(user) + "\n")
        events: list[dict] = [{"type": "system", "subtype": "init", "plugins": [], "mcp_servers": []}]
        if kind == "usage_limit":
            events.append({"type": "rate_limit_event",
                           "rate_limit_info": {"status": "rejected", "resetsAt": 1790727000}})
        if kind == "warning":
            events.append({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning"}})
        if kind != "infra":
            events.append({"type": "result", "total_cost_usd": cost, "num_turns": 1,
                           "usage": {"input_tokens": 5}, "is_error": False})
        (trial / "agent" / "claude-code.txt").write_text("".join(json.dumps(e) + "\n" for e in events))
        reward = {"reward": 0} if kind == "fail" else {"reward": 1}
        (trial / "verifier" / "reward.json").write_text(json.dumps(reward))


def _fake(jobs_dir: Path, **kw) -> FakeHarbor:
    return FakeHarbor(jobs_dir, **kw)


def _execute(root: Path, fake: FakeHarbor, **over) -> int:
    round_def = _plan_round(root, **{"tasks": ["tasks/t1"], "k": 1, "plan_seed": 1, **over})
    variants = {v: Variant.load(v) for v in round_def.variants}
    return runner.execute_round(round_def, variants, fake, root=root, holdout_dir=root / "holdout")


# Covers: R15, R16
def test_never_exceeds_concurrency(plan_env):
    fake = _fake(plan_env / "jobs" / "r1", delay=0.05)
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=2, k=2) == 0
    assert fake.peak == 2 and len(fake.calls) == 8


# Covers: R15, R16
def test_block_barrier(plan_env):
    fake = _fake(plan_env / "jobs" / "r1", delay=0.05)
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=3, k=3) == 0
    assert fake.violations == 0
    assert [c[2] for c in fake.calls] == sorted(c[2] for c in fake.calls)
    manifest = json.loads(next((plan_env / "jobs" / "r1").glob("r1-*/owl-variant.json")).read_text())
    assert {"round", "block", "attempt", "artifacts"} <= manifest.keys()
    assert manifest["round"]["id"] == "r1" and manifest["artifacts"] == [".claude/", ".b/"]


# Covers: R15, R16
def test_excluded_retried_kept_never_retried(plan_env):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: "infra" if call[1] == "a" and call[3] < 3 else "fail")
    assert _execute(plan_env, fake, concurrency=1, retries=2, stop={"consecutive_infra": 9}) == 0
    assert sorted(c for c in fake.calls if c[1] == "a") == [("t1", "a", 1, 1), ("t1", "a", 1, 2), ("t1", "a", 1, 3)]
    assert [c for c in fake.calls if c[1] == "b"] == [("t1", "b", 1, 1)]  # a failed verdict is kept
    assert all(len(j.split("__")) == 4 and j.startswith("r1-") for j in fake.jobs)


# Covers: R17, R18, R19
def test_usage_limit_stops_and_exits_3(plan_env, capsys):
    fake = _fake(plan_env / "jobs" / "r1", outcome=lambda call, n: "usage_limit" if n == 2 else "ok")
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=1, k=2) == 3
    assert len(fake.calls) == 2
    err = capsys.readouterr().err
    assert "Resume with: owl run --round" in err and "1790727000" in err


# Covers: R17, R18, R19
def test_allowed_warning_never_stops(plan_env):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: "warning")
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=1) == 0
    assert len(fake.calls) == 4 and len(set(fake.calls)) == 4
    assert (jobs / "owl-round.log").read_text().count("rate_limit_warnings=1") == 4


# Covers: R17, R18, R19
def test_infra_streak_stops(plan_env):
    fake = _fake(plan_env / "jobs" / "r1", outcome=lambda call, n: "infra")
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=1, retries=5) == 3
    assert len(fake.calls) == 3


# Covers: R17, R18, R19
def test_usage_limit_does_not_consume_retries(plan_env):
    jobs = plan_env / "jobs" / "r1"
    first = _fake(jobs, outcome=lambda call, n: "usage_limit")
    assert _execute(plan_env, first, concurrency=1, retries=0) == 3
    second = _fake(jobs)
    assert _execute(plan_env, second, concurrency=1, retries=0) == 0
    assert len(second.calls) == 2  # the usage_limit trial re-ran (attempt 2) although retries=0
    assert first.calls[0][:3] in {c[:3] for c in second.calls}
    assert {c[3] for c in second.calls if c[:3] == first.calls[0][:3]} == {2}


# Covers: R17, R18, R19
def test_budget_projection_skips_block_exit_4(plan_env):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: ("ok", 1.0))
    assert _execute(plan_env, fake, concurrency=1, k=3, budget_usd=5) == 4
    assert {c[2] for c in fake.calls} == {1, 2}  # 4 + mean block (2) > 5: block 3 never starts
    assert (jobs / "owl-budget-stop.json").is_file()


# Covers: R17, R18, R19
def test_budget_cap_mid_block_exit_4(plan_env):
    fake = _fake(plan_env / "jobs" / "r1", outcome=lambda call, n: ("ok", 1.0))
    assert _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=1, k=2, budget_usd=3) == 4
    assert len(fake.calls) == 3


# Covers: R17, R18, R19
def test_budget_stopped_round_refuses_resume(plan_env, capsys):
    jobs = plan_env / "jobs" / "r1"
    assert _execute(plan_env, _fake(jobs, outcome=lambda call, n: ("ok", 1.0)), concurrency=1, k=2, budget_usd=1) == 4
    again = _fake(jobs)
    assert _execute(plan_env, again, concurrency=1, k=2, budget_usd=1) == 2
    assert again.calls == [] and "budget" in capsys.readouterr().err


# Covers: R17, R18, R19
def test_resume_launches_only_missing(plan_env):
    jobs = plan_env / "jobs" / "r1"
    first = _fake(jobs, outcome=lambda call, n: "usage_limit" if n == 3 else "ok")
    assert _execute(plan_env, first, tasks=["tasks/t1", "tasks/t2"], concurrency=1, k=1) == 3
    second = _fake(jobs)
    assert _execute(plan_env, second, tasks=["tasks/t1", "tasks/t2"], concurrency=1, k=1) == 0
    assert len(second.calls) == 2
    assert {c[:3] for c in first.calls[:2]} | {c[:3] for c in second.calls} == {
        (t, v, 1) for t in ("t1", "t2") for v in ("a", "b")
    }


# Covers: R17, R18, R19
def test_resume_rejects_changed_plan(plan_env, capsys):
    jobs = plan_env / "jobs" / "r1"
    assert _execute(plan_env, _fake(jobs), concurrency=1, k=1) == 0
    changed = _fake(jobs)
    assert _execute(plan_env, changed, concurrency=1, k=2) == 2
    assert changed.calls == [] and "differ" in capsys.readouterr().err



# Covers: R17, R18, R19
def test_excluded_trial_without_cost_is_retried_under_budget(plan_env):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: "infra" if n == 1 else "ok")  # infra: no result, cost unknown
    assert _execute(plan_env, fake, concurrency=1, budget_usd=100) == 0
    assert len(fake.calls) == 3  # the infra trial was retried; the round went on
    assert "cost unknown" in (jobs / "owl-round.log").read_text()
    assert not (jobs / "owl-budget-stop.json").exists()


# Covers: R17, R18, R19
def test_kept_trial_without_cost_fails_closed(plan_env, capsys):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: ("ok", None))
    assert _execute(plan_env, fake, concurrency=1, budget_usd=100) == 4
    assert len(fake.calls) == 1 and (jobs / "owl-budget-stop.json").is_file()
    assert "unknown" in capsys.readouterr().err


# Covers: R17, R18, R19
def test_budget_wins_over_usage_limit(plan_env):
    jobs = plan_env / "jobs" / "r1"
    fake = _fake(jobs, outcome=lambda call, n: ("usage_limit", 5.0))
    assert _execute(plan_env, fake, concurrency=1, budget_usd=1) == 4
    assert (jobs / "owl-budget-stop.json").is_file()


# Covers: R17, R18, R19
def test_resume_over_budget_exits_4_without_launching(plan_env):
    jobs = plan_env / "jobs" / "r1"
    assert _execute(plan_env, _fake(jobs, outcome=lambda call, n: ("ok", 1.0)), concurrency=1, k=2, budget_usd=1) == 4
    (jobs / "owl-budget-stop.json").unlink()  # as if the stop had never been recorded
    again = _fake(jobs)
    assert _execute(plan_env, again, concurrency=1, k=2, budget_usd=1) == 4
    assert again.calls == [] and (jobs / "owl-budget-stop.json").is_file()


# Covers: R15, R16
def test_launch_exception_drains_and_exits_nonzero(plan_env, capsys):
    def boom(call, n):
        if n == 2:
            raise RuntimeError("harbor vanished")
        return "ok"

    fake = _fake(plan_env / "jobs" / "r1", outcome=boom, delay=0.05)
    code = _execute(plan_env, fake, tasks=["tasks/t1", "tasks/t2"], concurrency=2)
    assert code == 1 and len(fake.calls) == 2
    err = capsys.readouterr().err
    assert "launch failed" in err and "Resume with: owl run --round" in err


# Covers: R15, R16
def test_load_rejects_non_positive_concurrency_and_streak(env):
    with pytest.raises(SystemExit, match="concurrency"):
        rnd.Round.load(_write_round(env, concurrency=0), root=env)
    with pytest.raises(SystemExit, match="consecutive_infra"):
        rnd.Round.load(_write_round(env, stop={"consecutive_infra": 0}), root=env)


# Covers: R15, R16
def test_run_without_variant_or_round_exits_2(capsys):
    from argparse import Namespace

    from owl.cli import cmd_run

    with pytest.raises(SystemExit) as exc:
        cmd_run(Namespace(round=None, variant=None))
    assert exc.value.code == 2 and "--variant" in capsys.readouterr().err


def _write_raw_round(env, **over) -> Path:
    """Write a round.yaml, dropping keys whose override is None."""
    rdir = _write_round(env)
    data = yaml.safe_load((rdir / "round.yaml").read_text())
    data.update(over)
    (rdir / "round.yaml").write_text(yaml.safe_dump({k: v for k, v in data.items() if v is not None}))
    return rdir


# Covers: R11, R13, R20
def test_load_exposes_limits(env):
    assert rnd.Round.load(_write_round(env), root=env).limits == LIMITS


# Covers: R11, R13, R20
def test_load_rejects_missing_limits(env):
    with pytest.raises(SystemExit, match="limits"):
        rnd.Round.load(_write_raw_round(env, limits=None), root=env)


# Covers: R11, R13, R20
def test_load_rejects_top_level_limits(env):
    rdir = _write_raw_round(env, limits=None, **LIMITS)
    with pytest.raises(SystemExit, match="nest them under 'limits'"):
        rnd.Round.load(rdir, root=env)


# Covers: R11, R13, R20
@pytest.mark.parametrize(
    ("patch", "match"),
    [
        ({"max_turns": None}, "missing: max_turns"),
        ({"extra": 1}, "unknown: extra"),
        ({"agent_timeout_multiplier": 0}, "agent_timeout_multiplier"),
        ({"agent_setup_timeout_multiplier": "2"}, "agent_setup_timeout_multiplier"),
        ({"max_turns": 0}, "max_turns"),
        ({"max_turns": 2.5}, "max_turns"),
        ({"max_budget_usd": 5}, "max_budget_usd"),
        ({"max_budget_usd": "abc"}, "max_budget_usd"),
        ({"max_budget_usd": "0"}, "max_budget_usd"),
    ],
)
def test_load_rejects_invalid_limits(env, patch, match):
    limits = {**LIMITS, **patch}
    limits = {k: v for k, v in limits.items() if v is not None}
    with pytest.raises(SystemExit, match=match):
        rnd.Round.load(_write_round(env, limits=limits), root=env)
