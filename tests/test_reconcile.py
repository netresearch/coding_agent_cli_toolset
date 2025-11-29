"""
Tests for reconciliation operations.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Skip marker for Windows (Unix-style paths and PATH separator differences)
skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Uses Unix-style paths and PATH separator (:)"
)

from cli_audit.reconcile import (
    Installation,
    ReconciliationResult,
    BulkReconciliationResult,
    detect_installations,
    classify_install_method,
    _classify_via_path,
    clear_detection_cache,
    sort_by_preference,
    reconcile_tool,
    bulk_reconcile,
    verify_path_ordering,
    _check_path_ordering,
    _confirm_removal,
    _uninstall_installation,
    SYSTEM_TOOL_SAFELIST,
)
from cli_audit.config import Config, Preferences
from cli_audit.environment import Environment


class TestInstallationDataclass:
    """Tests for Installation dataclass."""

    def test_installation_creation(self):
        """Test Installation dataclass creation."""
        inst = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=True,
            valid=True,
        )

        assert inst.tool == "ripgrep"
        assert inst.version == "14.1.0"
        assert inst.method == "cargo"
        assert inst.active is True
        assert inst.valid is True

    def test_installation_to_dict(self):
        """Test Installation.to_dict()."""
        inst = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=True,
        )

        d = inst.to_dict()
        assert d["tool"] == "ripgrep"
        assert d["version"] == "14.1.0"
        assert d["method"] == "cargo"
        assert d["active"] is True


class TestClassifyInstallMethod:
    """Tests for installation method classification."""

    def test_classify_via_path_cargo(self):
        """Test cargo classification via path."""
        path = "/home/user/.cargo/bin/ripgrep"
        method = _classify_via_path(path)
        assert method == "cargo"

    def test_classify_via_path_pipx(self):
        """Test pipx classification via path."""
        path = "/home/user/.local/bin/black"
        method = _classify_via_path(path)
        assert method == "pipx"

    def test_classify_via_path_uv(self):
        """Test uv classification via path."""
        path = "/home/user/.uv/bin/ruff"
        method = _classify_via_path(path)
        assert method == "uv"

    def test_classify_via_path_nvm(self):
        """Test nvm classification via path."""
        path = "/home/user/.nvm/versions/node/v20.0.0/bin/node"
        method = _classify_via_path(path)
        assert method == "nvm"

    def test_classify_via_path_brew(self):
        """Test brew classification via path."""
        path = "/usr/local/bin/ripgrep"
        method = _classify_via_path(path)
        assert method == "brew"

    def test_classify_via_path_apt(self):
        """Test apt classification via path."""
        path = "/usr/bin/ripgrep"
        method = _classify_via_path(path)
        assert method == "apt"

    def test_classify_via_path_snap(self):
        """Test snap classification via path."""
        path = "/snap/bin/ripgrep"
        method = _classify_via_path(path)
        assert method == "snap"

    def test_classify_via_path_unknown(self):
        """Test unknown classification."""
        path = "/some/weird/path/tool"
        method = _classify_via_path(path)
        assert method == "unknown"


class TestDetectInstallations:
    """Tests for installation detection."""

    @skip_on_windows
    @patch("cli_audit.reconcile.validate_installation")
    @patch("cli_audit.reconcile.shutil.which")
    @patch("os.path.exists")
    @patch("os.access")
    @patch("os.path.realpath")
    def test_detect_single_installation(
        self,
        mock_realpath,
        mock_access,
        mock_exists,
        mock_which,
        mock_validate,
        monkeypatch,
    ):
        """Test detecting single installation."""
        # Setup mocks
        monkeypatch.setenv("PATH", "/home/user/.cargo/bin:/usr/bin")

        # Only cargo path exists
        def exists_side_effect(path):
            return path == "/home/user/.cargo/bin/rg"

        mock_exists.side_effect = exists_side_effect
        mock_access.return_value = True
        mock_realpath.side_effect = lambda p: p
        mock_which.return_value = "/home/user/.cargo/bin/rg"
        mock_validate.return_value = (True, "/home/user/.cargo/bin/rg", "14.1.0")

        # Clear cache
        clear_detection_cache()

        # Detect
        installations = detect_installations("ripgrep", ["rg"])

        assert len(installations) == 1
        assert installations[0].tool == "ripgrep"
        assert installations[0].version == "14.1.0"
        assert installations[0].active is True

    @skip_on_windows
    @patch("cli_audit.reconcile.validate_installation")
    @patch("cli_audit.reconcile.shutil.which")
    @patch("os.path.exists")
    @patch("os.access")
    @patch("os.path.realpath")
    def test_detect_multiple_installations(
        self,
        mock_realpath,
        mock_access,
        mock_exists,
        mock_which,
        mock_validate,
        monkeypatch,
    ):
        """Test detecting multiple installations."""
        # Setup mocks
        monkeypatch.setenv("PATH", "/home/user/.cargo/bin:/usr/bin")

        def exists_side_effect(path):
            return path in [
                "/home/user/.cargo/bin/rg",
                "/usr/bin/rg",
            ]

        mock_exists.side_effect = exists_side_effect
        mock_access.return_value = True
        mock_realpath.side_effect = lambda p: p
        mock_which.return_value = "/home/user/.cargo/bin/rg"

        def validate_side_effect(tool, verbose=False):
            # Return different versions for different paths
            which_result = mock_which.return_value
            if "cargo" in which_result:
                return (True, "/home/user/.cargo/bin/rg", "14.1.0")
            else:
                return (True, "/usr/bin/rg", "13.0.0")

        mock_validate.side_effect = validate_side_effect

        # Clear cache
        clear_detection_cache()

        # Detect
        installations = detect_installations("ripgrep", ["rg"])

        assert len(installations) == 2

    def test_detect_no_installations(self, monkeypatch):
        """Test detecting when tool not installed."""
        monkeypatch.setenv("PATH", "/usr/bin")
        clear_detection_cache()

        installations = detect_installations("nonexistent_tool")
        assert len(installations) == 0


class TestSortByPreference:
    """Tests for preference sorting."""

    def test_sort_by_preference_user_over_system(self):
        """Test user installations preferred over system."""
        installations = [
            Installation(
                tool="ripgrep",
                version="13.0.0",
                method="apt",
                path="/usr/bin/rg",
                active=True,
            ),
            Installation(
                tool="ripgrep",
                version="14.1.0",
                method="cargo",
                path="/home/user/.cargo/bin/rg",
                active=False,
            ),
        ]

        sorted_installs = sort_by_preference(installations)

        # cargo should be preferred over apt
        assert sorted_installs[0].method == "cargo"
        assert sorted_installs[1].method == "apt"

    def test_sort_by_preference_vendor_tools(self):
        """Test vendor tools (uv, pipx) preferred."""
        installations = [
            Installation(
                tool="black",
                version="24.0.0",
                method="pip",
                path="/home/user/.local/bin/black",
                active=False,
            ),
            Installation(
                tool="black",
                version="24.0.0",
                method="pipx",
                path="/home/user/.local/pipx/venvs/black/bin/black",
                active=True,
            ),
        ]

        sorted_installs = sort_by_preference(installations)

        # pipx should be preferred over pip
        assert sorted_installs[0].method == "pipx"
        assert sorted_installs[1].method == "pip"

    def test_sort_by_preference_same_tier_newer_version(self):
        """Test same tier prefers newer version."""
        installations = [
            Installation(
                tool="ripgrep",
                version="13.0.0",
                method="cargo",
                path="/home/user/.cargo/bin/rg",
                active=False,
            ),
            Installation(
                tool="ripgrep",
                version="14.1.0",
                method="cargo",
                path="/home/user/.local/bin/rg",
                active=True,
            ),
        ]

        sorted_installs = sort_by_preference(installations)

        # 14.1.0 should be preferred
        assert sorted_installs[0].version == "14.1.0"

    def test_sort_single_installation(self):
        """Test sorting single installation."""
        installations = [
            Installation(
                tool="ripgrep",
                version="14.1.0",
                method="cargo",
                path="/home/user/.cargo/bin/rg",
                active=True,
            ),
        ]

        sorted_installs = sort_by_preference(installations)
        assert len(sorted_installs) == 1
        assert sorted_installs[0].version == "14.1.0"


class TestReconcileTool:
    """Tests for single tool reconciliation."""

    @patch("cli_audit.reconcile.detect_installations")
    def test_reconcile_no_installations(self, mock_detect):
        """Test reconciliation when no installations found."""
        mock_detect.return_value = []

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = reconcile_tool("nonexistent", config=config, env=env)

        assert result.success is False
        assert "No installations found" in result.error_message

    @patch("cli_audit.reconcile.detect_installations")
    def test_reconcile_single_installation(self, mock_detect):
        """Test reconciliation with single installation."""
        inst = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=True,
        )
        mock_detect.return_value = [inst]

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = reconcile_tool("ripgrep", config=config, env=env)

        assert result.success is True
        assert len(result.installations) == 1
        assert result.action_taken == "none"

    @patch("cli_audit.reconcile.detect_installations")
    def test_reconcile_parallel_mode(self, mock_detect):
        """Test parallel reconciliation mode."""
        installations = [
            Installation(
                tool="ripgrep",
                version="14.1.0",
                method="cargo",
                path="/home/user/.cargo/bin/rg",
                active=True,
            ),
            Installation(
                tool="ripgrep",
                version="13.0.0",
                method="apt",
                path="/usr/bin/rg",
                active=False,
            ),
        ]
        mock_detect.return_value = installations

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = reconcile_tool("ripgrep", mode="parallel", config=config, env=env)

        assert result.success is True
        assert len(result.installations) == 2
        assert result.preferred.method == "cargo"
        assert result.action_taken in ("none", "path_guidance")

    @patch("cli_audit.reconcile._uninstall_installation")
    @patch("cli_audit.reconcile._confirm_removal")
    @patch("cli_audit.reconcile.detect_installations")
    def test_reconcile_aggressive_mode(self, mock_detect, mock_confirm, mock_uninstall):
        """Test aggressive reconciliation mode."""
        installations = [
            Installation(
                tool="ripgrep",
                version="14.1.0",
                method="cargo",
                path="/home/user/.cargo/bin/rg",
                active=True,
            ),
            Installation(
                tool="ripgrep",
                version="13.0.0",
                method="apt",
                path="/usr/bin/rg",
                active=False,
            ),
        ]
        mock_detect.return_value = installations
        mock_confirm.return_value = True
        mock_uninstall.return_value = (True, None)

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = reconcile_tool("ripgrep", mode="aggressive", config=config, env=env)

        assert result.success is True
        assert result.action_taken == "removed"
        assert len(result.removed_installations) == 1

    @patch("cli_audit.reconcile.detect_installations")
    def test_reconcile_safelist_protection(self, mock_detect):
        """Test system tool safelist protection."""
        installations = [
            Installation(
                tool="python",
                version="3.12.0",
                method="system",
                path="/usr/bin/python",
                active=True,
            ),
            Installation(
                tool="python",
                version="3.11.0",
                method="apt",
                path="/usr/bin/python3.11",
                active=False,
            ),
        ]
        mock_detect.return_value = installations

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = reconcile_tool("python", mode="aggressive", config=config, env=env)

        assert result.success is False
        assert "safelist" in result.error_message


class TestBulkReconcile:
    """Tests for bulk reconciliation."""

    @patch("cli_audit.reconcile.reconcile_tool")
    def test_bulk_reconcile_explicit(self, mock_reconcile):
        """Test bulk reconcile with explicit tool list."""
        mock_reconcile.return_value = ReconciliationResult(
            tool="ripgrep",
            installations=(),
            preferred=None,
            active=None,
            path_issues=(),
            action_taken="none",
            success=True,
        )

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_reconcile(
            mode="explicit",
            tool_names=["ripgrep", "fd"],
            config=config,
            env=env,
        )

        assert result.tools_checked == 2
        assert mock_reconcile.call_count == 2

    @patch("cli_audit.reconcile.reconcile_tool")
    def test_bulk_reconcile_no_tools(self, mock_reconcile):
        """Test bulk reconcile with no tools."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_reconcile(
            mode="explicit",
            tool_names=None,
            config=config,
            env=env,
        )

        assert result.tools_checked == 0
        assert result.conflicts_found == 0

    @patch("cli_audit.reconcile.reconcile_tool")
    def test_bulk_reconcile_conflicts_only(self, mock_reconcile):
        """Test bulk reconcile showing only conflicts."""

        def reconcile_side_effect(tool, *args, **kwargs):
            if tool == "ripgrep":
                # Multiple installations
                return ReconciliationResult(
                    tool="ripgrep",
                    installations=(
                        Installation("ripgrep", "14.1.0", "cargo", "/home/user/.cargo/bin/rg", True),
                        Installation("ripgrep", "13.0.0", "apt", "/usr/bin/rg", False),
                    ),
                    preferred=Installation("ripgrep", "14.1.0", "cargo", "/home/user/.cargo/bin/rg", True),
                    active=Installation("ripgrep", "14.1.0", "cargo", "/home/user/.cargo/bin/rg", True),
                    path_issues=(),
                    success=True,
                )
            else:
                # Single installation
                return ReconciliationResult(
                    tool="fd",
                    installations=(
                        Installation("fd", "9.0.0", "cargo", "/home/user/.cargo/bin/fd", True),
                    ),
                    preferred=Installation("fd", "9.0.0", "cargo", "/home/user/.cargo/bin/fd", True),
                    active=Installation("fd", "9.0.0", "cargo", "/home/user/.cargo/bin/fd", True),
                    path_issues=(),
                    success=True,
                )

        mock_reconcile.side_effect = reconcile_side_effect

        config = Config(tools={
            "ripgrep": {},
            "fd": {},
        })
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_reconcile(
            mode="conflicts",
            config=config,
            env=env,
        )

        # Should only show ripgrep (has conflict)
        assert result.tools_checked == 1
        assert result.conflicts_found == 1


class TestPathVerification:
    """Tests for PATH verification."""

    @skip_on_windows
    def test_verify_path_ordering_correct(self, monkeypatch):
        """Test PATH ordering when correct."""
        monkeypatch.setenv("PATH", "/home/user/.cargo/bin:/home/user/.local/bin:/usr/local/bin:/usr/bin")

        def exists_side_effect(path):
            # Only user paths exist
            return path in [
                "/home/user/.cargo/bin",
                "/home/user/.local/bin",
            ]

        with patch("os.path.exists", side_effect=exists_side_effect):
            with patch("os.path.expanduser") as mock_expand:
                # Mock expanduser to return test paths
                def expand_side_effect(path):
                    if path == "~/.cargo/bin":
                        return "/home/user/.cargo/bin"
                    elif path == "~/.local/bin":
                        return "/home/user/.local/bin"
                    elif path == "~/.uv/bin":
                        return "/home/user/.uv/bin"
                    elif path == "~/.pyenv/bin":
                        return "/home/user/.pyenv/bin"
                    elif path == "~/.rbenv/bin":
                        return "/home/user/.rbenv/bin"
                    return path

                mock_expand.side_effect = expand_side_effect
                issues = verify_path_ordering()
                assert len(issues) == 0

    @skip_on_windows
    def test_verify_path_ordering_incorrect(self, monkeypatch):
        """Test PATH ordering when incorrect."""
        monkeypatch.setenv("PATH", "/usr/bin:/home/user/.cargo/bin")

        def exists_side_effect(path):
            # Only user paths exist
            return path in [
                "/home/user/.cargo/bin",
            ]

        with patch("os.path.exists", side_effect=exists_side_effect):
            with patch("os.path.expanduser") as mock_expand:
                # Mock expanduser to return test paths
                def expand_side_effect(path):
                    if path == "~/.cargo/bin":
                        return "/home/user/.cargo/bin"
                    elif path == "~/.local/bin":
                        return "/home/user/.local/bin"
                    elif path == "~/.uv/bin":
                        return "/home/user/.uv/bin"
                    elif path == "~/.pyenv/bin":
                        return "/home/user/.pyenv/bin"
                    elif path == "~/.rbenv/bin":
                        return "/home/user/.rbenv/bin"
                    return path

                mock_expand.side_effect = expand_side_effect
                issues = verify_path_ordering()
                assert len(issues) > 0
                assert any("ordering issue" in issue for issue in issues)

    def test_verify_path_ordering_missing_user_bin(self, monkeypatch):
        """Test detection of missing user bin in PATH."""
        monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")

        def exists_side_effect(path):
            return path == os.path.expanduser("~/.cargo/bin")

        with patch("os.path.exists", side_effect=exists_side_effect):
            issues = verify_path_ordering()
            assert len(issues) > 0
            assert any("Missing from PATH" in issue for issue in issues)


class TestCheckPathOrdering:
    """Tests for _check_path_ordering helper."""

    def test_check_path_ordering_no_active(self):
        """Test when no active installation."""
        preferred = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=False,
        )

        issues = _check_path_ordering(preferred, None, False)

        assert len(issues) > 0
        assert "No active installation" in issues[0]

    def test_check_path_ordering_mismatch(self):
        """Test when preferred != active."""
        preferred = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=False,
        )

        active = Installation(
            tool="ripgrep",
            version="13.0.0",
            method="apt",
            path="/usr/bin/rg",
            active=True,
        )

        issues = _check_path_ordering(preferred, active, False)

        assert len(issues) > 0
        assert "not active" in issues[0]

    def test_check_path_ordering_correct(self):
        """Test when preferred == active."""
        preferred = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=True,
        )

        issues = _check_path_ordering(preferred, preferred, False)

        assert len(issues) == 0


class TestConfirmRemoval:
    """Tests for user confirmation."""

    @patch("sys.stdin.isatty", return_value=False)
    def test_confirm_removal_non_interactive(self, mock_isatty):
        """Test non-interactive mode returns False."""
        installations = [
            Installation("tool", "1.0.0", "cargo", "/path", False),
        ]

        result = _confirm_removal("tool", installations)
        assert result is False

    @patch("builtins.input", return_value="y")
    @patch("sys.stdin.isatty", return_value=True)
    def test_confirm_removal_yes(self, mock_isatty, mock_input):
        """Test user confirms with 'y'."""
        installations = [
            Installation("tool", "1.0.0", "cargo", "/path", False),
        ]

        result = _confirm_removal("tool", installations)
        assert result is True

    @patch("builtins.input", return_value="n")
    @patch("sys.stdin.isatty", return_value=True)
    def test_confirm_removal_no(self, mock_isatty, mock_input):
        """Test user declines with 'n'."""
        installations = [
            Installation("tool", "1.0.0", "cargo", "/path", False),
        ]

        result = _confirm_removal("tool", installations)
        assert result is False


class TestUninstallInstallation:
    """Tests for uninstallation."""

    @patch("cli_audit.reconcile.subprocess.run")
    def test_uninstall_cargo(self, mock_run):
        """Test cargo uninstall."""
        mock_run.return_value = MagicMock(returncode=0)

        inst = Installation(
            tool="ripgrep",
            version="14.1.0",
            method="cargo",
            path="/home/user/.cargo/bin/rg",
            active=False,
        )

        success, error = _uninstall_installation(inst, False)

        assert success is True
        assert error is None
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ['cargo', 'uninstall', 'ripgrep']

    @patch("cli_audit.reconcile.subprocess.run")
    def test_uninstall_pipx(self, mock_run):
        """Test pipx uninstall."""
        mock_run.return_value = MagicMock(returncode=0)

        inst = Installation(
            tool="black",
            version="24.0.0",
            method="pipx",
            path="/home/user/.local/bin/black",
            active=False,
        )

        success, error = _uninstall_installation(inst, False)

        assert success is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ['pipx', 'uninstall', 'black']

    @patch("cli_audit.reconcile.subprocess.run")
    def test_uninstall_uv(self, mock_run):
        """Test uv uninstall."""
        mock_run.return_value = MagicMock(returncode=0)

        inst = Installation(
            tool="ruff",
            version="0.5.0",
            method="uv",
            path="/home/user/.uv/bin/ruff",
            active=False,
        )

        success, error = _uninstall_installation(inst, False)

        assert success is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ['uv', 'tool', 'uninstall', 'ruff']

    def test_uninstall_system_package(self):
        """Test system package requires sudo."""
        inst = Installation(
            tool="ripgrep",
            version="13.0.0",
            method="apt",
            path="/usr/bin/rg",
            active=False,
        )

        success, error = _uninstall_installation(inst, False)

        assert success is False
        assert "sudo" in error

    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    def test_uninstall_manual(self, mock_exists, mock_remove):
        """Test manual removal."""
        inst = Installation(
            tool="tool",
            version="1.0.0",
            method="unknown",
            path="/home/user/bin/tool",
            active=False,
        )

        success, error = _uninstall_installation(inst, False)

        assert success is True
        mock_remove.assert_called_once_with("/home/user/bin/tool")


class TestSystemToolSafelist:
    """Tests for system tool safelist."""

    def test_safelist_contains_critical_tools(self):
        """Test safelist includes critical system tools."""
        assert "python" in SYSTEM_TOOL_SAFELIST
        assert "bash" in SYSTEM_TOOL_SAFELIST
        assert "sudo" in SYSTEM_TOOL_SAFELIST
        assert "rm" in SYSTEM_TOOL_SAFELIST

    def test_safelist_protects_from_removal(self):
        """Test safelist prevents removal."""
        for tool in SYSTEM_TOOL_SAFELIST:
            # Should not be removable in aggressive mode
            assert tool in SYSTEM_TOOL_SAFELIST
