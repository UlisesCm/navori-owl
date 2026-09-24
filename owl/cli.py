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

AGENT_IMPORT_PATHS = {
    "claude-code": "owl.agents.claude_code_harness:ClaudeCodeHarness",
    "codex": "codex",
}
DEFAULT_MODELS = {
    "claude-code": "anthropic/claude-haiku-4-5-20251001",
    "codex": "openai/gpt-6-luna",
}
ENV_FILE = ROOT / ".env"


def _harbor_command(variant: Variant, task: Path, job_name: str, jobs_dir: Path, model: str) -> list[str]:
    if variant.agent not in AGENT_IMPORT_PATHS:
        raise SystemExit(f"Variant {variant.id}: agent '{variant.agent}' not supported yet (F5).")
    if variant.agent == "codex" and (variant.plugins or variant.init or variant.bare):
        raise SystemExit(
            f"Variant {variant.id}: harness plugins/init/bare are not supported for agent 'codex' yet (F5)."
        )
    cmd = [
        "harbor", "run", "-p", str(task), "-a", AGENT_IMPORT_PATHS[variant.agent], "-m", model,
        "-o", str(jobs_dir), "--job-name", job_name, "-k", "1", "-y", "-q",
    ]
    if variant.agent == "claude-code":
        # variant_id is a kwarg only ClaudeCodeHarness accepts (harbor agent schema claude-code);
        # Harbor's built-in codex agent rejects unknown kwargs. Variant identity is already
        # recorded in owl-variant.json regardless, so it's fine to drop for other agents.
        cmd += ["--ak", f"variant_id={variant.id}"]
    if variant.agent_version:
        cmd += ["--ak", f"version={variant.agent_version}"]
    if variant.agent == "claude-code":
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
        if any(v.agent == "claude-code" for v in variants):
            env["CLAUDE_FORCE_OAUTH"] = "1"
        codex_variants = [v.id for v in variants if v.agent == "codex"]
        if codex_variants:
            auth_json = Path.home() / ".codex" / "auth.json"
            if not auth_json.is_file():
                raise SystemExit(
                    f"--auth oauth for {codex_variants}: {auth_json} not found. "
                    f"Log in with `codex login` (ChatGPT plan) first, or run with --auth api-key."
                )
            env["CODEX_FORCE_AUTH_JSON"] = "1"
    return env


def _effective_model(variants: list[Variant], model: str | None) -> str:
    agents = {v.agent for v in variants}
    if model is not None:
        if len(agents) > 1:
            raise SystemExit(
                f"-m/--model was given explicitly but variants mix agents {sorted(agents)}: "
                f"a model belongs to one provider. Run each agent's variants separately."
            )
        return model
    if len(agents) > 1:
        raise SystemExit(
            f"variants mix agents {sorted(agents)} with no explicit -m/--model: "
            f"pass -m or run each agent's variants separately (default models differ per provider)."
        )
    return DEFAULT_MODELS[next(iter(agents))]


def cmd_run(args: argparse.Namespace) -> int:
    variants = [Variant.load(v) for v in args.variant]
    model = _effective_model(variants, args.model)
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
                cmd = _harbor_command(variant, task_path, job_name, jobs_dir, model)
                code = subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode
                job_dir = jobs_dir / job_name
                job_dir.mkdir(parents=True, exist_ok=True)
                (job_dir / "owl-variant.json").write_text(
                    json.dumps(
                        {**variant.raw, "model": model, "auth": args.auth, "harbor_exit_code": code},
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
              f"plugins={g.plugins} builtin_plugins={g.builtin_plugins} mcp={g.mcp_servers}")
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
    run.add_argument(
        "-m", "--model", default=None,
        help=f"Overrides the agent's default (claude-code: {DEFAULT_MODELS['claude-code']}, "
             f"codex: {DEFAULT_MODELS['codex']}). Required if -v mixes agents.",
    )
    run.add_argument(
        "--auth", choices=["oauth", "api-key"], default="oauth",
        help="oauth = your subscription (Claude Code / ChatGPT plan login); api-key = ANTHROPIC_API_KEY / OPENAI_API_KEY.",
    )
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
