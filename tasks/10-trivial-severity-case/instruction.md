`opsdesk incidents list` is showing severities wrong. An incident stored with severity `SEV1`
shows up in the CLI output as `Sev1`. The API (`GET /incidents`) returns `SEV1` for the same
incident, so the two disagree. Fix the CLI so it prints the severity exactly as stored, like the
API does.
