"""owl: run variants on tasks through Harbor, then gate and summarize the trials.

    owl run -v vanilla-default -v superpowers -t tasks/00-smoke -k 1
    owl gate jobs/
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from owl.gate import check_jobs, write_report
from owl.variants import ROOT, Variant

AGENT_IMPORT_PATH = "owl.agents.claude_code_harness:ClaudeCodeHarness"
DEFAULT_MODEL = "anthropic/claude-haiku-4-5-20251001"
ENV_FILE = ROOT / ".env"


def _harbor_command(variant: Variant, task: Path, job_name: str, jobs_dir: Path, model: str) -> list[str]:
    if variant.agent != "claude-code":
        raise SystemExit(f"Variant {variant.id}: agent '{variant.agent}' not supported yet (F5).")
    cmd = [
        "harbor", "run", "-p", str(task), "-a", AGENT_IMPORT_PATH, "-m", model,
        "-o", str(jobs_dir), "--job-name", job_name, "-k", "1", "-y", "-q",
        "--ak", f"variant_id={variant.id}",
    ]
    if variant.agent_version:
        cmd += ["--ak", f"version={variant.agent_version}"]
    plugin_dirs = variant.materialize_plugins()
    if plugin_dirs:
        cmd += ["--ak", "plugin_dirs=" + ",".join(str(p) for p in plugin_dirs)]
    if variant.init:
        cmd += ["--ak", f"init_command={variant.init}"]
    if variant.bare:
        cmd += ["--ak", "bare=true"]
    for key, value in variant.env.items():
        cmd += ["--ae", f"{key}={value}"]
    if ENV_FILE.is_file():
        cmd += ["--env-file", str(ENV_FILE)]
    return cmd


def _auth_env(auth: str, variants: list[Variant]) -> dict[str, str]:
    env = dict(os.environ)
    if auth == "oauth":
        bare = [v.id for v in variants if v.bare]
        if bare:
            raise SystemExit(
                f"--bare never reads CLAUDE_CODE_OAUTH_TOKEN (official docs); "
                f"run {bare} with --auth api-key."
            )
        env["CLAUDE_FORCE_OAUTH"] = "1"
    return env


def cmd_run(args: argparse.Namespace) -> int:
    variants = [Variant.load(v) for v in args.variant]
    env = _auth_env(args.auth, variants)
    jobs_dir = (ROOT / args.jobs_dir).resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    rng = random.Random(args.seed)

    for task in args.task:
        task_path = Path(task).resolve()
        # Interleave variants per repetition so API drift and prompt caching hit every arm alike.
        for rep in range(1, args.k + 1):
            order = variants[:]
            rng.shuffle(order)
            for variant in order:
                job_name = f"{stamp}__{task_path.name}__{variant.id}__r{rep}"
                print(f"▶ {job_name}", flush=True)
                cmd = _harbor_command(variant, task_path, job_name, jobs_dir, args.model)
                code = subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode
                job_dir = jobs_dir / job_name
                job_dir.mkdir(parents=True, exist_ok=True)
                (job_dir / "owl-variant.json").write_text(
                    json.dumps(
                        {**variant.raw, "model": args.model, "auth": args.auth, "harbor_exit_code": code},
                        indent=2,
                    )
                )
                if code != 0:
                    print(f"  harbor exited with {code}", file=sys.stderr)
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    jobs_dir = Path(args.jobs_dir).resolve()
    gates = check_jobs(jobs_dir)
    if not gates:
        print(f"No owl trials under {jobs_dir}")
        return 1
    for g in gates:
        status = "PASS" if g.passed else "FAIL"
        cost = f"${g.cost_usd:.4f}" if g.cost_usd is not None else "-"
        reward = g.reward.get("reward") if g.reward else "-"
        print(f"{status}  {g.variant:<18} {g.trial:<28} reward={reward} cost={cost} turns={g.num_turns} "
              f"plugins={g.plugins} mcp={g.mcp_servers}")
        for reason in g.reasons:
            print(f"      - {reason}")
    write_report(gates, jobs_dir / "owl-gate.json")
    return 0 if all(g.passed for g in gates) else 2


def main() -> None:
    parser = argparse.ArgumentParser(prog="owl")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run variants on tasks (interleaved) through Harbor.")
    run.add_argument("-v", "--variant", action="append", required=True)
    run.add_argument("-t", "--task", action="append", required=True)
    run.add_argument("-k", type=int, default=1, help="Trials per variant and task.")
    run.add_argument("-m", "--model", default=DEFAULT_MODEL)
    run.add_argument("--auth", choices=["oauth", "api-key"], default="oauth")
    run.add_argument("--jobs-dir", default="jobs")
    run.add_argument("--seed", type=int, default=0)
    run.set_defaults(func=cmd_run)

    gate = sub.add_parser("gate", help="Check contamination and model reachability of trials.")
    gate.add_argument("jobs_dir", nargs="?", default="jobs")
    gate.set_defaults(func=cmd_gate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
