# navori:managed start id="master-accept-confirm-base" hash="995ddd0f" version="0.12.3" source="@navori/core"
#!/usr/bin/env bash
#
# PreToolUse(Bash): a manual acceptance (`navori master part … --approved-by`)
# or a `navori master close` must be confirmed by the person whose approval it
# records (spec 0034 R62, spec 0039 R58).
#
# This is deliberately an interruption, not a parser for the command. The CLI
# validates the complete flag contract; this hook keeps the human in the loop
# for the one form that claims their manual review.
set -euo pipefail

# Command extraction (payload → $cmd). Shared body, single source of truth.
nv_payload_fields="tool_input.command"
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

# Every matching command needs this literal token, so its absence from the raw
# payload proves this hook cannot apply and avoids parsing the payload at all.
TRIGGER_TOKENS='approved-by delivery-baseline delivery-queue escalation-reset navori master'
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

has_trigger_token "${payload:-}" || exit 0

payload_load
cmd=$(extract_cmd)

navori_audit_name="master-accept-confirm"
navori_audit_phase="PreToolUse"
navori_audit_tool="Bash"
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

navori_audit_verdict="skip"
navori_audit_reason="el comando no registra una aprobación manual"
navori_audit_on_exit() {
  navori_audit_log "$navori_audit_verdict" "$navori_audit_reason" || true
  return 0
}
trap navori_audit_on_exit EXIT

[ -n "$cmd" ] || exit 0

# Same boundary as D6/R43: a command after `&&`, `;`, `|`, in a subshell or a
# command substitution is still visible. `is_scan_trigger` keeps the flag in
# the same compound-command segment, so an unrelated later `--approved-by`
# cannot turn an earlier command into a confirmation prompt. `navori` may be
# bare, run via npx/bunx/pnpm exec|dlx, or a path ending in `/navori`.
# `--approved-by` takes `=` or a space; `close` is gated in all its forms.
BOUND='(^|[;&|(`]|[[:space:]])'
RUNNER='((npx|bunx|pnpm[[:space:]]+(exec|dlx))[[:space:]]+(-[^[:space:]]+[[:space:]]+)*)?'
NAVORI="${RUNNER}([^[:space:];&|(\`]*/)?navori(@[^[:space:]]+)?"
PART_RE="${NAVORI}[[:space:]]+master[[:space:]]+part([[:space:]]|\$).*--approved-by([[:space:]=]|\$)"
CLOSE_RE="${NAVORI}[[:space:]]+master[[:space:]]+close([[:space:];&|)<>]|\$)"
BASELINE_RE="${NAVORI}[[:space:]]+master[[:space:]]+delivery-baseline([[:space:]]|\$).*--approved-by([[:space:]=]|\$)"
QUEUE_RE="${NAVORI}[[:space:]]+master[[:space:]]+delivery-queue([[:space:]]|\$).*--approved-by([[:space:]=]|\$)"
DELIVERY_REVIEW_RE="${NAVORI}[[:space:]]+master[[:space:]]+delivery-(review|decision|publication|revoke)([[:space:];&|)<>]|\$)"
DELIVERY_CRITERION_RE="${NAVORI}[[:space:]]+master[[:space:]]+delivery-criterion([[:space:]]|\$).*--approved-by([[:space:]=]|\$)"
DELIVERY_REFRESH_RE="${NAVORI}[[:space:]]+master[[:space:]]+delivery-slice([[:space:]]|\$).*--refresh([[:space:]=]|\$)"
RESET_RE="${NAVORI}[[:space:]]+plan[[:space:]]+escalation-reset([[:space:]]|\$).*--approved-by([[:space:]=]|\$)"
TRIGGER_RE=".*${BOUND}(${PART_RE}|${CLOSE_RE}|${BASELINE_RE}|${QUEUE_RE}|${DELIVERY_REVIEW_RE}|${DELIVERY_CRITERION_RE}|${DELIVERY_REFRESH_RE}|${RESET_RE})"
# A command substitution starts a new command: make it a segment of its own so
# the `VAR=$(` prefix peeling in the shared scan cannot swallow it.
navori_subst='$('
navori_semi='; '
cmd="${cmd//"$navori_subst"/$navori_semi}"
# Quotes hide the boundary from `BOUND` in wrapped forms (`sh -c 'navori master
# close'`, `eval "…"`, `navori master "close"`): delete ONLY `"` and `'`. Never
# `\`: `navori_count_triggers` joins a `\<newline>` continuation first, and
# removing the backslash here would split the segment (spec 0052 R36). The cost
# is asking on `echo "navori master close"`, the safe direction. A word split by
# quotes (`navo"ri`) is deliberate obfuscation this hook does not claim to catch.
cmd="${cmd//[\"\']/}"
is_scan_trigger "$cmd" || exit 0

approval_description="a manual criterion"
case "$cmd" in
  *delivery-review*) approval_description="this exact technical snapshot: you inspected the bound report, attest that the named reviewer was separate from the producer, and observed the stated full QA command succeed. The CLI checks content and the current receipt; it does not authenticate reviewer identity or execute QA" ;;
  *delivery-decision*) approval_description="the explicit client decision on this exact presented delivery or reasoned disposition of its current scope" ;;
  *delivery-publication*) approval_description="the release or deploy reference for this exact accepted delivery; this records publication, it does not deploy" ;;
  *delivery-revoke*) approval_description="revocation of the active authority generation and prior effective proof" ;;
  *delivery-slice*) approval_description="the current-queue reverification refresh; pending criteria reset and normal plan approval is required again" ;;
  *escalation-reset*) approval_description="another review round after two rejections at level 2 or higher" ;;
  *delivery-baseline*|*delivery-queue*) approval_description="the delivery baseline or bounded queue" ;;
esac

# Fixed by construction: no repository content reaches JSON, so this still
# works when jq and node are unavailable.
# Codex parses `permissionDecision` but drops `"ask"` (the call proceeds), so
# the Codex copy denies instead: deny-as-confirmation, decided by `$0` like
# `comment-draft-confirm.sh` (spec 0041 D11). Never an allow.
case "$0" in
  *".codex/hooks/"*)
    navori_audit_verdict="deny"
    navori_audit_reason="manual approval or stage close"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[navori] this records that the user approved %s, and Codex hooks cannot prompt. Show the user what it approves and let them confirm and run the command themselves."}}\n' "$approval_description"
    ;;
  *)
    navori_audit_verdict="ask"
    navori_audit_reason="manual approval or stage close"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"[navori] this records that you approved %s. Confirm only if you reviewed it."}}\n' "$approval_description"
    ;;
esac
# navori:managed end id="master-accept-confirm-base"
