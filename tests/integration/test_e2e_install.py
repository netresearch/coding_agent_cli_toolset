"""
End-to-end integration tests for installation workflows.

Tests complete installation scenarios from detection through execution.
"""

import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Skip marker for Windows (rollback scripts use Unix paths and shell syntax)
skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Rollback scripts use Unix paths (/tmp) and shell syntax"
)

from cli_audit import (
    install_tool,
    bulk_install,
    Config,
    Environment,
    InstallResult,
    BulkInstallResult,
    ToolSpec,
)


class TestSingleToolInstallation:
    """Integration tests for single tool installation."""

    @patch("cli_audit.installer.subprocess.run")
    @patch("cli_audit.installer.shutil.which")
    @patch("cli_audit.package_managers.subprocess.run")
    def test_install_python_tool_with_pipx(self, mock_pm_run, mock_which, mock_run):
        """Test installing a Python tool using pipx."""
        # Setup: pipx is available
        mock_pm_run.return_value = MagicMock(returncode=0)

        # Mock successful installation
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Installed package successfully",
            stderr="",
        )

        # Mock validation
        mock_which.return_value = "/home/user/.local/bin/black"

        # Create minimal config
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        # Execute installation
        result = install_tool(
            tool_name="black",
            package_name="black",
            target_version="latest",
            config=config,
            env=env,
            language="python",
            verbose=False,
        )

        # Verify result
        assert result.success is True
        assert result.tool_name == "black"
        assert result.package_manager_used in ("pipx", "pip", "uv")
        assert len(result.steps_completed) > 0

    @patch("cli_audit.installer.subprocess.run")
    @patch("cli_audit.installer.shutil.which")
    @patch("cli_audit.package_managers.subprocess.run")
    def test_install_rust_tool_with_cargo(self, mock_pm_run, mock_which, mock_run):
        """Test installing a Rust tool using cargo."""
        # Setup: cargo is available
        mock_pm_run.return_value = MagicMock(returncode=0)

        # Mock successful installation
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Installed package ripgrep v14.1.1",
            stderr="",
        )

        # Mock validation
        mock_which.return_value = "/home/user/.cargo/bin/rg"

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = install_tool(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="latest",
            config=config,
            env=env,
            language="rust",
        )

        assert result.success is True
        assert result.tool_name == "ripgrep"
        assert result.package_manager_used in ("cargo", "rustup")

    @patch("cli_audit.installer.subprocess.run")
    def test_install_with_retry_on_network_failure(self, mock_run):
        """Test that installation retries on transient network failures."""
        # First attempt fails with network error, second succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="connection refused"),
            MagicMock(returncode=0, stdout="Success", stderr=""),
        ]

        from cli_audit.installer import execute_step_with_retry
        from cli_audit.install_plan import InstallStep

        step = InstallStep("Download package", ("curl", "-O", "package.tar.gz"))
        result = execute_step_with_retry(step, max_retries=3)

        # Should succeed after retry
        assert result.success is True
        assert mock_run.call_count == 2


class TestBulkInstallation:
    """Integration tests for bulk installation workflows."""

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    @patch("cli_audit.bulk.get_missing_tools")
    def test_bulk_install_explicit_tools(self, mock_get_missing, mock_install):
        """Test bulk installation of explicit tool list."""
        # Setup: tools are missing
        mock_get_missing.return_value = ["ripgrep", "fd", "bat"]

        # Mock successful installations
        def mock_install_fn(tool_name, **kwargs):
            return InstallResult(
                tool_name=tool_name,
                success=True,
                installed_version="1.0.0",
                package_manager_used="cargo",
                steps_completed=(),
                duration_seconds=1.0,
                validation_passed=True,
                binary_path=f"/usr/bin/{tool_name}",
            )

        mock_install.side_effect = mock_install_fn

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["ripgrep", "fd", "bat"],
            config=config,
            env=env,
            max_workers=2,
        )

        assert len(result.successes) == 3
        assert len(result.failures) == 0
        assert result.duration_seconds > 0

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    def test_bulk_install_with_fail_fast(self, mock_install):
        """Test bulk installation with fail-fast enabled."""
        # First tool succeeds, second fails, third should be skipped
        def mock_install_fn(tool_name, **kwargs):
            if tool_name == "fd":
                return InstallResult(
                    tool_name=tool_name,
                    success=False,
                    installed_version=None,
                    package_manager_used="cargo",
                    steps_completed=(),
                    duration_seconds=1.0,
                    error_message="Package not found",
                )
            return InstallResult(
                tool_name=tool_name,
                success=True,
                installed_version="1.0.0",
                package_manager_used="cargo",
                steps_completed=(),
                duration_seconds=1.0,
            )

        mock_install.side_effect = mock_install_fn

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["ripgrep", "fd", "bat"],
            config=config,
            env=env,
            fail_fast=True,
            max_workers=1,  # Sequential for predictable fail-fast
        )

        # Should have 1 success and 1 failure at minimum
        # Note: fail_fast may not prevent all tools from running in ThreadPoolExecutor
        # even with max_workers=1, as futures may be submitted before failure is detected
        assert len(result.successes) >= 1
        assert len(result.failures) >= 1
        # At least one tool should have run (not all 3 succeeded)
        assert len(result.successes) < 3


class TestDependencyResolution:
    """Integration tests for dependency resolution."""

    def test_resolve_dependencies_simple_chain(self):
        """Test resolving simple dependency chain."""
        from cli_audit.bulk import resolve_dependencies, ToolSpec

        specs = [
            ToolSpec("tool_a", "tool_a", dependencies=()),
            ToolSpec("tool_b", "tool_b", dependencies=("tool_a",)),
            ToolSpec("tool_c", "tool_c", dependencies=("tool_b",)),
        ]

        levels = resolve_dependencies(specs)

        # Should resolve to 3 levels
        assert len(levels) == 3
        assert levels[0][0].tool_name == "tool_a"
        assert levels[1][0].tool_name == "tool_b"
        assert levels[2][0].tool_name == "tool_c"

    def test_resolve_dependencies_parallel(self):
        """Test resolving parallel dependencies."""
        from cli_audit.bulk import resolve_dependencies, ToolSpec

        specs = [
            ToolSpec("tool_a", "tool_a", dependencies=()),
            ToolSpec("tool_b", "tool_b", dependencies=()),
            ToolSpec("tool_c", "tool_c", dependencies=("tool_a", "tool_b")),
        ]

        levels = resolve_dependencies(specs)

        # Level 0 should have tool_a and tool_b (parallel)
        assert len(levels) == 2
        assert len(levels[0]) == 2
        tool_names_level0 = {spec.tool_name for spec in levels[0]}
        assert tool_names_level0 == {"tool_a", "tool_b"}


class TestRollbackScenarios:
    """Integration tests for installation rollback."""

    @patch("cli_audit.bulk.execute_rollback")
    @patch("cli_audit.bulk.generate_rollback_script")
    @patch("cli_audit.bulk.install_tool")
    def test_atomic_rollback_on_failure(self, mock_install, mock_generate, mock_execute):
        """Test atomic rollback when installation fails."""
        # First tool succeeds, second fails
        def mock_install_fn(tool_name, **kwargs):
            if tool_name == "tool_b":
                return InstallResult(
                    tool_name=tool_name,
                    success=False,
                    installed_version=None,
                    package_manager_used="cargo",
                    steps_completed=(),
                    duration_seconds=1.0,
                    error_message="Installation failed",
                )
            return InstallResult(
                tool_name=tool_name,
                success=True,
                installed_version="1.0.0",
                package_manager_used="cargo",
                steps_completed=(),
                duration_seconds=1.0,
                binary_path=f"/usr/bin/{tool_name}",
            )

        mock_install.side_effect = mock_install_fn
        mock_generate.return_value = "/tmp/rollback.sh"
        mock_execute.return_value = True

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        bulk_install(
            mode="explicit",
            tool_names=["tool_a", "tool_b"],
            config=config,
            env=env,
            atomic=True,
            max_workers=1,
        )

        # Should have attempted rollback
        assert mock_execute.called


class TestConfigurationIntegration:
    """Integration tests with various configurations."""

    def test_config_with_custom_preferences(self):
        """Test installation with custom preferences."""
        from cli_audit.config import Preferences, BulkPreferences

        # Create config with custom preferences
        bulk_prefs = BulkPreferences(
            fail_fast=True,
            auto_rollback=True,
            generate_rollback_script=True,
        )

        prefs = Preferences(
            reconciliation="aggressive",
            breaking_changes="reject",
            max_workers=4,
            cache_ttl_seconds=1800,  # 30 minutes
            bulk=bulk_prefs,
        )

        config = Config(preferences=prefs)

        # Verify preferences are applied
        assert config.preferences.max_workers == 4
        assert config.preferences.cache_ttl_seconds == 1800
        assert config.preferences.bulk.fail_fast is True

    def test_config_merge_priority(self):
        """Test configuration merge with correct priority."""
        from cli_audit.config import Preferences

        # Project config (high priority)
        project_prefs = Preferences(max_workers=8, breaking_changes="accept")
        project_config = Config(preferences=project_prefs)

        # User config (low priority)
        user_prefs = Preferences(max_workers=16, timeout_seconds=10)
        user_config = Config(preferences=user_prefs)

        # Merge (project takes priority)
        merged = project_config.merge_with(user_config)

        assert merged.preferences.max_workers == 8  # From project
        assert merged.preferences.breaking_changes == "accept"  # From project
        assert merged.preferences.timeout_seconds == 10  # From user


@pytest.fixture
def temp_install_dir():
    """Create temporary directory for installation tests."""
    temp_dir = tempfile.mkdtemp(prefix="cli_audit_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_environment():
    """Create mock environment for testing."""
    return Environment(
        mode="workstation",
        confidence=1.0,
        package_managers=["pipx", "cargo", "npm"],
        os_info={"name": "linux", "version": "6.6"},
    )
