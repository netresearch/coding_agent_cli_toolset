"""Tests for the version-pin reader (``cli_audit.pins``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli_audit.pins import (
    apply_pin_to_status,
    is_never,
    is_pinned,
    load_pins,
    lookup_pin,
    reset_cache,
    should_skip,
)


@pytest.fixture
def pins_file(tmp_path: Path) -> Path:
    """Write a realistic pins.json and return its path."""
    path = tmp_path / "pins.json"
    path.write_text(
        json.dumps(
            {
                "ripgrep": "14.1.0",
                "php": {
                    "8.5": "8.5.3",
                    "8.2": "never",
                },
                "node": {"22": "never"},
                # Intentionally non-string values to exercise defensive parsing
                "bogus_int": 42,
                "bogus_null": None,
            }
        )
    )
    return path


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure load_pins's LRU cache doesn't leak state between tests."""
    reset_cache()
    yield
    reset_cache()


class TestLoadPins:
    def test_loads_valid_json(self, pins_file: Path):
        data = load_pins(str(pins_file))
        assert data["ripgrep"] == "14.1.0"
        assert data["php"]["8.5"] == "8.5.3"

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert load_pins(str(tmp_path / "does-not-exist.json")) == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path):
        path = tmp_path / "pins.json"
        path.write_text("{ not valid json")
        assert load_pins(str(path)) == {}

    def test_invalid_json_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        path = tmp_path / "pins.json"
        path.write_text("{ not valid json")
        with caplog.at_level("WARNING", logger="cli_audit.pins"):
            load_pins(str(path))
        assert any("not valid JSON" in r.message for r in caplog.records), caplog.records

    def test_top_level_list_rejected(self, tmp_path: Path):
        path = tmp_path / "pins.json"
        path.write_text("[1, 2, 3]")
        assert load_pins(str(path)) == {}

    def test_top_level_list_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        path = tmp_path / "pins.json"
        path.write_text("[1, 2, 3]")
        with caplog.at_level("WARNING", logger="cli_audit.pins"):
            load_pins(str(path))
        assert any("top-level object" in r.message for r in caplog.records)

    def test_cache_returns_same_object(self, pins_file: Path):
        first = load_pins(str(pins_file))
        second = load_pins(str(pins_file))
        assert first is second


class TestLookupPin:
    def test_single_version_tool(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert lookup_pin("ripgrep", pins) == "14.1.0"

    def test_multi_version_tool_with_cycle(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert lookup_pin("php@8.5", pins) == "8.5.3"
        assert lookup_pin("php@8.2", pins) == "never"

    def test_multi_version_tool_unknown_cycle(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert lookup_pin("php@9.0", pins) == ""

    def test_multi_version_tool_without_cycle_returns_empty(self, pins_file: Path):
        """Bare 'php' lookup on a nested entry returns empty; the caller must
        supply a cycle to resolve nested pins."""
        pins = load_pins(str(pins_file))
        assert lookup_pin("php", pins) == ""

    def test_tool_not_in_pins(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert lookup_pin("git-branchless", pins) == ""

    def test_non_string_values_are_ignored(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert lookup_pin("bogus_int", pins) == ""
        assert lookup_pin("bogus_null", pins) == ""


class TestIsPinnedAndIsNever:
    def test_is_pinned_true_for_version(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert is_pinned("ripgrep", pins)

    def test_is_pinned_true_for_never(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert is_pinned("php@8.2", pins)

    def test_is_pinned_false_for_unknown(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert not is_pinned("ripgrep@1.0", pins)

    def test_is_never_only_true_for_never_sentinel(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert is_never("php@8.2", pins)
        assert not is_never("ripgrep", pins)
        assert not is_never("git-branchless", pins)


class TestShouldSkip:
    def test_never_always_skips(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert should_skip("php@8.2", "9.9.9", pins)

    def test_skip_when_pin_matches_latest(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert should_skip("ripgrep", "14.1.0", pins)

    def test_no_skip_when_pin_differs_from_latest(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert not should_skip("ripgrep", "15.0.0", pins)

    def test_no_skip_when_not_pinned(self, pins_file: Path):
        pins = load_pins(str(pins_file))
        assert not should_skip("git-branchless", "0.10.0", pins)


class TestApplyPinToStatus:
    @pytest.mark.parametrize(
        "status", ["UP-TO-DATE", "OUTDATED", "NOT INSTALLED", "CONFLICT", "UNKNOWN"]
    )
    def test_no_pin_passes_through(self, status: str):
        assert apply_pin_to_status(status, "1.0", pin="") == status

    def test_never_plus_not_installed_is_up_to_date(self):
        assert apply_pin_to_status("NOT INSTALLED", "", "never") == "UP-TO-DATE"

    def test_never_plus_installed_is_conflict(self):
        assert apply_pin_to_status("UP-TO-DATE", "1.0", "never") == "CONFLICT"

    def test_specific_pin_matches_installed_is_up_to_date(self):
        # Pin honored even when snapshot thought it was outdated.
        assert apply_pin_to_status("OUTDATED", "1.2.3", "1.2.3") == "UP-TO-DATE"

    def test_specific_pin_does_not_match_installed_is_conflict(self):
        assert apply_pin_to_status("UP-TO-DATE", "1.2.4", "1.2.3") == "CONFLICT"

    def test_specific_pin_with_nothing_installed_is_not_installed(self):
        assert apply_pin_to_status("NOT INSTALLED", "", "1.2.3") == "NOT INSTALLED"


class TestDefaultPath:
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """``CLI_AUDIT_PINS_PATH`` should override the default location."""
        path = tmp_path / "alt-pins.json"
        path.write_text('{"ripgrep": "9.9.9"}')
        monkeypatch.setenv("CLI_AUDIT_PINS_PATH", str(path))
        # Re-import to pick up the new env var; the module computes the path
        # at import time.
        import importlib

        import cli_audit.pins as pins_mod

        importlib.reload(pins_mod)
        try:
            assert pins_mod.load_pins()["ripgrep"] == "9.9.9"
        finally:
            # Restore clean module state for other tests.
            importlib.reload(pins_mod)
