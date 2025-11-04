"""
Tests for upgrade management operations.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from cli_audit.upgrade import (
    BulkUpgradeResult,
    UpgradeBackup,
    UpgradeCandidate,
    UpgradeResult,
    bulk_upgrade,
    check_breaking_change_policy,
    check_upgrade_available,
    cleanup_backup,
    clear_version_cache,
    compare_versions,
    confirm_breaking_change,
    create_upgrade_backup,
    filter_by_breaking_changes,
    get_available_version,
    get_upgrade_candidates,
    is_major_upgrade,
    restore_from_backup,
    upgrade_tool,
)
from cli_audit.config import Config, Preferences, ToolConfig
from cli_audit.environment import Environment
from cli_audit.installer import InstallResult, StepResult
from cli_audit.install_plan import InstallStep


class TestCompareVersions:
    """Tests for version comparison."""

    def test_compare_versions_semantic_less_than(self):
        """Test semantic version comparison (less than)."""
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_compare_versions_semantic_greater_than(self):
        """Test semantic version comparison (greater than)."""
        assert compare_versions("1.0.1", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("2.0.0", "1.0.0") == 1

    def test_compare_versions_semantic_equal(self):
        """Test semantic version comparison (equal)."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.5.3", "2.5.3") == 0

    def test_compare_versions_major_precedence(self):
        """Test major version takes precedence."""
        assert compare_versions("2.0.0", "1.99.99") == 1

    def test_compare_versions_prerelease(self):
        """Test pre-release version comparison."""
        assert compare_versions("1.0.0-alpha", "1.0.0-beta") == -1
        assert compare_versions("1.0.0-beta", "1.0.0") == -1

    def test_compare_versions_fallback_string(self):
        """Test fallback to string comparison for non-semantic."""
        # Should not crash, use string comparison
        result = compare_versions("nightly", "stable")
        assert result in (-1, 0, 1)


class TestIsMajorUpgrade:
    """Tests for major version bump detection."""

    def test_is_major_upgrade_true(self):
        """Test major version bump detection."""
        assert is_major_upgrade("1.5.3", "2.0.0") is True
        assert is_major_upgrade("1.0.0", "2.0.0") is True
        assert is_major_upgrade("3.14.159", "4.0.0") is True

    def test_is_major_upgrade_false_minor(self):
        """Test minor version bump not breaking."""
        assert is_major_upgrade("1.5.3", "1.6.0") is False

    def test_is_major_upgrade_false_patch(self):
        """Test patch version bump not breaking."""
        assert is_major_upgrade("1.5.3", "1.5.4") is False

    def test_is_major_upgrade_same_major(self):
        """Test same major version not breaking."""
        assert is_major_upgrade("2.0.0", "2.99.99") is False

    def test_is_major_upgrade_malformed(self):
        """Test malformed versions default to false."""
        # Should not crash, default to False
        result = is_major_upgrade("invalid", "also-invalid")
        assert result is False


class TestGetAvailableVersion:
    """Tests for version detection."""

    @patch("cli_audit.upgrade.subprocess.run")
    def test_get_available_version_cargo(self, mock_run):
        """Test cargo version query."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='ripgrep = "14.1.1"    # Line tool for searching\n',
        )

        version = get_available_version("ripgrep", "cargo")
        assert version == "14.1.1"
        mock_run.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_get_available_version_pypi(self, mock_urlopen):
        """Test PyPI JSON API query."""
        import json
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "info": {"version": "24.10.0"}
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        version = get_available_version("black", "pip")
        assert version == "24.10.0"

    @patch("cli_audit.upgrade.subprocess.run")
    def test_get_available_version_npm(self, mock_run):
        """Test npm version query."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="5.2.3\n",
        )

        version = get_available_version("typescript", "npm")
        assert version == "5.2.3"

    @patch("cli_audit.upgrade.subprocess.run")
    def test_get_available_version_cache(self, mock_run):
        """Test version caching."""
        # Clear cache first to ensure clean state
        clear_version_cache()

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='ripgrep = "14.1.1"\n',
        )

        # First call - should query
        version1 = get_available_version("ripgrep", "cargo")
        assert version1 == "14.1.1"
        assert mock_run.call_count == 1

        # Second call - should use cache
        version2 = get_available_version("ripgrep", "cargo")
        assert version2 == "14.1.1"
        assert mock_run.call_count == 1  # Not called again

        # Clear cache
        clear_version_cache()

        # Third call - should query again
        version3 = get_available_version("ripgrep", "cargo")
        assert version3 == "14.1.1"
        assert mock_run.call_count == 2  # Called again

    @patch("cli_audit.upgrade.subprocess.run")
    def test_get_available_version_failure(self, mock_run):
        """Test version query failure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        version = get_available_version("nonexistent", "cargo")
        assert version is None


class TestCheckUpgradeAvailable:
    """Tests for upgrade availability check."""

    @patch("cli_audit.upgrade.get_available_version")
    @patch("cli_audit.upgrade.validate_installation")
    def test_check_upgrade_available_true(self, mock_validate, mock_get_version):
        """Test upgrade available detection."""
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.0")
        mock_get_version.return_value = "14.1.1"

        available, current, latest = check_upgrade_available("ripgrep", "cargo")

        assert available is True
        assert current == "14.1.0"
        assert latest == "14.1.1"

    @patch("cli_audit.upgrade.get_available_version")
    @patch("cli_audit.upgrade.validate_installation")
    def test_check_upgrade_available_false_up_to_date(self, mock_validate, mock_get_version):
        """Test no upgrade when up-to-date."""
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.1")
        mock_get_version.return_value = "14.1.1"

        available, current, latest = check_upgrade_available("ripgrep", "cargo")

        assert available is False
        assert current == "14.1.1"
        assert latest == "14.1.1"

    @patch("cli_audit.upgrade.validate_installation")
    def test_check_upgrade_available_not_installed(self, mock_validate):
        """Test upgrade check for non-installed tool."""
        mock_validate.return_value = (False, None, None)

        available, current, latest = check_upgrade_available("ripgrep", "cargo")

        assert available is False
        assert current is None
        assert latest is None


class TestBreakingChangePolicyCheck:
    """Tests for breaking change policy enforcement."""

    def test_breaking_change_policy_accept(self):
        """Test accept policy allows breaking changes."""
        config = Config(preferences=Preferences(breaking_changes="accept"))

        allowed, reason = check_breaking_change_policy(config, "1.0.0", "2.0.0")

        assert allowed is True
        assert reason == "breaking_accepted"

    def test_breaking_change_policy_warn(self):
        """Test warn policy allows but flags breaking changes."""
        config = Config(preferences=Preferences(breaking_changes="warn"))

        allowed, reason = check_breaking_change_policy(config, "1.0.0", "2.0.0")

        assert allowed is True
        assert reason == "breaking_warning"

    def test_breaking_change_policy_reject(self):
        """Test reject policy blocks breaking changes."""
        config = Config(preferences=Preferences(breaking_changes="reject"))

        allowed, reason = check_breaking_change_policy(config, "1.0.0", "2.0.0")

        assert allowed is False
        assert reason == "breaking_rejected"

    def test_breaking_change_policy_non_breaking(self):
        """Test non-breaking changes always allowed."""
        config = Config(preferences=Preferences(breaking_changes="reject"))

        allowed, reason = check_breaking_change_policy(config, "1.5.0", "1.6.0")

        assert allowed is True
        assert reason == "not_breaking"


class TestConfirmBreakingChange:
    """Tests for breaking change confirmation."""

    @patch("cli_audit.upgrade.sys.stdin.isatty", return_value=False)
    def test_confirm_breaking_change_non_interactive(self, mock_isatty):
        """Test non-interactive mode returns False."""
        result = confirm_breaking_change("warning message")
        assert result is False

    @patch("cli_audit.breaking_changes.input", return_value="y")
    @patch("cli_audit.breaking_changes.sys.stdin.isatty", return_value=True)
    def test_confirm_breaking_change_yes(self, mock_isatty, mock_input):
        """Test user confirmation with 'y'."""
        result = confirm_breaking_change("warning message")
        assert result is True

    @patch("cli_audit.breaking_changes.input", return_value="n")
    @patch("cli_audit.breaking_changes.sys.stdin.isatty", return_value=True)
    def test_confirm_breaking_change_no(self, mock_isatty, mock_input):
        """Test user rejection with 'n'."""
        result = confirm_breaking_change("warning message")
        assert result is False


class TestBackupAndRestore:
    """Tests for backup and rollback functionality."""

    def test_create_upgrade_backup(self, tmp_path):
        """Test backup creation."""
        # Create a test binary
        binary_path = tmp_path / "test_tool"
        binary_path.write_text("fake binary content")

        # Create a test config
        config_dir = tmp_path / ".config" / "test_tool"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config"
        config_file.write_text("test config")

        with patch("cli_audit.upgrade.get_config_paths", return_value=[str(config_file)]):
            backup = create_upgrade_backup(
                "test_tool",
                str(binary_path),
                "1.0.0",
                "cargo",
            )

        assert backup.tool_name == "test_tool"
        assert backup.version == "1.0.0"
        assert backup.binary_path == str(binary_path)
        assert os.path.exists(backup.backup_path)
        assert len(backup.config_paths) == 1
        assert backup.checksum  # SHA256 checksum exists

        # Cleanup
        cleanup_backup(backup)

    def test_restore_from_backup(self, tmp_path):
        """Test backup restoration."""
        # Create original binary
        binary_path = tmp_path / "test_tool"
        binary_path.write_text("original content")

        # Create backup
        with patch("cli_audit.upgrade.get_config_paths", return_value=[]):
            backup = create_upgrade_backup(
                "test_tool",
                str(binary_path),
                "1.0.0",
                "cargo",
            )

        # Modify original
        binary_path.write_text("modified content")

        # Restore
        success = restore_from_backup(backup)

        assert success is True
        assert binary_path.read_text() == "original content"

        # Cleanup
        cleanup_backup(backup)

    def test_restore_from_backup_checksum_mismatch(self, tmp_path):
        """Test restore fails on checksum mismatch."""
        binary_path = tmp_path / "test_tool"
        binary_path.write_text("original content")

        with patch("cli_audit.upgrade.get_config_paths", return_value=[]):
            backup = create_upgrade_backup(
                "test_tool",
                str(binary_path),
                "1.0.0",
                "cargo",
            )

        # Corrupt backup
        backup_binary = os.path.join(backup.backup_path, "test_tool")
        with open(backup_binary, 'w') as f:
            f.write("corrupted content")

        # Restore should fail
        success = restore_from_backup(backup)
        assert success is False

        # Cleanup
        cleanup_backup(backup)


class TestUpgradeTool:
    """Tests for single tool upgrade."""

    @patch("cli_audit.upgrade.install_tool")
    @patch("cli_audit.upgrade.create_upgrade_backup")
    @patch("cli_audit.upgrade.get_available_version")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_success(
        self,
        mock_validate,
        mock_select_pm,
        mock_get_version,
        mock_backup,
        mock_install,
    ):
        """Test successful upgrade."""
        # Setup mocks
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.0")
        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_get_version.return_value = "14.1.1"
        mock_backup.return_value = UpgradeBackup(
            tool_name="ripgrep",
            version="14.1.0",
            binary_path="/usr/bin/rg",
            backup_path="/tmp/backup",
            config_paths=(),
            timestamp=time.time(),
            package_manager="cargo",
            checksum="abc123",
        )

        step_result = StepResult(
            step=InstallStep("test", ("echo", "test")),
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        mock_install.return_value = InstallResult(
            tool_name="ripgrep",
            success=True,
            installed_version="14.1.1",
            package_manager_used="cargo",
            steps_completed=(step_result,),
            duration_seconds=10.0,
            validation_passed=True,
            binary_path="/usr/bin/rg",
        )

        # Execute upgrade
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("ripgrep", "latest", config, env)

        # Verify
        assert result.success is True
        assert result.previous_version == "14.1.0"
        assert result.new_version == "14.1.1"
        assert result.backup is not None

    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_not_installed(self, mock_validate):
        """Test upgrade of non-installed tool."""
        mock_validate.return_value = (False, None, None)

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("nonexistent", "latest", config, env)

        assert result.success is False
        assert "not currently installed" in result.error_message

    @patch("cli_audit.upgrade.get_available_version")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_already_up_to_date(
        self,
        mock_validate,
        mock_select_pm,
        mock_get_version,
    ):
        """Test upgrade when already at target version."""
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.1")
        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_get_version.return_value = "14.1.1"

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("ripgrep", "latest", config, env)

        assert result.success is True
        assert result.previous_version == "14.1.1"
        assert result.new_version == "14.1.1"
        assert "Already at target version" in result.error_message

    @patch("cli_audit.upgrade.get_available_version")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_downgrade_rejected(
        self,
        mock_validate,
        mock_select_pm,
        mock_get_version,
    ):
        """Test downgrade rejection."""
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.1")
        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_get_version.return_value = "14.0.0"

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("ripgrep", "14.0.0", config, env)

        assert result.success is False
        assert "Downgrade not supported" in result.error_message

    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_breaking_change_rejected(
        self,
        mock_validate,
        mock_select_pm,
    ):
        """Test breaking change rejected by policy."""
        mock_validate.return_value = (True, "/usr/bin/tool", "1.5.0")
        mock_select_pm.return_value = ("cargo", "hierarchy")

        config = Config(preferences=Preferences(breaking_changes="reject"))
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("tool", "2.0.0", config, env)

        assert result.success is False
        assert result.breaking_change is True
        assert "blocked by policy" in result.error_message

    @patch("cli_audit.upgrade.install_tool")
    @patch("cli_audit.upgrade.restore_from_backup")
    @patch("cli_audit.upgrade.create_upgrade_backup")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_upgrade_tool_with_rollback(
        self,
        mock_validate,
        mock_select_pm,
        mock_backup,
        mock_restore,
        mock_install,
    ):
        """Test automatic rollback on failure."""
        mock_validate.return_value = (True, "/usr/bin/rg", "14.1.0")
        mock_select_pm.return_value = ("cargo", "hierarchy")

        backup = UpgradeBackup(
            tool_name="ripgrep",
            version="14.1.0",
            binary_path="/usr/bin/rg",
            backup_path="/tmp/backup",
            config_paths=(),
            timestamp=time.time(),
            package_manager="cargo",
            checksum="abc123",
        )
        mock_backup.return_value = backup
        mock_restore.return_value = True

        # Simulate installation failure
        step_result = StepResult(
            step=InstallStep("test", ("echo", "test")),
            success=False,
            stdout="",
            stderr="error",
            exit_code=1,
            duration_seconds=1.0,
            error_message="Installation failed",
        )

        mock_install.return_value = InstallResult(
            tool_name="ripgrep",
            success=False,
            installed_version=None,
            package_manager_used="cargo",
            steps_completed=(step_result,),
            duration_seconds=10.0,
            error_message="Installation failed",
        )

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = upgrade_tool("ripgrep", "14.1.1", config, env)

        assert result.success is False
        assert result.rollback_executed is True
        assert result.rollback_success is True
        mock_restore.assert_called_once_with(backup, False)


class TestGetUpgradeCandidates:
    """Tests for upgrade candidate detection."""

    @patch("cli_audit.upgrade.check_upgrade_available")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_get_upgrade_candidates_explicit(
        self,
        mock_validate,
        mock_select_pm,
        mock_check_upgrade,
    ):
        """Test explicit mode."""
        mock_validate.return_value = (True, "/usr/bin/tool", "1.0.0")
        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_check_upgrade.return_value = (True, "1.0.0", "1.1.0")

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        candidates = get_upgrade_candidates("explicit", ["tool1"], config, env)

        assert len(candidates) == 1
        assert candidates[0].tool_name == "tool1"
        assert candidates[0].current_version == "1.0.0"
        assert candidates[0].available_version == "1.1.0"

    @patch("cli_audit.upgrade.check_upgrade_available")
    @patch("cli_audit.upgrade.select_package_manager")
    @patch("cli_audit.upgrade.validate_installation")
    def test_get_upgrade_candidates_all(
        self,
        mock_validate,
        mock_select_pm,
        mock_check_upgrade,
    ):
        """Test all mode."""
        mock_validate.return_value = (True, "/usr/bin/tool", "1.0.0")
        mock_select_pm.return_value = ("cargo", "hierarchy")
        mock_check_upgrade.return_value = (True, "1.0.0", "2.0.0")

        config = Config(tools={
            "tool1": ToolConfig(),
            "tool2": ToolConfig(),
        })
        env = Environment(mode="workstation", confidence=1.0)

        candidates = get_upgrade_candidates("all", None, config, env)

        assert len(candidates) == 2


class TestFilterByBreakingChanges:
    """Tests for breaking change filtering."""

    def test_filter_by_breaking_changes_accept(self):
        """Test accept policy allows all."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
            UpgradeCandidate("tool2", "1.0.0", "2.0.0", True, "cargo"),
        ]

        allowed, blocked = filter_by_breaking_changes(candidates, "accept")

        assert len(allowed) == 2
        assert len(blocked) == 0

    def test_filter_by_breaking_changes_reject(self):
        """Test reject policy blocks breaking."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
            UpgradeCandidate("tool2", "1.0.0", "2.0.0", True, "cargo"),
        ]

        allowed, blocked = filter_by_breaking_changes(candidates, "reject")

        assert len(allowed) == 1
        assert len(blocked) == 1
        assert allowed[0].tool_name == "tool1"
        assert blocked[0].tool_name == "tool2"

    def test_filter_by_breaking_changes_warn(self):
        """Test warn policy allows all."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
            UpgradeCandidate("tool2", "1.0.0", "2.0.0", True, "cargo"),
        ]

        allowed, blocked = filter_by_breaking_changes(candidates, "warn")

        assert len(allowed) == 2
        assert len(blocked) == 0


class TestBulkUpgrade:
    """Tests for bulk upgrade operations."""

    @patch("cli_audit.upgrade.upgrade_tool")
    @patch("cli_audit.upgrade.get_upgrade_candidates")
    def test_bulk_upgrade_no_candidates(
        self,
        mock_get_candidates,
        mock_upgrade,
    ):
        """Test bulk upgrade with no candidates."""
        mock_get_candidates.return_value = []

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_upgrade("all", config=config, env=env)

        assert len(result.tools_attempted) == 0
        assert len(result.upgrades) == 0
        assert len(result.failures) == 0

    @patch("cli_audit.upgrade.upgrade_tool")
    @patch("cli_audit.upgrade.get_upgrade_candidates")
    def test_bulk_upgrade_success(
        self,
        mock_get_candidates,
        mock_upgrade,
    ):
        """Test successful bulk upgrade."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
            UpgradeCandidate("tool2", "2.0.0", "2.1.0", False, "cargo"),
        ]
        mock_get_candidates.return_value = candidates

        mock_upgrade.return_value = UpgradeResult(
            tool_name="tool1",
            success=True,
            previous_version="1.0.0",
            new_version="1.1.0",
            backup=None,
        )

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_upgrade("all", config=config, env=env, max_workers=1)

        assert len(result.tools_attempted) == 2
        assert len(result.upgrades) == 2
        assert len(result.failures) == 0

    @patch("cli_audit.upgrade.get_upgrade_candidates")
    def test_bulk_upgrade_dry_run(
        self,
        mock_get_candidates,
    ):
        """Test dry-run mode."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
        ]
        mock_get_candidates.return_value = candidates

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_upgrade("all", config=config, env=env, dry_run=True)

        assert len(result.tools_attempted) == 1
        assert len(result.upgrades) == 0  # No actual upgrades in dry-run

    @patch("cli_audit.upgrade.upgrade_tool")
    @patch("cli_audit.upgrade.get_upgrade_candidates")
    def test_bulk_upgrade_with_failures(
        self,
        mock_get_candidates,
        mock_upgrade,
    ):
        """Test bulk upgrade with mixed success/failure."""
        candidates = [
            UpgradeCandidate("tool1", "1.0.0", "1.1.0", False, "cargo"),
            UpgradeCandidate("tool2", "2.0.0", "2.1.0", False, "cargo"),
        ]
        mock_get_candidates.return_value = candidates

        # First succeeds, second fails
        mock_upgrade.side_effect = [
            UpgradeResult(
                tool_name="tool1",
                success=True,
                previous_version="1.0.0",
                new_version="1.1.0",
                backup=None,
            ),
            UpgradeResult(
                tool_name="tool2",
                success=False,
                previous_version="2.0.0",
                new_version=None,
                backup=None,
                error_message="Upgrade failed",
            ),
        ]

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_upgrade("all", config=config, env=env, max_workers=1)

        assert len(result.upgrades) == 1
        assert len(result.failures) == 1
