"""Tests for the repository's process documents."""

from __future__ import annotations

from owl.variants import ROOT

PROTOCOL = ROOT / "docs" / "round-protocol.md"


# Covers: R9, R10 (round-protocol)
def test_round_protocol_has_trigger_table() -> None:
    text = PROTOCOL.read_text()
    for step in ("Corte", "Pins", "Spike", "Auditoría de prefijos", "Precios", "Piloto", "Smoke", "Holdout",
                 "Pre-registro"):
        assert f"**{step}.**" in text, step
    table = text.split("## Disparadores", 1)[1].split("##", 1)[0]
    rows = [line for line in table.splitlines() if line.startswith("| ") and "---" not in line][1:]
    triggers = {row.split("|")[1].strip(): row.split("|")[2].lower() for row in rows}
    assert "spike" in triggers["Un harness cambia de versión mayor o de flujo documentado"]
    assert "auditoría" not in triggers["Cambia el modelo"] and "piloto" in triggers["Cambia el modelo"]
    assert "holdout" in triggers["Cambia `owl/verifier/lib.sh` o un prefijo de `artifacts`"]
    assert "smoke" in triggers["Cambia cualquier pin"]
    assert "## Cambio de pin después del corte" in text and "RULES.md" in text.split("después del corte", 1)[1]
