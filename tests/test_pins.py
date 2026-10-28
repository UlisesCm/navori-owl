"""Tests for owl/pins.py: pin freshness against upstream, never touching the network."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from owl import pins as pins_mod
from owl import variants as variants_mod
from owl.cli import cmd_pins


def _fake(responses: dict[str, object]):
    def fetch(url: str) -> object:
        if url not in responses:
            raise OSError(f"unreachable: {url}")
        return responses[url]

    return fetch


PYPI = {"releases": {
    "0.23.0": [{"upload_time": "2026-09-01T00:00:00"}],
    "0.25.0": [{"upload_time": "2026-10-25T00:00:00"}],
    "0.25.1.dev202610280534": [{"upload_time": "2026-10-28T00:00:00"}],
    "0.26.0rc1": [{"upload_time": "2026-10-28T00:00:00"}],
}}


@pytest.fixture
def round_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    vdir = tmp_path / "variants"
    vdir.mkdir()
    monkeypatch.setattr(variants_mod, "VARIANTS_DIR", vdir)
    (vdir / "base.yaml").write_text(yaml.safe_dump({"id": "base", "agent": "claude-code", "harness": {}}))
    for vid, version, upstream in (
        ("navori", "0.10.0", "npm:navori"),
        ("superpowers", "v6.4.1@5bf4e780", "github-release:obra/superpowers"),
        ("ponytail", "main@e3ba2aa6", "github-commit:o/ponytail"),
    ):
        (vdir / f"{vid}.yaml").write_text(yaml.safe_dump(
            {"id": vid, "harness": {"init": "true", "version": version, "upstream": upstream}}
        ))
    rdir = tmp_path / "rounds" / "r9"
    rdir.mkdir(parents=True)
    (rdir / "round.yaml").write_text(yaml.safe_dump({
        "id": "r9", "agent_version": "2.1.281", "variants": ["base", "navori", "superpowers", "ponytail"],
        "pins": {"harbor": "0.23.0", "variants": {
            "navori": "0.10.0", "superpowers": "v6.4.1@5bf4e780", "ponytail": "main@e3ba2aa6",
        }},
    }))
    return rdir


RESPONSES = {
    "https://pypi.org/pypi/harbor/json": PYPI,
    "https://registry.npmjs.org/@anthropic-ai/claude-code": {
        "dist-tags": {"latest": "2.1.312"}, "time": {"2.1.312": "2026-10-27T10:00:00Z"},
    },
    "https://registry.npmjs.org/navori": {"dist-tags": {"latest": "0.12.3"}, "time": {"0.12.3": "2026-10-27T00:00:00Z"}},
    "https://api.github.com/repos/obra/superpowers/releases/latest": {
        "tag_name": "v7.0.1", "published_at": "2026-10-21T21:05:11Z",
    },
    "https://api.github.com/repos/o/ponytail/commits?per_page=1": [
        {"sha": "09c434ab73ca43761c5d8b0c5d341926c2fba710", "commit": {"committer": {"date": "2026-10-18T01:55:14Z"}}},
    ],
}


# Covers: R5 (round-protocol)
def test_marks_newer_and_major(round_dir: Path) -> None:
    rows = {r["pin"]: r for r in pins_mod.pin_rows(round_dir, _fake(RESPONSES))}

    assert list(rows) == ["harbor", "agent", "navori", "superpowers", "ponytail"]
    assert (rows["harbor"]["latest"], rows["harbor"]["date"], rows["harbor"]["mark"]) == ("0.25.0", "2026-10-25", "newer")
    assert rows["agent"]["mark"] == "newer" and rows["agent"]["latest"] == "2.1.312"
    assert rows["navori"]["mark"] == "newer"
    assert rows["superpowers"]["mark"] == "major"
    assert (rows["ponytail"]["latest"], rows["ponytail"]["mark"]) == ("09c434ab", "newer")
    table = pins_mod.render(list(rows.values()))
    assert table.splitlines()[0].split() == ["pin", "pinned", "latest", "date", "mark"]


# Covers: R5 (round-protocol)
def test_skips_prereleases() -> None:
    assert pins_mod.latest("pypi:harbor", _fake(RESPONSES)) == ("0.25.0", "2026-10-25")
    beta = {"https://registry.npmjs.org/x": {"dist-tags": {"latest": "2.0.0-beta.1"}, "time": {}}}
    assert pins_mod.latest("npm:x", _fake(beta)) is None


# Covers: R5 (round-protocol)
def test_current_pins_have_no_mark(round_dir: Path) -> None:
    current = dict(RESPONSES)
    current["https://pypi.org/pypi/harbor/json"] = {"releases": {"0.23.0": [{"upload_time": "2026-09-01T00:00:00"}]}}
    current["https://api.github.com/repos/o/ponytail/commits?per_page=1"] = [
        {"sha": "e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156", "commit": {"committer": {"date": "2026-09-14T00:00:00Z"}}},
    ]
    rows = {r["pin"]: r for r in pins_mod.pin_rows(round_dir, _fake(current))}
    assert rows["harbor"]["mark"] == "" and rows["ponytail"]["mark"] == ""


# Covers: R6 (round-protocol)
def test_unreachable_source_is_unknown(
    round_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    partial = {k: v for k, v in RESPONSES.items() if "superpowers" not in k}
    rows = {r["pin"]: r for r in pins_mod.pin_rows(round_dir, _fake(partial))}
    assert (rows["superpowers"]["latest"], rows["superpowers"]["mark"]) == ("?", "unknown")
    assert rows["navori"]["latest"] == "0.12.3"

    def offline(url: str) -> object:
        raise OSError("offline")

    monkeypatch.setattr(pins_mod, "http_json", offline)
    assert cmd_pins(argparse.Namespace(round=str(round_dir))) == 0
    out = capsys.readouterr().out
    assert out.count("unknown") == 5
