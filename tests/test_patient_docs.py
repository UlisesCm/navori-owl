"""Fast, non-Docker checks on patient/'s static content (T4).

Run: `uv run pytest tests/test_patient_docs.py` (no Docker, no model).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATIENT = ROOT / "patient"


# Covers: R1
def test_agents_md_matches_claude_md() -> None:
    """Agent neutrality: Codex reads AGENTS.md, Claude Code reads CLAUDE.md — both must carry the
    same base conventions (M1-M6) so no variant gets a harder or easier `conventions` baseline.
    Source of truth is patient/CLAUDE.md; patient/AGENTS.md is committed as an exact duplicate
    (not generated at seal time: seal.sh's job is sealing a fixture, not authoring content, and a
    static duplicate plus this test is simpler to keep in sync than a build-time copy step)."""
    claude_md = (PATIENT / "CLAUDE.md").read_text()
    agents_md = (PATIENT / "AGENTS.md").read_text()
    assert claude_md == agents_md, "patient/AGENTS.md drifted from patient/CLAUDE.md — re-copy it"


# Covers: R1
def test_no_harness_name_leaks_into_patient() -> None:
    """D2: the patient's base content must stay neutral across every variant it's rendered under."""
    for path in PATIENT.rglob("*"):
        if path.is_dir() or "node_modules" in path.parts:
            continue
        text = path.read_text(errors="ignore")
        assert "navori" not in text.lower(), f"{path} mentions navori"
