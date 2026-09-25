# adae1445-7c17-496d-8a88-55bddc5019c7
#
# Base image every F2 task derives its fixture from (design.md D1, D3): built once, tagged
# owl-patient:local. A task's own environment/Dockerfile is just:
#   FROM owl-patient:local
#   COPY seed.patch /tmp/
#   RUN /opt/owl/seal.sh
#
# Digest-pinned per R1/D2 so every derived task image is byte-reproducible from the same base.
# Resolve the current digest for this tag with:
#   docker pull node:22-bookworm-slim && docker inspect --format '{{index .RepoDigests 0}}' node:22-bookworm-slim
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS base

# procps: pkill (owl_begin/owl_finish, D6.1). git: seal.sh, baseline commit. curl/jq: convenience
# for task authoring/debugging inside the container; ca-certificates: npm/npx over https (image
# build time only — no network access during a trial, D9/variants).
RUN apt-get update \
 && apt-get install -y --no-install-recommends git procps ca-certificates curl jq \
 && rm -rf /var/lib/apt/lists/*

# Verifier's own TypeScript toolchain (D6 point 6): typecheck tasks (14, 15, 17) run tsc from
# here, never from /app/node_modules — an agent that weakens or deletes the app's own tsconfig or
# node_modules must not be able to fake a passing typecheck. @types/node is pinned to the exact
# version patient/package.json ships (keep these in sync), and installed here too: with default
# typeRoots, tsc auto-includes every package under /app/node_modules/@types, which an agent
# fully controls (it's ignored runtime state — never shows up in scope) — an agent could plant an
# ambient declaration there to make a seeded type error disappear. owl_typecheck pins
# --typeRoots/--types to this directory instead, so /app/node_modules/@types is never consulted.
# Root-owned; the agent (node) can read but not write it.
RUN mkdir -p /opt/owl/toolchain \
 && npm init -y --prefix /opt/owl/toolchain >/dev/null \
 && npm install --prefix /opt/owl/toolchain --no-audit --no-fund --save-dev \
      typescript@5.7.3 @types/node@22.10.5 \
 && chmod -R go-w /opt/owl/toolchain

# /var/lib/owl: root, 0755 — the baseline record (D5) and content manifest (D6 point 3) seal.sh
# writes per task live here, outside /app, where a non-root agent can never reach them.
RUN mkdir -p /var/lib/owl && chmod 0755 /var/lib/owl

WORKDIR /app
COPY packages/ /app/packages/
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY CLAUDE.md AGENTS.md CHANGELOG.md .editorconfig .gitignore package.json tsconfig.json /app/

# One npm install for the whole workspace: only devDependency is typescript (@types/node is a
# second one, added for the workspace's own strict typecheck — see design.md D2 for why). No
# per-package installs, no lockfile drift between packages/*.
RUN npm install --no-audit --no-fund

COPY seal.sh /opt/owl/seal.sh
RUN chmod 0555 /opt/owl/seal.sh
