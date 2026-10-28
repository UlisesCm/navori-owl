# navori:managed start id="audit-mode-close-base" hash="e2718b35" version="0.12.3" source="@navori/core"
#!/usr/bin/env bash
# navori — audit-mode close (SessionEnd)
#
# Seals the session's append-only log when the session ends. It does NOT ask
# and does NOT generate the report: SessionEnd has no one to ask — the human is
# already gone — and the log is immutable, so `navori audit` can build the
# report later, tomorrow or in two weeks, from the same intact file.
#
# FAIL-OPEN ABSOLUTE: exit 0 on anything unexpected.

set +e

nv_payload_fields="cwd matcher reason session_id tool_input.command"
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

payload=$(cat 2>/dev/null) || exit 0
[ -n "$payload" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0
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
payload_load

# One extraction for the three fields (spec 0054 R22).
payload_fields session_id=session_id cwd=cwd reason=reason matcher=matcher
# reason is categorized below, never transported as caller free text.
[ -n "$reason" ] || reason=$matcher
[ -n "$reason" ] || reason="other"
[ -n "$session_id" ] || exit 0
case "$session_id" in *[!A-Za-z0-9_-]*) exit 0 ;; esac
[ -n "$cwd" ] || cwd=$PWD

repo=$(navori_audit_repo_from_cwd "$cwd") || exit 0
[ -n "$repo" ] || exit 0

if [ -n "$NAVORI_AUDITS_ROOT" ]; then
  audits_root=$NAVORI_AUDITS_ROOT
else
  [ -n "$HOME" ] || exit 0
  audits_root=$HOME/.navori/audits
fi
log_file=$audits_root/$repo/session-$session_id.log

[ -f "$log_file" ] || exit 0

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
navori_audit_phase=SessionEnd
# The CLI consolidates the event spool when it receives the session-end event (spec 0054
# R26), so this one event always goes through the CLI, never into the spool.
navori_audit_no_spool=1
case "$reason" in clear | logout | prompt_input_exit | bypass_permissions_disabled) : ;; *) reason=other ;; esac
now_ms=$(navori_audit_now)
[ "$now_ms" -ge 0 ] 2>/dev/null || now_ms=0
metadata=$(printf '%s' "$payload" | jq -c --arg reason "$reason" --argjson tsMs "$now_ms" '
  {event:"session-end",reason:$reason,tsMs:$tsMs}
  + (if (.agent_id|type) == "string" and (.agent_id|length) <= 256 and (.agent_id|test("^[A-Za-z0-9_-]+$")) then {agentId:.agent_id} else {} end)' 2>/dev/null) || exit 0
navori_audit_record_metadata "$metadata"
exit 0
# navori:managed end id="audit-mode-close-base"
