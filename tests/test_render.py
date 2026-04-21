"""Tests for ``cli_audit.render`` — pipe-delimited audit table rendering."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from cli_audit import pins as pins_module
from cli_audit.render import render_table


@pytest.fixture(autouse=True)
def _no_grouping(monkeypatch: pytest.MonkeyPatch):
    """Disable category grouping so every test emits a flat table."""
    monkeypatch.setenv("CLI_AUDIT_GROUP", "0")
    # The render module reads this flag at import time; patch the binding.
    import cli_audit.render as render_mod

    monkeypatch.setattr(render_mod, "GROUP_BY_CATEGORY", False)


@pytest.fixture(autouse=True)
def _no_color_no_links(monkeypatch: pytest.MonkeyPatch):
    """Keep the output plain so assertions don't fight ANSI / OSC8."""
    import cli_audit.render as render_mod

    monkeypatch.setattr(render_mod, "USE_COLOR", False)
    monkeypatch.setattr(render_mod, "ENABLE_LINKS", False)
    monkeypatch.setattr(render_mod, "USE_EMOJI", False)


@pytest.fixture
def empty_pins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the pins reader at an empty file so nothing is pinned."""
    path = tmp_path / "pins.json"
    path.write_text("{}")
    pins_module.reset_cache()
    monkeypatch.setattr(pins_module, "DEFAULT_PINS_PATH", str(path))
    yield
    pins_module.reset_cache()


@pytest.fixture
def pinned_world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A pins.json covering the shapes the renderer has to handle."""
    import json

    path = tmp_path / "pins.json"
    path.write_text(
        json.dumps(
            {
                "ripgrep": "14.1.0",
                "php": {"8.5": "8.5.3", "8.2": "never"},
            }
        )
    )
    pins_module.reset_cache()
    monkeypatch.setattr(pins_module, "DEFAULT_PINS_PATH", str(path))
    yield
    pins_module.reset_cache()


def _render(tools: list[dict[str, Any]]) -> list[str]:
    """Capture the rendered table lines (minus header)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        render_table(tools)
    lines = buf.getvalue().splitlines()
    # First line is always the header
    assert lines[0] == "state|tool|installed|latest_upstream|notes"
    return lines[1:]


class TestHeader:
    def test_header_has_five_columns(self, empty_pins):
        buf = io.StringIO()
        with redirect_stdout(buf):
            render_table([])
        assert buf.getvalue().strip() == "state|tool|installed|latest_upstream|notes"


class TestNotesColumn:
    def test_plain_installed_shows_method(self, empty_pins):
        rows = _render(
            [
                {
                    "tool": "ripgrep",
                    "installed": "14.1.0",
                    "latest_upstream": "14.1.0",
                    "status": "UP-TO-DATE",
                    "installed_method": "cargo",
                }
            ]
        )
        assert rows == ["✓|ripgrep|14.1.0|14.1.0|cargo"]

    def test_missing_method_yields_empty_notes(self, empty_pins):
        rows = _render(
            [
                {
                    "tool": "mystery",
                    "installed": "1.0",
                    "latest_upstream": "1.0",
                    "status": "UP-TO-DATE",
                }
            ]
        )
        # Trailing separator, empty notes cell.
        assert rows == ["✓|mystery|1.0|1.0|"]


class TestPinRendering:
    def test_specific_pin_appears_next_to_installed(self, pinned_world):
        rows = _render(
            [
                {
                    "tool": "ripgrep",
                    "installed": "14.1.0",
                    "latest_upstream": "14.1.0",
                    "status": "UP-TO-DATE",
                    "installed_method": "cargo",
                }
            ]
        )
        assert rows == ["✓|ripgrep|14.1.0 [PIN:14.1.0]|14.1.0|cargo"]

    def test_violated_pin_becomes_conflict_icon(self, pinned_world):
        # php@8.5 pinned to 8.5.3, installed 8.5.5 → pin violation.
        rows = _render(
            [
                {
                    "tool": "php@8.5",
                    "installed": "8.5.5",
                    "latest_upstream": "8.5.5",
                    "status": "UP-TO-DATE",
                    "installed_method": "apt",
                }
            ]
        )
        assert rows == ["⚠|php@8.5|8.5.5 [PIN:8.5.3]|8.5.5|apt"]

    def test_never_plus_absent_renders_up_to_date(self, pinned_world):
        # php@8.2 pinned never, not installed → ✓ (intent honored).
        rows = _render(
            [
                {
                    "tool": "php@8.2",
                    "installed": "",
                    "latest_upstream": "8.2.30",
                    "status": "NOT INSTALLED",
                    "installed_method": "",
                }
            ]
        )
        assert rows == ["✓|php@8.2| [PIN:never]|8.2.30|"]


class TestConflictPrefixStripping:
    """Regression test for the ANSI-vs-raw comparison bug — the sentinel
    ``CONFLICT: …`` must be stripped before coloring, not after."""

    def test_conflict_prefix_stripped(self, empty_pins):
        rows = _render(
            [
                {
                    "tool": "double-rg",
                    "installed": "CONFLICT: 14.0.0 at /usr/bin vs 14.1.0 at ~/.cargo/bin",
                    "latest_upstream": "14.1.0",
                    "status": "CONFLICT",
                    "installed_method": "multiple",
                }
            ]
        )
        # Row starts with the conflict icon; installed column must NOT still
        # carry the "CONFLICT: " prefix.
        assert len(rows) == 1
        assert rows[0].startswith("⚠|double-rg|")
        _, _, installed_col, _, _ = rows[0].split("|")
        assert not installed_col.startswith("CONFLICT:"), installed_col
        assert "14.0.0 at" in installed_col


# (Env-var override of DEFAULT_PINS_PATH is covered by
# ``tests/test_pins.py::TestDefaultPath::test_env_override``.)
