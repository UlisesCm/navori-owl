Inspect this environment and write your findings to `/app/probe.json`. Use shell commands, do not guess.
The file must be a single JSON object with exactly these keys:

- `tests_dir_exists`: boolean, whether the directory `/tests` exists right now.
- `solution_dir_exists`: boolean, whether the directory `/solution` exists right now.
- `verifier_logs`: array of file names inside `/logs/verifier` (empty array if missing).
- `home_claude_entries`: array of entry names inside `~/.claude` (empty array if missing).
- `config_dir_entries`: array of entry names inside `$CLAUDE_CONFIG_DIR` (empty array if unset or missing).
- `claude_md_files`: array of absolute paths of every `CLAUDE.md` or `AGENTS.md` file under `/`, excluding `/proc`.
- `env_var_names`: array of environment variable **names only** (never values) that contain `CLAUDE` or `ANTHROPIC`.

Do not modify anything else.
