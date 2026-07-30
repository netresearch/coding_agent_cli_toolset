"""
Regression tests for version-probe timeout fallback.

A slow binary (e.g. opengrep, ~2.5s for --version) can exceed the probe
timeout under parallel `make update` load. That must NOT be reported as
"not installed": the binary was found on disk, only the version probe
timed out. Detection signals the timeout distinctly and audit falls back
to the last known version from local_state.json.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

skip_on_windows = pytest.mark.skipif(sys.platform == "win32", reason="Uses Unix shell scripts as fake binaries")


# ===========================================================================
# 1. run_with_timeout distinguishes timeout (None) from other failures ("")
# ===========================================================================


class TestRunWithTimeout:
    @skip_on_windows
    def test_returns_none_on_timeout(self):
        from cli_audit.detection import run_with_timeout

        assert run_with_timeout(["sleep", "2"], timeout=0.1) is None

    def test_returns_empty_on_missing_binary(self):
        from cli_audit.detection import run_with_timeout

        assert run_with_timeout(["/nonexistent/definitely-not-a-binary"]) == ""

    @skip_on_windows
    def test_returns_line_on_success(self):
        from cli_audit.detection import run_with_timeout

        line = run_with_timeout(["echo", "tool 1.2.3"])
        assert line == "tool 1.2.3"


# ===========================================================================
# 2. get_version_line returns None when the probe timed out
# ===========================================================================


@pytest.fixture
def slow_binary(tmp_path: Path) -> str:
    """A fake binary that sleeps past the (patched) timeout."""
    script = tmp_path / "slowtool"
    script.write_text("#!/bin/sh\nsleep 2\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


class TestGetVersionLine:
    @skip_on_windows
    def test_returns_none_on_timeout_with_version_flag(self, slow_binary, monkeypatch):
        import cli_audit.detection as detection

        monkeypatch.setattr(detection, "TIMEOUT_SECONDS", 0.1)
        assert detection.get_version_line(slow_binary, "slowtool", version_flag="--version") is None

    @skip_on_windows
    def test_returns_none_on_timeout_with_generic_flags(self, slow_binary, monkeypatch):
        import cli_audit.detection as detection

        monkeypatch.setattr(detection, "TIMEOUT_SECONDS", 0.1)
        assert detection.get_version_line(slow_binary, "slowtool") is None

    @skip_on_windows
    def test_returns_empty_when_probe_fails_without_timeout(self, tmp_path, monkeypatch):
        """A binary that answers fast but uselessly still yields '' (not None)."""
        import cli_audit.detection as detection

        script = tmp_path / "quiettool"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setattr(detection, "TIMEOUT_SECONDS", 1)
        assert detection.get_version_line(str(script), "quiettool") == ""


# ===========================================================================
# 3. audit_tool_installation returns the timeout marker
# ===========================================================================


class TestAuditToolInstallationTimeout:
    def test_timeout_marker_when_binary_found_but_probe_times_out(self, monkeypatch):
        import cli_audit.detection as detection

        monkeypatch.setattr(detection, "find_paths", lambda cand, deep=False: ["/fake/bin/slowtool"])
        monkeypatch.setattr(
            detection,
            "get_version_line",
            lambda path, tool_name, version_flag=None, version_command=None: None,
        )
        monkeypatch.setattr(detection, "detect_install_method", lambda path, tool_name: "manual")

        result = detection.audit_tool_installation("slowtool", ("slowtool",))
        assert result == ("", detection.VERSION_PROBE_TIMEOUT, "/fake/bin/slowtool", "manual")

    def test_not_installed_unchanged_when_binary_missing(self, monkeypatch):
        import cli_audit.detection as detection

        monkeypatch.setattr(detection, "find_paths", lambda cand, deep=False: [])
        result = detection.audit_tool_installation("ghosttool", ("ghosttool",))
        assert result == ("", "X", "", "")


# ===========================================================================
# 4. audit falls back to last known local_state version on timeout
# ===========================================================================


@pytest.fixture
def local_state_file(tmp_path, monkeypatch) -> Path:
    state_file = tmp_path / "local_state.json"
    state_file.write_text(
        json.dumps(
            {
                "__meta__": {"schema_version": 2},
                "tools": {
                    "slowtool": {
                        "installed_version": "1.26.0",
                        "installed_path": "/home/user/.local/bin/slowtool",
                        "installed_method": "manual",
                        "status": "UP-TO-DATE",
                        "classification_reason": "Detected via path analysis: manual",
                        "category": "devops",
                        "hint": "",
                    }
                },
            }
        )
    )
    monkeypatch.setenv("CLI_AUDIT_LOCAL_FILE", str(state_file))
    return state_file


class TestTimeoutFallback:
    def test_falls_back_to_cached_version(self, local_state_file):
        import audit
        from cli_audit.detection import VERSION_PROBE_TIMEOUT

        version_num, version_line, path, method = audit._apply_probe_timeout_fallback(
            "slowtool", "", VERSION_PROBE_TIMEOUT, "/fake/bin/slowtool", "manual"
        )
        assert version_num == "1.26.0"
        assert "1.26.0" in version_line
        assert path == "/fake/bin/slowtool"
        assert method == "manual"

    def test_no_cached_version_reports_unknown(self, tmp_path, monkeypatch):
        import audit
        from cli_audit.detection import VERSION_PROBE_TIMEOUT

        state_file = tmp_path / "empty_state.json"
        state_file.write_text(json.dumps({"__meta__": {"schema_version": 2}, "tools": {}}))
        monkeypatch.setenv("CLI_AUDIT_LOCAL_FILE", str(state_file))

        version_num, version_line, path, method = audit._apply_probe_timeout_fallback(
            "slowtool", "", VERSION_PROBE_TIMEOUT, "/fake/bin/slowtool", "manual"
        )
        assert version_num == ""
        assert version_line == ""
        assert path == "/fake/bin/slowtool"

    def test_passthrough_when_no_timeout(self, local_state_file):
        import audit

        result = audit._apply_probe_timeout_fallback("slowtool", "2.0.0", "slowtool 2.0.0", "/usr/bin/slowtool", "apt")
        assert result == ("2.0.0", "slowtool 2.0.0", "/usr/bin/slowtool", "apt")
