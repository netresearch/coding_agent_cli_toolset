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


@pytest.fixture(autouse=True)
def _empty_user_config(monkeypatch: pytest.MonkeyPatch):
    """Default every test to an empty user config.

    Without this the renderer picks up the developer's real
    ``~/.config/cli-audit/config.yml`` and leaks ``[AUTO]`` markers into
    unrelated assertions. Tests that exercise the AUTO marker override
    this with ``monkeypatch.setattr(render_mod, 'load_config', ...)``.
    """
    import cli_audit.render as render_mod
    from cli_audit.config import Config

    monkeypatch.setattr(render_mod, "load_config", lambda: Config())


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

    def test_stale_patch_pin_is_informational_not_conflict(self, pinned_world):
        """On multi-version rows, a patch-level pin that no longer matches
        ``installed`` is marked ``stale`` but does not escalate the row to
        CONFLICT — the schema can't distinguish a stale skip-marker from a
        deliberate patch-hold the world moved past."""
        rows = _render(
            [
                {
                    "tool": "php@8.5",
                    "installed": "8.5.5",
                    "latest_upstream": "8.5.5",
                    "status": "UP-TO-DATE",
                    "installed_method": "apt",
                    "is_multi_version": True,
                    "version_cycle": "8.5",
                }
            ]
        )
        assert rows == ["✓|php@8.5|8.5.5 [PIN:8.5.3 stale]|8.5.5|apt"]

    def test_cycle_hold_any_patch_is_up_to_date(self, monkeypatch, tmp_path):
        """``python@3.12`` pinned to the cycle string ``"3.12"`` means
        "stay within 3.12.x". An installed ``3.12.7`` is UP-TO-DATE even
        when ``latest_upstream`` is newer."""
        import json

        path = tmp_path / "pins.json"
        path.write_text(json.dumps({"python": {"3.12": "3.12"}}))
        pins_module.reset_cache()
        monkeypatch.setattr(pins_module, "DEFAULT_PINS_PATH", str(path))
        rows = _render(
            [
                {
                    "tool": "python@3.12",
                    "installed": "3.12.7",
                    "latest_upstream": "3.12.13",
                    "status": "OUTDATED",
                    "installed_method": "apt",
                    "is_multi_version": True,
                    "version_cycle": "3.12",
                }
            ]
        )
        assert rows == ["✓|python@3.12|3.12.7 [CYCLE:3.12]|3.12.13|apt"]

    def test_single_version_violated_pin_still_conflicts(self, pinned_world):
        """Outside the multi-version world there's no cycle notion — an
        exact pin that doesn't match installed is a real conflict."""
        rows = _render(
            [
                {
                    "tool": "ripgrep",
                    "installed": "15.0.0",
                    "latest_upstream": "15.0.0",
                    "status": "UP-TO-DATE",
                    "installed_method": "cargo",
                }
            ]
        )
        assert rows == ["⚠|ripgrep|15.0.0 [PIN:14.1.0]|15.0.0|cargo"]

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
                    "is_multi_version": True,
                    "version_cycle": "8.2",
                }
            ]
        )
        assert rows == ["✓|php@8.2| [PIN:never]|8.2.30|"]

    def test_never_plus_installed_is_conflict(self, pinned_world, monkeypatch, tmp_path):
        """PIN:never applied but the tool is present → ⚠️ conflict."""
        import json

        path = tmp_path / "pins.json"
        path.write_text(json.dumps({"ruby": {"3.3": "never"}}))
        pins_module.reset_cache()
        monkeypatch.setattr(pins_module, "DEFAULT_PINS_PATH", str(path))
        rows = _render(
            [
                {
                    "tool": "ruby@3.3",
                    "installed": "3.3.6",
                    "latest_upstream": "3.3.11",
                    "status": "OUTDATED",
                    "installed_method": "manual",
                    "is_multi_version": True,
                    "version_cycle": "3.3",
                }
            ]
        )
        assert rows == ["⚠|ruby@3.3|3.3.6 [PIN:never]|3.3.11|manual"]


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


class TestAutoMarker:
    """Tests for the ``[AUTO]`` marker driven by explicit config entries."""

    def _config(self, tools: dict[str, bool | None]):
        """Build a minimal ``Config`` with per-tool auto_update values."""
        from cli_audit.config import Config, ToolConfig

        return Config(tools={k: ToolConfig(auto_update=v) for k, v in tools.items()})

    def test_auto_marker_shown_when_explicit_true(
        self, empty_pins, monkeypatch: pytest.MonkeyPatch
    ):
        import cli_audit.render as render_mod

        cfg = self._config({"ripgrep": True})
        monkeypatch.setattr(render_mod, "load_config", lambda: cfg)
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
        assert rows == ["✓|ripgrep|14.1.0 [AUTO]|14.1.0|cargo"]

    def test_auto_marker_hidden_when_pin_is_never(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """AUTO and PIN:never contradict each other — don't show both."""
        import json

        import cli_audit.render as render_mod

        path = tmp_path / "pins.json"
        path.write_text(json.dumps({"ruby": {"3.3": "never"}}))
        pins_module.reset_cache()
        monkeypatch.setattr(pins_module, "DEFAULT_PINS_PATH", str(path))
        cfg = self._config({"ruby": True})  # base auto_update=True
        monkeypatch.setattr(render_mod, "load_config", lambda: cfg)
        rows = _render(
            [
                {
                    "tool": "ruby@3.3",
                    "installed": "3.3.6",
                    "latest_upstream": "3.3.11",
                    "status": "OUTDATED",
                    "installed_method": "manual",
                    "is_multi_version": True,
                    "version_cycle": "3.3",
                }
            ]
        )
        # [AUTO] must NOT appear; the row is a ⚠️ conflict only.
        assert rows == ["⚠|ruby@3.3|3.3.6 [PIN:never]|3.3.11|manual"]

    def test_auto_marker_inherits_from_base_tool(
        self, empty_pins, monkeypatch: pytest.MonkeyPatch
    ):
        """``python: auto_update: true`` should surface as [AUTO] on
        ``python@3.14`` rows (base-tool fallback)."""
        import cli_audit.render as render_mod

        cfg = self._config({"python": True})
        monkeypatch.setattr(render_mod, "load_config", lambda: cfg)
        rows = _render(
            [
                {
                    "tool": "python@3.14",
                    "installed": "3.14.4",
                    "latest_upstream": "3.14.4",
                    "status": "UP-TO-DATE",
                    "installed_method": "manual",
                    "is_multi_version": True,
                    "version_cycle": "3.14",
                }
            ]
        )
        assert rows == ["✓|python@3.14|3.14.4 [AUTO]|3.14.4|manual"]


# (Env-var override of DEFAULT_PINS_PATH is covered by
# ``tests/test_pins.py::TestDefaultPath::test_env_override``.)
