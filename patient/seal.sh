#!/bin/bash
# adae1445-7c17-496d-8a88-55bddc5019c7
#
# Common fixture seal (design.md D3), baked into owl-patient:local at /opt/owl/seal.sh (root,
# 0555). Every F2 task's environment/Dockerfile is just:
#   FROM owl-patient:local
#   COPY seed.patch /tmp/
#   RUN /opt/owl/seal.sh
# tasks/00-smoke keeps its own inline Dockerfile RUN steps (design.md D3/D6, "Centralization"
# note below) instead of calling this: it isn't FROM owl-patient:local, so it has no /opt/owl/
# to call into.
#
# Order matters and mirrors tasks/00-smoke/environment/Dockerfile exactly, generalized to an
# optional seed.patch:
#   1. apply /tmp/seed.patch if present (atomic; leaves no .orig/.rej) and delete it
#   2. git init + single commit ("fixture")
#   3. refs/owl/baseline -> that commit
#   4. /var/lib/owl/{baseline,ignore,baseline.manifest}, root, 0444
#   5. chown -R node:node /app
#   6. reflog expire + gc --prune=now (no history to recover a solution from, R3)
set -euo pipefail

cd /app

# BuildKit's copy/snapshot machinery can leave /app owned by a uid that doesn't match the build
# step's effective uid even though both report as root inside the container (observed on
# OrbStack's builder) — git's ownership check trips on that mismatch. Every task built FROM
# owl-patient:local calls this script, always as root, always against a path it just received
# via COPY/FROM, so this is safe unconditionally (never widens what an agent, who never runs
# seal.sh, can reach).
git config --global --add safe.directory /app

if [ -f /tmp/seed.patch ]; then
  git apply --whitespace=nowarn /tmp/seed.patch
  rm -f /tmp/seed.patch
fi

git init -q -b main
git -c user.name=owl -c user.email=owl@localhost add -A
git -c user.name=owl -c user.email=owl@localhost commit -q -m "fixture"
git update-ref refs/owl/baseline HEAD

mkdir -p /var/lib/owl
git rev-parse refs/owl/baseline > /var/lib/owl/baseline
chmod 0444 /var/lib/owl/baseline

touch /var/lib/owl/ignore
if [ -f /app/.gitignore ]; then
  cat /app/.gitignore > /var/lib/owl/ignore
fi
chmod 0444 /var/lib/owl/ignore

# CANONICAL ALGORITHM: must compute byte-identical output to owl_snapshot() in
# owl/verifier/lib.sh and to ClaudeCodeHarness._SNAPSHOT_CMD (owl/agents/claude_code_harness.py)
# — see owl_snapshot's docstring for the full rationale (content-only, no git, newline-safe,
# fails closed). Centralization note (design.md D3/D6): this is a fourth call site for the same
# algorithm as far as *tasks derived from owl-patient:local* are concerned, but it does not add a
# fourth copy to the drift surface the existing parity test
# (tests/test_validate_docker.py::test_three_snapshot_copies_are_byte_identical) guards: that
# test is specific to tasks/00-smoke, which never goes through seal.sh (it isn't FROM
# owl-patient:local and has no /opt/owl/ to call into) — its Dockerfile keeps its own inline copy,
# unchanged by T4. For every task built from owl-patient:local (T9 onward), seal.sh is the *only*
# build-time copy (replacing what would otherwise be a fifth per-task Dockerfile RUN step, one per
# task); tests/patient_sealed (tests/test_validate_docker.py, -m docker) checks its output against
# a fresh run of owl_snapshot from the real owl/verifier/lib.sh, so drift between this script and
# the canonical function is still regression-tested, just via a different pair of call sites than
# 00-smoke's test targets.
rm -f /var/lib/owl/baseline.manifest
T=0
nl() { [ "$(printf '%s' "$1" | wc -l)" = 0 ]; }
: > /var/lib/owl/baseline.manifest
while IFS= read -r -d '' f; do
  nl "$f" || { T=1; continue; }
  m=$(stat -c '%a' "$f" 2>/dev/null) || continue
  h=$(sha256sum "$f" 2>/dev/null) || continue
  h=${h%% *}
  printf 'F\t%s\t%s\t%s\n' "$m" "$h" "$f" >> /var/lib/owl/baseline.manifest
done < <(find /app -path /app/.git -prune -o -type f -print0 2>/dev/null)
while IFS= read -r -d '' f; do
  nl "$f" || { T=1; continue; }
  t=$(readlink "$f" 2>/dev/null) || continue
  nl "$t" || { T=1; continue; }
  printf 'L\t%s\t%s\n' "$t" "$f" >> /var/lib/owl/baseline.manifest
done < <(find /app -path /app/.git -prune -o -type l -print0 2>/dev/null)
while IFS= read -r -d '' f; do
  nl "$f" || { T=1; continue; }
  ft=$(stat -c '%F' "$f" 2>/dev/null) || continue
  printf 'O\t%s\t%s\n' "$ft" "$f" >> /var/lib/owl/baseline.manifest
done < <(find /app -path /app/.git -prune -o \( -type p -o -type s -o -type c -o -type b \) -print0 2>/dev/null)
LC_ALL=C sort -o /var/lib/owl/baseline.manifest /var/lib/owl/baseline.manifest
if [ "$T" != 0 ]; then
  echo "seal.sh: a path under /app could not be safely snapshotted (embedded newline); failing the build" >&2
  exit 1
fi
chmod 0444 /var/lib/owl/baseline.manifest

chown -R node:node /app

git reflog expire --expire=now --all
git gc -q --prune=now
