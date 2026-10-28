# navori:managed start id="pr-publisher-confirm-base" hash="3085c571" version="0.12.3" source="@navori/core"
#!/usr/bin/env bash
#
# PreToolUse(Bash): a `gh pr create` that did NOT come from the
# `publisher` is raised to a user confirmation.
#
# WHY (#705): the publisher is the single owner of commit+PR, and it is invoked on
# 15% of the PRs this harness opens. The rate is not uniform — one park repo
# runs at 48%, and the repo that PUBLISHES the publisher sat at 0 of 101. The
# confound was checked and does not hold: in the sessions where subagents were
# demonstrably available and used, the publisher was still never called. The publisher
# is not skipped; its antechamber is never entered, because `gh pr create` falls
# out of whatever the main agent was already doing and nothing interrupts it.
#
# So this hook interrupts, and does no more than that. It does NOT block: a
# session where the operator forbids subagents has no way to reach the publisher,
# and a hook that made PRs impossible there would be worse than the deviation it
# corrects. `ask` keeps the decision with the human while removing the one thing
# measured to fail — a layer that only suggests.
set -euo pipefail

# Command extraction (payload → $cmd). Shared body, single source of truth.
nv_payload_fields="agent_id subagent_id tool_input.command"
payload_load() { :; }
# Shared hook boilerplate — inlined into each hook at render time (see the
# include directive in the source scripts + lib/render/hook-includes.ts). Single source
# of truth for the sibling gate scripts; DO NOT copy this body back into a hook
# by hand (that is the drift #225/#261 removed).
#
# PreToolUse(Bash) passes the tool input on stdin. Read one field out of it
# WITHOUT hard-depending on jq (NOT preinstalled on macOS): try jq, then node
# (Claude Code's own runtime), then a best-effort sed unwrap on the leaf key.
# Nothing extracted → empty output, and each caller decides what that means (the
# gate scripts scan defensively; guard-destructive waves the command through).
#
# $1 is a dotted path written HERE, never user input — the payload is the data.
# Generic on purpose: `.cwd` feeds the worktree resolver of #454 through the
# SAME hardened cascade instead of a second copy of it.
#
# The sed fallback reads a JSON string through its first unescaped quote. JSON
# object member order is not a host contract: `command` can precede `cwd`, so a
# greedy capture to the last quote would swallow the rest of the payload when
# neither jq nor node is available.
# `${payload-$(cat)}` (unset test, not `:-`) rather than an unconditional
# `payload=$(cat)`: a caller that already captured stdin itself (spec 0035 —
# `managed-drift-watch.sh` needs the audit recorder's session_id/cwd even on
# tool names this hook does not otherwise read) keeps that value, empty or
# not, instead of this partial re-reading an already-drained pipe and
# clobbering it with "".
payload=${payload-$(cat)}
payload_field() {
  case "$1" in "" | *[!A-Za-z0-9_.]*) ;; *)
    if [ "${_nv_pf_loaded:-0}" = 1 ] && [ "$payload" = "${_nv_pf_src:-}" ]; then
      case " ${nv_payload_fields:-} " in *" $1 "*)
        # ast-grep-ignore: no-bash-eval — D3 reads only a variable name built from the validated literal path; payload values are never eval input.
        eval 'printf "%s\n" "${_nv_pf_'"${1//./__}"'-}"'
        return 0
        ;;
      esac
    fi
    ;;
  esac
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r ".$1 // empty" 2>/dev/null && return 0
  fi
  if command -v node >/dev/null 2>&1; then
    printf '%s' "$payload" | node -e 'let s="";const p=process.argv[1].split(".");process.stdin.on("data",c=>s+=c).on("end",()=>{try{let v=JSON.parse(s);for(const k of p)v=v?.[k];process.stdout.write(String(v??""))}catch{}})' "$1" 2>/dev/null && return 0
  fi
  printf '%s' "$payload" | sed -nE "s/.*\"${1##*.}\"[[:space:]]*:[[:space:]]*\"(([^\"\\]|\\.)*)\".*/\\1/p"
}
extract_cmd() {
  payload_field tool_input.command
}

# payload_fields VAR=path… — several fields, ONE process (spec 0054 R22, D10).
# Each `payload_field` call forks a subshell plus jq/node; a hook that needs two
# or more fields up front pays that per field. Here a single jq (or node) emits
# every field followed by a NUL and closes with the sentinel `END` NUL.
#
# NEVER SHIFTS A FIELD (challenge B3). `tool_input.command` is model-controlled,
# and JSON `\u0000` decodes to a NUL byte, which would end that field early and
# slide the next value (`cwd`, `session_id`, a role) into the wrong variable. So
# the producer REFUSES to emit anything when any value holds a NUL, and the shell
# reads exactly N fields plus the sentinel with nothing after it. Any anomaly —
# a NUL, a missing or extra field, empty output for a non-empty payload, a
# producer that failed — discards the whole read and repeats it field by field
# with `payload_field`, i.e. exactly today's behaviour. A variable is never left
# empty "because the read went wrong" (that would read as "allowed").
#
# Values match `$(payload_field …)`: trailing newlines stripped, `null` and
# `false` empty, non-strings as compact JSON. Paths are dotted and written HERE,
# never user input. Works under bash 3.2 and zsh: no arrays, `printf -v` to assign.
_payload_fields_read() {
  local _pf_spec _pf_val _pf_end _pf_extra
  for _pf_spec in "$@"; do
    IFS= read -r -d '' _pf_val || return 1
    # Suffix removal is quadratic in bash even without a newline. Only values
    # ending in one need command substitution's native trailing-newline trim.
    case "$_pf_val" in *$'\n') _pf_val=$(printf '%s' "$_pf_val") ;; esac
    printf -v "${_pf_spec%%=*}" '%s' "$_pf_val" || return 1
  done
  IFS= read -r -d '' _pf_end || return 1
  [ "$_pf_end" = END ] || return 1
  if IFS= read -r -d '' _pf_extra; then return 1; fi
  [ -z "$_pf_extra" ] || return 1
  return 0
}
payload_fields() {
  local _pf_spec _pf_filter="" _pf_paths="" _pf_cached=1
  [ "$#" -gt 0 ] || return 0
  for _pf_spec in "$@"; do
    case " ${nv_payload_fields:-} " in *" ${_pf_spec#*=} "*) ;; *) _pf_cached=0 ;; esac
  done
  if [ "$_pf_cached" = 1 ] && [ "${_nv_pf_loaded:-0}" = 1 ] && [ "$payload" = "${_nv_pf_src:-}" ]; then
    for _pf_spec in "$@"; do
      printf -v "${_pf_spec%%=*}" '%s' "$(payload_field "${_pf_spec#*=}")"
    done
    return 0
  fi
  if [ -z "$payload" ]; then
    for _pf_spec in "$@"; do printf -v "${_pf_spec%%=*}" '%s' ""; done
    return 0
  fi
  for _pf_spec in "$@"; do
    _pf_filter="$_pf_filter(.${_pf_spec#*=}? // \"\" | tostring),"
    _pf_paths="$_pf_paths ${_pf_spec#*=}"
  done
  _pf_filter="[${_pf_filter%,}] as \$v | if all(\$v[]; any(explode[]; . == 0) | not) then (\$v[] | ., \"\\u0000\"), \"END\\u0000\" else empty end"
  if command -v jq >/dev/null 2>&1; then
    _payload_fields_read "$@" < <(printf '%s' "$payload" | jq -j "$_pf_filter" 2>/dev/null) && return 0
  fi
  if command -v node >/dev/null 2>&1; then
    _payload_fields_read "$@" < <(printf '%s' "$payload" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{try{const j=JSON.parse(s);let o="";for(const p of process.argv[1].trim().split(" ")){let v=j;for(const k of p.split("."))v=v?.[k];const t=v==null||v===false?"":typeof v==="string"?v:JSON.stringify(v);if(t.includes("\0"))return;o+=t+"\0"}process.stdout.write(o+"END\0")}catch{}})' "$_pf_paths" 2>/dev/null) && return 0
  fi
  for _pf_spec in "$@"; do
    printf -v "${_pf_spec%%=*}" '%s' "$(payload_field "${_pf_spec#*=}")"
  done
  return 0
}

# Spec 0055 D3: load once in the parent shell, inherited by command substitutions.
# Only literal, validated paths form variable names; payload values are never eval'd.
# Keep the old cache ineligible while loading, including its per-field fallback.
payload_load() {
  [ "${_nv_pf_loaded:-0}" = 1 ] && [ "$payload" = "${_nv_pf_src:-}" ] && return 0
  local _pl_path
  [ -z "${ZSH_VERSION:-}" ] || setopt local_options sh_word_split
  set --
  for _pl_path in ${nv_payload_fields:-}; do
    case "$_pl_path" in "" | *[!A-Za-z0-9_.]*) return 1 ;; esac
    set -- "$@" "_nv_pf_${_pl_path//./__}=$_pl_path"
  done
  _nv_pf_loaded=0
  payload_fields "$@"
  _nv_pf_src=$payload
  _nv_pf_loaded=1
}
# NOT called here on purpose. `payload_field` may spawn a process, and
# `routing-watch.sh` — which includes this partial and runs after EVERY tool call
# in every session — never reads `cmd`. Each consumer that wants it calls
# `extract_cmd` itself, at the point where it already knows it needs it.

# Gate to `gh pr create` only. $TRIGGER_RE is consumed by the shared detector
# inlined below, which splits compound commands on && || ; | and matches at a
# segment START — so `git push … && gh pr create …` is caught and an
# `echo "gh pr create"` is not.
TRIGGER_RE='^gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$)'
# Literal substring every branch of $TRIGGER_RE needs, read by the fast path in
# the shared detector (spec 0016). `create` rather than `gh`: both are necessary
# conditions, and the rarer one skips the fork on more commands. Keep NEXT to
# the regex — a branch added there without its token here loses the shortcut.
TRIGGER_TOKENS='create'
# Shared gate detector — inlined into each hook at render time (see the include
# directive in the source scripts + lib/render/hook-includes.ts). The caller MUST set
# $TRIGGER_RE (an ERE) before the include; it decides which git ops this hook
# gates. Single source of truth for the FIX B/C wrapper-peeling logic; DO NOT
# copy this body into a hook by hand.
#
# Detect whether $1 (a possibly-compound command) invokes a gated operation.
# Splits $1 on the shell separators && || ; | and newlines, strips leading
# whitespace plus wrapper words (`(`, `\`, `command `) and `VAR=value` env
# prefixes from each segment, and returns 0 if ANY segment STARTS with a gated
# `git …` invocation on a word boundary (matched by $TRIGGER_RE). Replaces
# literal-prefix `case` matching, which silently skipped the gate for
# `cd x && git commit`, `echo y; git push`, or a leading space (#88: NEVER skip
# the gate silently). Matching a segment START means a quoted `echo "git commit"`
# does NOT trigger it. Known limitation: it cannot see through `sh -c`, `eval`,
# or obfuscation — a seatbelt, not a sandbox.
#
# Heredoc bodies (#1095): when the caller sets TRIGGER_STRIP_HEREDOC_BODIES=1,
# the body of a `cat <<TAG … TAG` heredoc is DATA, not commands, so a
# `git commit` line inside e.g. a `gh issue create --body "$(cat <<'EOF' …`
# no longer counts. It is an ALLOW-list on purpose: only a `cat` heredoc (bare,
# or inside `$(…)` of gh/git/echo/printf) with nothing chained after it is
# stripped; anything else — `bash <<EOF`, `while read c; do $c; done <<EOF`,
# `cat <<EOF | sh`, `python - <<EOF` — keeps its body, because a shell or
# interpreter may execute it. Opt-in because master-accept-confirm matches
# unanchored and must keep seeing bodies fed to a non-shell interpreter.
# The fast path on its own, so a caller can apply it EARLIER than the segment
# scan — before it has even paid to extract the command from the payload.
#
# Returns 0 when $1 may contain a gated operation, 1 when it provably cannot.
# The argument is the one the block below spells out: no $TRIGGER_RE can match
# without one of the caller's literal TOKENS appearing in the segment it
# matches, and every segment is a substring of the input. So the absence of
# every token is proof that no segment can match — and the same proof holds one
# level up, over the raw PAYLOAD the command was extracted from: JSON escaping
# touches `"`, `\` and control characters, never the letters of a token.
#
# Disarms when $TRIGGER_TOKENS is unset: with no tokens declared there is
# nothing to prove absent, so it answers "maybe" and the caller does the work.
# Fail-open to the SLOW path, never to a skip.
has_trigger_token() {
  [ -n "${TRIGGER_TOKENS:-}" ] || return 0
  # Token iteration goes through newline-split + `read`, NOT `for _tok in
  # $TRIGGER_TOKENS`: zsh does not word-split an unquoted expansion, so the
  # `for` form iterated ONCE with the whole list as a single token there — and
  # a token that can never match is a gate that never fires. Caught by the
  # bash×zsh differential suite.
  local _input="$1" _tok _nl=$'\n'
  local _toks="${TRIGGER_TOKENS// /$_nl}"
  while IFS= read -r _tok; do
    [ -n "$_tok" ] || continue
    case "$_input" in *"$_tok"*) return 0 ;; esac
  done <<< "$_toks"
  return 1
}

# Words that let a later part of a command re-enter git, the cwd or a shell.
# Text is reduced to alphanumeric words first, so `/usr/bin/git` and `(cd` match.
navori_mentions_shellish() {
  local t=" ${1//[!A-Za-z0-9_]/ } "
  case "$t" in
    *" git "*|*" cd "*|*" pushd "*|*" popd "*|*" sh "*|*" bash "*|*" zsh "*|*" dash "*|*" ksh "*) return 0 ;;
    *" env "*|*" eval "*|*" exec "*|*" command "*|*" builtin "*|*" source "*|*" xargs "*) return 0 ;;
  esac
  return 1
}

# Sets `navori_heredoc_stripped` to $1 minus the bodies (and terminators) of
# heredocs this hook may safely treat as data; the introducing line is KEPT, so
# `git commit -F - <<'EOF'` still triggers. Any doubt (second heredoc on the
# line, unterminated body, empty tag) leaves the text untouched: fail closed.
# All locals are declared once at the top: zsh prints a re-declared `local`.
navori_strip_heredoc_bodies() {
  local input="$1" line before rest seg pre pfirst tag after cmp="" out="" r=""
  local dash=0 inbody=0 tab=$'\t' nl=$'\n'
  navori_heredoc_stripped="$input"
  case "$input" in *'<<'*) ;; *) return 0 ;; esac
  while IFS= read -r line; do
    if [ "$inbody" = 1 ]; then
      cmp="$line"
      if [ "$dash" = 1 ]; then cmp="${cmp#"${cmp%%[!$tab]*}"}"; fi
      if [ "$cmp" = "$tag" ]; then inbody=0; fi
      continue
    fi
    out="$out$line$nl"
    case "$line" in *'<<'*) ;; *) continue ;; esac
    before="${line%%<<*}"
    rest="${line#*<<}"
    case "$rest" in '<'*) continue ;; esac                  # here-string: no body
    dash=0
    case "$rest" in -*) dash=1; rest="${rest#-}" ;; esac
    rest="${rest#"${rest%%[![:space:]]*}"}"
    tag=""; after=""
    case "$rest" in
      \'*) r="${rest#\'}"; case "$r" in *\'*) tag="${r%%\'*}"; after="${r#*\'}" ;; esac ;;
      \"*) r="${rest#\"}"; case "$r" in *\"*) tag="${r%%\"*}"; after="${r#*\"}" ;; esac ;;
      \\*) r="${rest#\\}"; tag="${r%%[!A-Za-z0-9_.-]*}"; after="${r#"$tag"}" ;;
      *) tag="${rest%%[!A-Za-z0-9_.-]*}"; after="${rest#"$tag"}" ;;
    esac
    [ -n "$tag" ] || continue
    # Nothing chained after the tag, and no second heredoc on the line.
    case "$after" in *'|'*|*';'*|*'&'*|*'<<'*) continue ;; esac
    # The word before `<<` must be `cat`. Inside `$(…)`/backticks the command
    # that receives cat's output must be a known data consumer, not an
    # interpreter (`bash -c "$(cat <<EOF`, `eval "$(cat <<EOF`).
    seg="$before"
    case "$before" in
      *'$('*) seg="${before##*\$\(}"; pre="${before%\$\(*}" ;;
      *'`'*) seg="${before##*\`}"; pre="${before%\`*}" ;;
      *) pre="" ;;
    esac
    if [ -n "$pre" ]; then
      pre="${pre##*&&}"; pre="${pre##*;}"; pre="${pre##*|}"
      pre="${pre#"${pre%%[![:space:]]*}"}"
      pfirst="${pre%%[[:space:]]*}"
      case "$pfirst" in gh|git|echo|printf) ;; *) continue ;; esac
    fi
    seg="${seg#"${seg%%[![:space:]]*}"}"
    case "$seg" in *'|'*|*';'*|*'&'*) continue ;; esac
    case "$seg" in cat|cat[[:space:]]*) ;; *) continue ;; esac
    inbody=1
  done <<< "$input"
  [ "$inbody" = 0 ] || return 0                             # unterminated: keep all
  navori_heredoc_stripped="$out"
  return 0
}

# Counts the segments of $1 that start with a gated op ($TRIGGER_RE); sets the
# global `navori_trigger_hits`. `$2` = 1 stops at the first hit (is_scan_trigger
# only needs "any"). The single home of the segment normalisation, shared with
# navori_commit_landing so the two can never disagree about what a segment is.
navori_count_triggers() {
  # Pre-expanded newline: zsh does NOT expand $'\n' in the REPLACEMENT of
  # ${var//pat/repl} (it inserts the literal characters), so an inline $'\n'
  # left compound commands unsplit there and the gate silently skipped
  # `cd x && git commit` (#391). A plain variable expands identically in
  # bash and zsh. ($'\n' in PATTERN position expands fine in both.)
  local input="$1" stop="${2:-0}" segment nl=$'\n'
  navori_trigger_hits=0
  if [ "${TRIGGER_STRIP_HEREDOC_BODIES:-}" = 1 ]; then
    case "$input" in *'<<'*) navori_strip_heredoc_bodies "$input"; input="$navori_heredoc_stripped" ;; esac
  fi
  # FIX B: join `\<newline>` continuations into a space FIRST, so a command
  # split across lines with a trailing backslash stays ONE logical segment
  # (otherwise the subcommand/flag lands in a segment not starting with git).
  input="${input//\\$'\n'/ }"
  input="${input//&&/$nl}"
  input="${input//||/$nl}"
  input="${input//;/$nl}"
  input="${input//|/$nl}"
  # `<<<` feeds the already-expanded value as data — no re-evaluation — so a
  # command that contains backticks/$() is inspected, never executed.
  while IFS= read -r segment; do
    segment="${segment#"${segment%%[![:space:]]*}"}"        # strip leading ws
    # FIX C: peel wrappers so `(git …`, `\git`, `command git …` and
    # `VAR=val git …` all reduce to a plain `git …` before matching.
    while [[ "$segment" == \(* ]]; do                       # strip leading ( runs
      segment="${segment#\(}"
      segment="${segment#"${segment%%[![:space:]]*}"}"
    done
    segment="${segment#\\}"                                 # strip a leading backslash (\git)
    while [[ "$segment" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; do  # strip VAR=val prefixes
      case "$segment" in
        *[[:space:]]*)
          segment="${segment#*[[:space:]]}"
          segment="${segment#"${segment%%[![:space:]]*}"}"
          ;;
        *) segment=""; break ;;
      esac
    done
    if [[ "$segment" == command\ * ]]; then                 # strip a leading `command ` word
      segment="${segment#command }"
      segment="${segment#"${segment%%[![:space:]]*}"}"
    fi
    # FIX C: allow git global options between `git` and the subcommand
    # (`git -c k=v commit`, `git -C /repo push`). $TRIGGER_RE's trailing boundary
    # keeps `git commitgraph` / `git config …` from matching.
    if printf '%s' "$segment" | grep -qE "$TRIGGER_RE"; then
      navori_trigger_hits=$((navori_trigger_hits + 1))
      if [ "$stop" = 1 ]; then return 0; fi
    fi
  done <<< "$input"
  return 0
}

is_scan_trigger() {
  # ─── Fast path (spec 0016 T3.2, second pass): the segment loop pays one
  # `grep -qE` FORK per segment — and a heredoc body or a 40-step compound
  # is 40 segments, so the field cost scaled with command length (measured:
  # 2.8 ms trivial, 14.8 ms for a 199-char heredoc, 95.8 ms for 40 segments;
  # p50 across one real session's commands was 40 ms per hook, not the
  # trivial floor). No $TRIGGER_RE can match without one of the caller's
  # literal TOKENS appearing in the segment it matches — and every segment is
  # a substring of the input, transformed only by insertions (`\<NL>` → space,
  # separators → newline) and prefix-peeling, none of which can CREATE a
  # token. So a single in-process substring scan of the raw input is a strict
  # superset of the segment matches: if no token is present, no segment can
  # match, and the gate answers "not for me" without a single fork. Same
  # argument, same safe direction, as the guard's own fast path.
  #
  # $TRIGGER_TOKENS is set by the including hook NEXT TO its $TRIGGER_RE, so
  # the pair travels together; when unset the fast path disarms and the loop
  # runs exactly as before (fail-open to the SLOW path, never to a skip).
  has_trigger_token "$1" || return 1
  navori_count_triggers "$1" 1
  [ "$navori_trigger_hits" -gt 0 ]
}

# THE CHEAP GATE, and it comes before everything that costs a process.
#
# This hook fires on EVERY Bash call and does real work on almost none of them,
# and until this line it paid for that privilege twice: `extract_cmd` forks jq
# (or node) to read the command, and the `skip` record forks jq again to write
# "I ran and it was not a PR". Measured on a `git status` payload: 24.8 ms per
# Bash call, half of the ~48 ms that already forced `audit-log.sh` to be
# redesigned.
#
# `has_trigger_token` answers from the payload navori already has in memory,
# with no fork at all, and its answer is a proof rather than a guess: the
# command is a substring of the payload, and JSON escaping cannot break a token
# apart. No token in the payload → no segment can match → nothing here concerns
# this hook.
#
# WHAT IS GIVEN UP: the `skip` record for those calls. It says "the hook ran and
# the command was not a PR" — 99.9% of its firings — and it cost two forks to
# produce. Every record that carries information (`ask`, `allow`) is still
# written below. Same trade as #696, for the same reason.
has_trigger_token "${payload:-}" || exit 0

payload_load
cmd=$(extract_cmd)

navori_audit_name="pr-publisher-confirm"
navori_audit_phase="PreToolUse"
navori_audit_tool="Bash"
# Fail-open no-ops, overwritten by the real definitions the include brings in.
# Same contract as the sibling gates: a recorder may never kill what it observes.
navori_audit_begin() { :; }
navori_audit_log() { :; }
# Shared audit repository resolver (#764) — inlined into every audit hook at
# render time. A nested agent worktree lives below the repository's
# `.claude/worktrees/` directory, but its basename is an ephemeral agent id.
#
# navori_audit_repo_from_cwd <cwd> — prints the stable parent repo name.
# This only uses shell builtins before the existing `basename` call: audit hooks
# run often, so discovering the Git common directory would add an avoidable fork
# per invocation.
navori_audit_repo_from_cwd() {
  navori_audit_repo_cwd=$1
  case "$navori_audit_repo_cwd" in
    */.claude/worktrees | */.claude/worktrees/*)
      navori_audit_repo_cwd=${navori_audit_repo_cwd%%/.claude/worktrees*}
      ;;
  esac
  basename "$navori_audit_repo_cwd" 2>/dev/null
}
# Shared advisory metadata recorder. The CLI is the single writer of the session log.
# The only shell write is one noclobber event file inside the CLI-created 0700 spool dir.
# The CLI re-validates every file before it reaches the log. No human content, no other
# redirects and no fallback writes are permitted here (spec 0054 D8; pinned by a drift test).
# Missing CLI or failed validation leaves an observation gap, never a hook failure.
# zsh replaces $0 with the function name; preserve the enclosing script identity.
navori_audit_script=$0
# Spec 0055 D4: the session's own id, read with builtins only. Succeeds (sets
# navori_audit_sid) only when the key "session_id" appears exactly once and its value
# is the same `id` shape the jq in navori_audit_record_metadata accepts. Anything else
# (absent, duplicated, escaped, odd value) fails: the caller falls back to auditing.
navori_audit_sid_read() {
  navori_audit_sid=
  case ${payload:-} in *'"session_id"'*) ;; *) return 1 ;; esac
  # Consume quote-delimited chunks in this shell: wildcard prefix searches and
  # duplicate scans can become quadratic with a large input before or after the key.
  navori_audit_sr=
  {
    IFS= read -r -d '"' navori_audit_sv || :
    while IFS= read -r -d '"' navori_audit_sv; do
      if [ "$navori_audit_sv" = session_id ]; then
        IFS= read -r -d '' navori_audit_sr || :
        break
      fi
    done
  } <<< "$payload"
  case $navori_audit_sr in *'"session_id"'*) return 1 ;; esac
  navori_audit_sr=${navori_audit_sr#"${navori_audit_sr%%[![:space:]]*}"}
  case $navori_audit_sr in :*) navori_audit_sr=${navori_audit_sr#:} ;; *) return 1 ;; esac
  navori_audit_sr=${navori_audit_sr#"${navori_audit_sr%%[![:space:]]*}"}
  case $navori_audit_sr in \"*) navori_audit_sr=${navori_audit_sr#\"} ;; *) return 1 ;; esac
  navori_audit_sv=${navori_audit_sr%%\"*}
  [ "$navori_audit_sv" != "$navori_audit_sr" ] || return 1
  case $navori_audit_sv in "" | *[!A-Za-z0-9_-]*) return 1 ;; esac
  [ "${#navori_audit_sv}" -le 256 ] || return 1
  navori_audit_sid=$navori_audit_sv
}

# Is there a regular, non-symlink file named "$1" in any repo dir under the audit root
# (dot-prefixed repo names included: the default glob skips them)? "$1" is
# `session-<id>.log` or `.armed`. Builtins and globs only. zsh needs null_glob
# (localised here) or an unmatched glob aborts the hook.
navori_audit_has_file() {
  [ -z "${ZSH_VERSION:-}" ] || setopt local_options null_glob
  for navori_audit_hf in "$navori_audit_root"/*/"$1" "$navori_audit_root"/.[!.]*/"$1" "$navori_audit_root"/..?*/"$1"; do
    [ -f "$navori_audit_hf" ] && [ ! -L "$navori_audit_hf" ] && return 0
  done
  return 1
}

# Audit only when the session has an active log (or an arm to consume). With a readable
# session id and no log there is nothing to record, so no timestamp (no perl) is paid.
# Doubt of any kind keeps today's behaviour: audit on.
navori_audit_begin() {
  navori_audit_on=0
  navori_audit_gate_pending=0
  navori_audit_root=${NAVORI_AUDITS_ROOT:-${HOME:-}/.navori/audits}
  [ -n "${HOME:-}${NAVORI_AUDITS_ROOT:-}" ] || return 0
  [ -d "$navori_audit_root" ] || return 0
  if navori_audit_sid_read; then
    if navori_audit_has_file "session-$navori_audit_sid.log"; then
      :
    elif case "${navori_audit_phase:-}" in SessionStart | UserPromptSubmit) true ;; *) false ;; esac &&
      navori_audit_has_file ".armed"; then
      :
    else
      navori_audit_gate_pending=1
      return 0
    fi
  fi
  navori_audit_on=1
  navori_audit_t0=$(navori_audit_now)
}

navori_audit_now() {
  if [ -n "${EPOCHREALTIME:-}" ]; then
    # `1756... .123456` → milliseconds, with pure parameter expansion.
    navori_audit_epoch=${EPOCHREALTIME/,/.}
    printf '%s%s' "${navori_audit_epoch%%.*}" "$(printf '%.3s' "${navori_audit_epoch#*.}")"
    return 0
  fi
  perl -MTime::HiRes=time -e 'printf "%.0f", time*1000' 2>/dev/null \
    || printf '%s' $(( $(date +%s 2>/dev/null || echo 0) * 1000 ))
}

# One spool file per event: `{"v":1,"host":…,"metadata":{…}}`, built by a single jq so the
# JSON is well-formed whatever the payload held. Args: metadata JSON. Needs
# navori_audit_spool and navori_audit_host. Returns non-zero when nothing was written.
navori_audit_spool_write() {
  navori_audit_event=$(jq -cn --arg host "$navori_audit_host" --argjson m "$1" \
    '{v:1,host:$host,metadata:$m}' 2>/dev/null) || return 1
  [ -n "$navori_audit_event" ] && [ "${#navori_audit_event}" -le 4096 ] || return 1
  navori_audit_stamp=${EPOCHREALTIME:-0}
  navori_audit_stamp=${navori_audit_stamp//[.,]/}
  ( set -C; umask 077; printf '%s\n' "$navori_audit_event" > "$navori_audit_spool/$navori_audit_stamp-$$-$RANDOM.json" ) 2>/dev/null || return 1
  return 0
}

# Resolve one exact marker before invoking the metadata writer. Startup may
# offer a repo-scoped arm candidate; the CLI authoritatively validates private
# modes, ownership and header identity before either append or spool creation.
navori_audit_record_metadata() {
  [ -n "${payload:-}" ] || return 0
  navori_audit_root=${NAVORI_AUDITS_ROOT:-${HOME:-}/.navori/audits}
  [ -n "${HOME:-}${NAVORI_AUDITS_ROOT:-}" ] || return 0
  [ -d "$navori_audit_root" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0
  navori_audit_fields=$(printf '%s' "$payload" | jq -er '
    def id: type == "string" and length > 0 and length <= 256 and test("^[A-Za-z0-9_-]+$");
    def agent: id or (type == "string" and length <= 256 and test("^pi-[a-z]+-[A-Za-z0-9_:-]+$"));
    select(.session_id | id) |
    [.session_id, (if (.cwd | type) == "string" then .cwd else "" end),
     ([.agent_id, .subagent_id] | map(select(agent)) | first) // "orchestrator", "."] | .[]' 2>/dev/null) || return 0
  navori_audit_session=${navori_audit_fields%%
*}
  navori_audit_rest=${navori_audit_fields#*
}
  navori_audit_cwd=${navori_audit_rest%%
*}
  navori_audit_rest=${navori_audit_rest#*
}
  navori_audit_agent=${navori_audit_rest%%
*}
  [ -n "$navori_audit_cwd" ] || navori_audit_cwd=$PWD
  navori_audit_repo=$(navori_audit_repo_from_cwd "$navori_audit_cwd") || return 0
  case "$navori_audit_repo" in "" | . | .. | *[!A-Za-z0-9_.-]*) return 0 ;; esac
  navori_audit_file=$navori_audit_root/$navori_audit_repo/session-$navori_audit_session.log
  if [ ! -f "$navori_audit_file" ] || [ -L "$navori_audit_file" ]; then
    [ "${navori_audit_phase:-}" = SessionStart ] || return 0
    navori_audit_arm=$navori_audit_root/$navori_audit_repo/.armed
    [ -f "$navori_audit_arm" ] && [ ! -L "$navori_audit_arm" ] || return 0
  fi
  case "${nv_engine:-}" in
    claude | codex | pi) navori_audit_host=$nv_engine ;;
    *) case "$navori_audit_script" in
      *".codex/hooks/"* | *".codex/scripts/"*) navori_audit_host=codex ;;
      *".pi/navori/hooks/"* | *".pi/navori/scripts/"*) navori_audit_host=pi ;;
      *) navori_audit_host=claude ;;
    esac ;;
  esac
  # Spool lane (spec 0054 R26, D8): when `navori audit --start` created this session's
  # spool dir, drop ONE event file there instead of starting the CLI. The dir must be a
  # real directory we own (not a symlink); the file is created with noclobber (O_EXCL:
  # never overwrites, never follows a symlink planted at that name) under umask 077.
  # The CLI re-validates host, categories and size when it consolidates. Anything
  # unusual — no dir, wrong owner, failed write — falls through to the CLI bridge below.
  navori_audit_spool=$navori_audit_root/$navori_audit_repo/spool-$navori_audit_session
  # `navori_audit_no_spool` (set by audit-mode-close) forces the CLI: the session-end
  # event is what makes the CLI consolidate the spool.
  if [ -z "${navori_audit_no_spool:-}" ] && [ -d "$navori_audit_spool" ] && [ ! -L "$navori_audit_spool" ] && [ -O "$navori_audit_spool" ]; then
    navori_audit_spool_write "$1" && return 0
  fi
  command -v navori >/dev/null 2>&1 || return 0
  # The writer assigns eventId/wireVersion before first persistence. Replay
  # keeps those identifiers; this transport never generates replacement IDs.
  printf '%s' "$1" | navori audit --record-metadata --host "$navori_audit_host" \
    --root-session "$navori_audit_session" --repo "$navori_audit_repo" \
    --root "$navori_audit_root" >/dev/null 2>&1 || :
  return 0
}

# Only closed categories and bounded technical identifiers cross this bridge.
# Args: verdict, reason, kind. `reason` is recorded only when it is one of the
# allowlisted codes below (mirrored by HOOK_REASON_CODES in lib/audit/model.ts,
# pinned by a drift test); any other non-empty text is stored as "unspecified".
# `kind` defaults from the verdict (block -> hard, ask -> ask); `deny` stays
# explicit because the confirm hooks use it as deny-as-confirmation on Codex.
navori_audit_log() {
  navori_audit_race=0
  if [ "${navori_audit_on:-0}" != 1 ]; then
    # The log may have been born during this hook (audit-mode-trigger, or a parallel hook
    # of the same event): record with ms 0, there was no t0 (spec 0055 R9).
    [ "${navori_audit_gate_pending:-0}" = 1 ] && [ -n "${navori_audit_sid:-}" ] || return 0
    navori_audit_has_file "session-$navori_audit_sid.log" || return 0
    navori_audit_race=1
  fi
  command -v jq >/dev/null 2>&1 || return 0
  if [ "${NAVORI_AUDIT_SKIP_NOOPS:-0}" = 1 ]; then
    case "${1:-}" in skip | noop) return 0 ;; esac
  fi
  navori_audit_end=$(navori_audit_now)
  [ "$navori_audit_end" -ge 0 ] 2>/dev/null || navori_audit_end=0
  navori_audit_ms=$(( navori_audit_end - ${navori_audit_t0:-$navori_audit_end} ))
  [ "$navori_audit_ms" -ge 0 ] 2>/dev/null || navori_audit_ms=0
  [ "$navori_audit_race" = 0 ] || navori_audit_ms=0
  navori_audit_metadata=$(printf '%s' "${payload:-}" | jq -c \
    --arg name "${navori_audit_name:-unknown}" --arg phase "${navori_audit_phase:-unknown}" \
    --arg verdict "${1:-unknown}" --arg reason "${2:-}" \
    --arg tool "${navori_audit_tool:-}" --arg source "${navori_audit_source:-core}" \
    --arg kind "${3:-}" --argjson ms "$navori_audit_ms" --argjson tsMs "$navori_audit_end" '
    def id: type == "string" and length > 0 and length <= 256 and test("^[A-Za-z0-9_-]+$");
    def agent: id or (type == "string" and length <= 256 and test("^pi-[a-z]+-[A-Za-z0-9_:-]+$"));
    def invocation: type == "string" and length > 0 and length <= 256 and test("^[A-Za-z0-9_:-]+$");
    def technical_label: if length <= 256 and test("^[A-Za-z0-9_.:-]+$") then . else "unknown" end;
    {event:"hook",name:($name|technical_label),source:($source|technical_label),ms:$ms,tsMs:$tsMs,
     phase:(if (["PreToolUse","PostToolUse","SessionStart","SessionEnd","Stop","SubagentStart","SubagentStop","UserPromptSubmit","PreCompact"]|index($phase)) != null then $phase else "unknown" end),
     verdict:(if (["allow","ask","block","deny","skip","noop","clean","dirty","inject","repeat","partial","compact-advice","gate-started","gate-killed"]|index($verdict)) != null then $verdict else "unknown" end),
     agentId:(([.agent_id,.subagent_id]|map(select(agent))|first)//"orchestrator")}
     + (if (.tool_use_id|invocation) then {toolUseId:.tool_use_id} else {} end)
     + (if (["Bash","Edit","Read","Write","Agent","Task","NotebookEdit"]|index($tool)) != null then {tool:$tool} else {} end)
     + (if $reason == "" then {}
        elif (["oversize","no-verify","force-push-base","rm-root","rm-var","no-preserve-root","fork-bomb","block-device","managed-rewrite","binary-missing","plan-denied","subcommand-unavailable","native-hook","foreign-repo","foreign-gate"]|index($reason)) != null then {reason:$reason}
        else {reason:"unspecified"} end)
     + (($kind | if . == "" then (if $verdict == "block" then "hard" elif $verdict == "ask" then "ask" else "" end) else . end) as $k
        | if (["hard","ask","advisory"]|index($k)) != null then {kind:$k} else {} end)' 2>/dev/null) || return 0
  navori_audit_record_metadata "$navori_audit_metadata"
  return 0
}
navori_audit_begin

# The verdict is derived once, in a trap, rather than by a call per branch —
# this fires on EVERY Bash call and does real work on almost none of them.
navori_audit_verdict="skip"
navori_audit_reason="el comando no abre un PR"
navori_audit_on_exit() {
  navori_audit_log "$navori_audit_verdict" "$navori_audit_reason" || true
  return 0
}
trap navori_audit_on_exit EXIT

# An EMPTY $cmd means nothing could be read from the tool input, not "some
# command that isn't a PR". Unlike the quality gate, the fail-open direction
# here is to stay quiet: this hook's worst case is a false confirmation prompt
# on every Bash call, which would train the user to dismiss it unread — and a
# prompt nobody reads is worth less than no prompt at all.
[ -n "$cmd" ] || exit 0
is_scan_trigger "$cmd" || exit 0

# Who is running it. Inside a subagent the host sends a real `agent_id` on the
# tool phases; the main thread sends none. Measured over the park's audit logs:
# 10,879 events carried a real id and every one of them resolved to a subagent.
#
# Read HERE, not at the top: `payload_field` may spawn a process, and by this
# line we already know the command is the rare one that needs the answer.
#
# It names SOME subagent, not specifically the publisher — a `scout` opening a
# PR would pass. That is deliberate: this is a routing nudge, not a security
# boundary, and the detector cannot see through `sh -c` either.
#
# CODEX (spec 0041 R10): Codex hooks cannot emit `ask` and a `.codex/rules`
# `prompt` rule only confirms on the main thread — it is silent inside the
# publisher subagent (live probe V1) — so the Codex copy denies instead:
# deny-as-confirmation, decided by `$0` like `comment-draft-confirm.sh`. It runs
# BEFORE the subagent allow, because the publisher is exactly where the
# unconfirmed `gh pr create` happens. Fixed by construction: no jq needed.
case "$0" in
  *".codex/hooks/"*)
    navori_audit_verdict="deny"
    navori_audit_reason="gh pr create requires user confirmation (Codex)"
    # The outer process deadline also covers synchronous Git/state resolution.
    # Only a complete deny is forwarded; a missing, stale or stalled CLI falls back.
    if command -v node >/dev/null 2>&1 && command -v navori >/dev/null 2>&1; then
      if printf '%s' "$payload" | node -e '
        const {spawn}=require("node:child_process");
        let raw="", out="", failed=false;
        process.stdin.on("data", chunk => {raw+=chunk;if(Buffer.byteLength(raw)>65536)failed=true;});
        process.stdin.on("end", () => {
          if(failed){process.exitCode=1;return;}
          const child=spawn("navori",["codex","approval","request"],{detached:true,stdio:["pipe","pipe","ignore"]});
          const stop=()=>{failed=true;try{process.kill(-child.pid,"SIGKILL")}catch{}};
          const timer=setTimeout(stop,5000);
          child.on("error",()=>{clearTimeout(timer);process.exitCode=1;});
          child.stdin.on("error",()=>{});
          child.stdout.on("data",chunk=>{out+=chunk;if(Buffer.byteLength(out)>65536)stop();});
          child.on("close",code=>{
            clearTimeout(timer);
            try{
              const result=JSON.parse(out), h=result.hookSpecificOutput;
              if(failed||code!==0||Object.keys(result).length!==1||h.hookEventName!=="PreToolUse"||h.permissionDecision!=="deny"||typeof h.permissionDecisionReason!=="string")throw Error();
              process.stdout.write(JSON.stringify(result)+"\n");
            }catch{process.exitCode=1;}
          });
          child.stdin.end(raw);
        });
      ' 2>/dev/null; then
        exit 0
      fi
    fi
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[navori] this `gh pr create` opens a PR and Codex hooks cannot prompt. Show the user the title and body, and let them confirm and run the command themselves."}}'
    exit 0
    ;;
esac

# PI (spec 0048 D5, R4-R6): Pi has no host permission prompt, so its copy asks ALWAYS, for the main
# thread and for a subagent alike, BEFORE the subagent allow below: the publisher is exactly where the
# unconfirmed `gh pr create` happens. Decided by `$0`, like the Codex arm. The Pi extension resolves
# the `ask`: a confirmation showing the title/body in the interactive parent, refusal plus relay to the
# parent (R6) in a child or without UI. The body file is named in `navoriBodyFiles` so the approval is
# bound to its content. No parser at all still asks, with a fixed reason: this arm never goes quiet.
case "$0" in
  *"/.pi/navori/"*)
    navori_audit_verdict="ask"
    navori_audit_reason="gh pr create requires user confirmation (Pi)"
    nv_kind="gh-pr-open"
    nv_label="a GitHub pull request"
    NV_FALLBACK_REASON="[navori] this call opens a GitHub pull request and its draft could not be read or rendered (no readable body, or no jq/node on PATH to parse it). Review the exact command above before confirming."
    nv_have_jq=0
    command -v jq >/dev/null 2>&1 && nv_have_jq=1
    nv_have_node=0
    command -v node >/dev/null 2>&1 && nv_have_node=1
    if [ "$nv_have_jq" = 0 ] && [ "$nv_have_node" = 0 ]; then
      printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$NV_FALLBACK_REASON"
      exit 0
    fi
# Draft reader shared by every hook that shows the user WHAT is about to be published
# (`comment-draft-confirm`, and the Pi copy of `pr-publisher-confirm`, spec 0048 D5/R5).
# Inlined at render time (see lib/render/hook-includes.ts). Pure reading: it decides which
# file or inline text carries the body and renders a bounded preview; the JSON that speaks to
# the host stays in each script (partials never carry host output vocabulary).
#
# Needs, from the caller: `cmd`, `nv_kind` (gh-comment, gh-review, gh-issue-create, gh-pr-open,
# gh-api-graphql, gh-api-rest, acli-create, acli-update), `nv_label`, `NV_FALLBACK_REASON`, and
# `nv_have_jq` / `nv_have_node` (0 or 1). Defines only functions; nothing runs until
# `navori_draft_body` is called.
#
# `navori_draft_body` sets, as globals (the callers read them after the call):
#   nv_body_source  none | inline | gql-text | file
#   nv_reason       the text the user reads before confirming
#   nv_body_path    the body file named by the command, when there is one
#   nv_bound_file   every file the preview was read from, so a caller can bind the approval to
#                   its content (empty when the preview came from the command itself)

# --- Locate the flag value for a small set of alternatives (`-F|--body-file`,
# `--body-adf`, `--input`, …). Reads the WHOLE $cmd, so it only ever targets a
# flag whose VALUE is a file path — never a body carried inline in the command,
# which the codebase's own compound-command splitters (`gate-trigger.sh`) do
# not respect quoting for either; a file path does not contain `;`/`|`/`&&` in
# practice, so this stays safe where the inline case (never read this way)
# would not be.
nv_flag_value() {
  local text="$1" flags="$2" raw
  raw=$(printf '%s' "$text" | grep -oE "(^|[[:space:]])(${flags})(=|[[:space:]]+)('[^']*'|\"[^\"]*\"|[^[:space:]]+)" | head -1) || true
  [ -n "$raw" ] || return 0
  printf '%s' "$raw" | sed -E "s/^[[:space:]]*(${flags})(=|[[:space:]]+)//; s/^['\"]//; s/['\"]\$//"
}

nv_looks_like_json() {
  local t="${1#"${1%%[![:space:]]*}"}"
  case "$t" in
    "{"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Reads a bounded prefix of $1 into $nv_body_content. Returns 1 (never aborts
# under `set -e` — always called from an `if`/`||`) when the path is not a
# readable regular file, which is what R12 means by "cannot read the body".
nv_read_body() {
  # NOT named `path`: that identifier is zsh's special array aliased to
  # `$PATH` (`man zshparam`), so a plain `local path=…` silently collapses the
  # function's own command lookup to whatever was assigned — every builtin
  # call after it (here, `head`) then fails with "command not found". Caught
  # by the bash×zsh differential suite (#391), same class as the `$'\n'` and
  # unquoted-`for` pitfalls the shared partials already document.
  local nv_target="$1"
  [ -n "$nv_target" ] && [ "$nv_target" != "-" ] && [ -f "$nv_target" ] && [ -r "$nv_target" ] || return 1
  nv_body_content=$(head -c 200000 -- "$nv_target" 2>/dev/null) || return 1
  return 0
}

# ADF (Atlassian Document Format) is a JSON tree; only its `text` leaves are
# shown, and `query` (GraphQL's OWN document) is never treated as one — R11.
nv_adf_text_from_file() {
  if [ "$nv_have_jq" = 1 ]; then
    jq -r '[.. | .text? // empty] | join(" ")' "$1" 2>/dev/null
    return 0
  fi
  node -e '
const fs = require("fs");
try {
  const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
  const out = [];
  const walk = (n) => {
    if (n && typeof n === "object") {
      if (typeof n.text === "string") out.push(n.text);
      for (const k in n) walk(n[k]);
    }
  };
  walk(data);
  process.stdout.write(out.join(" "));
} catch (e) {
  /* leave stdout empty; the caller falls back to the raw file content */
}
' "$1" 2>/dev/null
  return 0
}

nv_gql_body_from_input() {
  if [ "$nv_have_jq" = 1 ]; then
    jq -r '(.variables.body // .body // empty)' "$1" 2>/dev/null
    return 0
  fi
  node -e '
const fs = require("fs");
try {
  const d = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
  const b = (d.variables && d.variables.body) || d.body || "";
  process.stdout.write(String(b));
} catch (e) {}
' "$1" 2>/dev/null
  return 0
}

# Caps a preview at 1,500 characters, with the count of what was cut — R11.
nv_truncate() {
  local text="$1" max=1500 len=${#1}
  if [ "$len" -gt "$max" ]; then
    # `$max`, NOT the bare name: zsh's `${text:0:max}` reads `max` as the
    # START of a history-modifier list (`:m…`) instead of a length variable —
    # `unrecognized modifier 'm'` — where bash resolves it as arithmetic. The
    # `$`-prefixed form is unambiguous, and identical, in both shells.
    printf '%s\n[+%d caracteres omitidos]' "${text:0:$max}" "$((len - max))"
  else
    printf '%s' "$text"
  fi
}

navori_draft_body() {
  nv_body_source="none"
  nv_body_path=""
  nv_bound_file=""
  nv_sniff_adf=0
  nv_force_adf=0

  case "$nv_kind" in
    gh-comment | gh-review | gh-issue-create | gh-pr-open)
      nv_body_path=$(nv_flag_value "$cmd" '-F|--body-file')
      if [ -n "$nv_body_path" ] && [ "$nv_body_path" != "-" ]; then
        nv_body_source="file"
      elif printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(-b|--body)([[:space:]=]|$)'; then
        nv_body_source="inline"
      fi
      ;;
    gh-api-graphql)
      nv_body_path=$(printf '%s' "$cmd" | grep -oE -- '-F[[:space:]]+body=@[^[:space:]]+' | head -1 | sed -E 's/^-F[[:space:]]+body=@//') || true
      if [ -n "$nv_body_path" ]; then
        nv_body_source="file"
      elif printf '%s' "$cmd" | grep -qE -- '-f[[:space:]]+body=[^[:space:]]+'; then
        nv_body_source="inline"
      else
        nv_input=$(nv_flag_value "$cmd" '--input')
        if [ -n "$nv_input" ] && [ "$nv_input" != "-" ] && nv_read_body "$nv_input"; then
          nv_gql_text=$(nv_gql_body_from_input "$nv_input")
          if [ -n "$nv_gql_text" ]; then
            nv_body_source="gql-text"
            nv_bound_file="$nv_input"
          fi
        fi
      fi
      ;;
    gh-api-rest)
      nv_body_path=$(nv_flag_value "$cmd" '--input')
      if [ -z "$nv_body_path" ]; then
        nv_body_path=$(printf '%s' "$cmd" | grep -oE -- '-F[[:space:]]+[A-Za-z0-9_]+=@[^[:space:]]+' | head -1 | sed -E 's/^-F[[:space:]]+[A-Za-z0-9_]+=@//') || true
      fi
      if [ -n "$nv_body_path" ] && [ "$nv_body_path" != "-" ]; then
        nv_body_source="file"
      fi
      ;;
    acli-create)
      nv_body_path=$(nv_flag_value "$cmd" '-F|--body-file')
      if [ -n "$nv_body_path" ]; then
        nv_body_source="file"
        nv_sniff_adf=1
      elif printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(-b|--body)([[:space:]=]|$)'; then
        nv_body_source="inline"
      fi
      ;;
    acli-update)
      nv_body_path=$(nv_flag_value "$cmd" '--body-adf')
      if [ -n "$nv_body_path" ]; then
        nv_body_source="file"
        nv_force_adf=1
      else
        nv_body_path=$(nv_flag_value "$cmd" '-F|--body-file')
        if [ -n "$nv_body_path" ]; then
          nv_body_source="file"
          nv_sniff_adf=1
        elif printf '%s' "$cmd" | grep -qE '(^|[[:space:]])(-b|--body)([[:space:]=]|$)'; then
          nv_body_source="inline"
        fi
      fi
      ;;
  esac

  nv_reason=""
  case "$nv_body_source" in
    inline)
      # R11: never re-derive the value (it might carry `;`/`|`/newlines the
      # compound-command scan above does not respect quoting for); the reason
      # just points back at the command the host already shows the user.
      nv_reason="[navori] this call publishes $nv_label. Its body is inline in the command above — review it there before confirming."
      ;;
    gql-text)
      nv_preview=$(nv_truncate "$nv_gql_text")
      nv_reason="[navori] this call publishes $nv_label. \`body\` variable:

$nv_preview"
      ;;
    file)
      nv_bound_file="$nv_body_path"
      if nv_read_body "$nv_body_path"; then
        nv_text="$nv_body_content"
        if [ "$nv_force_adf" = 1 ] || { [ "$nv_sniff_adf" = 1 ] && nv_looks_like_json "$nv_body_content"; }; then
          nv_adf_text=$(nv_adf_text_from_file "$nv_body_path")
          [ -n "$nv_adf_text" ] && nv_text="$nv_adf_text"
        fi
        nv_preview=$(nv_truncate "$nv_text")
        nv_reason="[navori] this call publishes $nv_label from file '$nv_body_path':

$nv_preview"
      else
        nv_reason="$NV_FALLBACK_REASON"
      fi
      ;;
    *)
      nv_reason="$NV_FALLBACK_REASON"
      ;;
  esac
}
    navori_draft_body
    nv_pi_files=0
    [ -z "$nv_bound_file" ] || nv_pi_files=1
    if [ "$nv_have_jq" = 1 ]; then
      jq -cn --arg r "$nv_reason" --arg f "$nv_pi_files:$nv_bound_file" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}
          + (if ($f | startswith("1:")) then {navoriBodyFiles: [$f[2:]]} else {} end)'
    else
      NV_R="$nv_reason" NV_F="$nv_pi_files:$nv_bound_file" node -e 'const out={hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:process.env.NV_R}};if(process.env.NV_F.startsWith("1:"))out.navoriBodyFiles=[process.env.NV_F.slice(2)];process.stdout.write(JSON.stringify(out))'
    fi
    exit 0
    ;;
esac

navori_pr_agent=$(payload_field agent_id)
[ -n "$navori_pr_agent" ] || navori_pr_agent=$(payload_field subagent_id)
if [ -n "$navori_pr_agent" ]; then
  navori_audit_verdict="allow"
  navori_audit_reason="el PR viene de un subagente"
  exit 0
fi

navori_audit_verdict="ask"
navori_audit_reason="PR abierto fuera del publisher"

# `ask` routes the call to the user instead of resolving it. The reason is what
# they read, so it says what the publisher adds and how to get it — a prompt that
# only says "are you sure" is a tax, not a routing signal.
#
# jq builds it: the reason travels inside JSON and a hand-rolled string would
# break on the first quote. No jq (not preinstalled on macOS) → stay silent
# rather than emit malformed JSON, which the host rejects with a wall of schema
# text that teaches the user to ignore this hook.
command -v jq >/dev/null 2>&1 || exit 0

# The message lands in its own assignment rather than inline in the jq call.
# A heredoc nested inside `"$( ... )"` is parsed by the shell BEFORE the quoted
# delimiter takes effect for the outer context, so the apostrophe in "repo's"
# and the backticks around `gh pr create` opened quotes that were never closed
# and the file failed `bash -n` outright. Caught by the syntax check; it would
# have shipped a hook that cannot run to every repo in the park.
navori_pr_reason=$(cat <<'MSG'
[navori] this `gh pr create` does not come from the publisher.

The publisher is the single owner of commit+PR: it applies the title/body format
this repo uses and runs the git/gh pre-flight before opening anything.

Delegate it with the Agent tool (subagent_type: publisher), or confirm to
open this PR by hand — a rollout PR, a revert, or a session where subagents are
unavailable are all legitimate reasons to do so.
MSG
)

jq -cn --arg reason "$navori_pr_reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
exit 0
# navori:managed end id="pr-publisher-confirm-base"
