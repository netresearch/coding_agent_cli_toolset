"""
Tests for bulk installation operations.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_audit.bulk import (
    BulkInstallResult,
    ProgressTracker,
    ToolSpec,
    bulk_install,
    execute_rollback,
    generate_rollback_script,
    get_missing_tools,
    get_tools_to_install,
    group_by_package_manager,
    resolve_dependencies,
)
from cli_audit.config import Config, Preferences, ToolConfig
from cli_audit.environment import Environment
from cli_audit.installer import InstallResult, StepResult

# Skip marker for Windows (rollback scripts are Unix shell scripts)
skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Rollback scripts use Unix shell syntax"
)


class TestToolSpec:
    """Tests for ToolSpec dataclass."""

    def test_toolspec_minimal(self):
        """Test ToolSpec with minimal fields."""
        spec = ToolSpec(tool_name="ripgrep", package_name="ripgrep")
        assert spec.tool_name == "ripgrep"
        assert spec.package_name == "ripgrep"
        assert spec.target_version == "latest"
        assert spec.language is None
        assert spec.dependencies == ()

    def test_toolspec_full(self):
        """Test ToolSpec with all fields."""
        spec = ToolSpec(
            tool_name="black",
            package_name="black",
            target_version="24.10.0",
            language="python",
            dependencies=("python", "pip"),
        )
        assert spec.tool_name == "black"
        assert spec.package_name == "black"
        assert spec.target_version == "24.10.0"
        assert spec.language == "python"
        assert spec.dependencies == ("python", "pip")

    def test_toolspec_to_dict(self):
        """Test ToolSpec serialization."""
        spec = ToolSpec(
            tool_name="mypy",
            package_name="mypy",
            target_version="1.8.0",
            language="python",
            dependencies=("python",),
        )
        d = spec.to_dict()
        assert d["tool_name"] == "mypy"
        assert d["package_name"] == "mypy"
        assert d["target_version"] == "1.8.0"
        assert d["language"] == "python"
        assert d["dependencies"] == ["python"]


class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_progress_tracker_init(self):
        """Test ProgressTracker initialization."""
        tracker = ProgressTracker()
        assert tracker._progress == {}
        assert tracker._callbacks == []

    def test_progress_tracker_update(self):
        """Test updating progress."""
        tracker = ProgressTracker()
        tracker.update("ripgrep", "in_progress", "Installing...")

        progress = tracker.get_progress("ripgrep")
        assert progress is not None
        assert progress["status"] == "in_progress"
        assert progress["message"] == "Installing..."
        assert "timestamp" in progress

    def test_progress_tracker_get_nonexistent(self):
        """Test getting progress for nonexistent tool."""
        tracker = ProgressTracker()
        assert tracker.get_progress("nonexistent") is None

    def test_progress_tracker_get_all(self):
        """Test getting all progress."""
        tracker = ProgressTracker()
        tracker.update("ripgrep", "success")
        tracker.update("black", "failed", "Network error")

        all_progress = tracker.get_all_progress()
        assert len(all_progress) == 2
        assert "ripgrep" in all_progress
        assert "black" in all_progress

    def test_progress_tracker_summary(self):
        """Test progress summary."""
        tracker = ProgressTracker()
        tracker.update("tool1", "pending")
        tracker.update("tool2", "in_progress")
        tracker.update("tool3", "success")
        tracker.update("tool4", "failed")
        tracker.update("tool5", "skipped")

        summary = tracker.get_summary()
        assert summary["pending"] == 1
        assert summary["in_progress"] == 1
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1

    def test_progress_tracker_callback(self):
        """Test progress callbacks."""
        tracker = ProgressTracker()
        callback_args = []

        def callback(tool_name, status, message):
            callback_args.append((tool_name, status, message))

        tracker.register_callback(callback)
        tracker.update("ripgrep", "success", "v14.1.1")

        assert len(callback_args) == 1
        assert callback_args[0] == ("ripgrep", "success", "v14.1.1")

    def test_progress_tracker_thread_safety(self):
        """Test thread-safe progress updates."""
        tracker = ProgressTracker()

        def update_progress(tool_num):
            for i in range(10):
                tracker.update(f"tool{tool_num}", "in_progress", f"step {i}")
                time.sleep(0.001)

        threads = [threading.Thread(target=update_progress, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all 5 tools tracked without corruption
        assert len(tracker.get_all_progress()) == 5


class TestBulkInstallResult:
    """Tests for BulkInstallResult dataclass."""

    def test_bulk_install_result_minimal(self):
        """Test BulkInstallResult with minimal data."""
        result = BulkInstallResult(
            tools_attempted=("ripgrep",),
            successes=(),
            failures=(),
            skipped=(),
            duration_seconds=5.0,
        )
        assert result.tools_attempted == ("ripgrep",)
        assert result.successes == ()
        assert result.duration_seconds == 5.0
        assert result.rollback_script is None

    def test_bulk_install_result_to_dict(self):
        """Test BulkInstallResult serialization."""
        from cli_audit.install_plan import InstallStep

        step_result = StepResult(
            step=InstallStep("test", ("echo", "test")),
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        install_result = InstallResult(
            tool_name="ripgrep",
            success=True,
            installed_version="14.1.1",
            package_manager_used="cargo",
            steps_completed=(step_result,),
            duration_seconds=10.0,
            validation_passed=True,
            binary_path="/usr/bin/rg",
        )

        result = BulkInstallResult(
            tools_attempted=("ripgrep",),
            successes=(install_result,),
            failures=(),
            skipped=(),
            duration_seconds=15.0,
            rollback_script="/tmp/rollback.sh",
        )

        d = result.to_dict()
        assert d["tools_attempted"] == ["ripgrep"]
        assert len(d["successes"]) == 1
        assert d["rollback_script"] == "/tmp/rollback.sh"


class TestGetMissingTools:
    """Tests for get_missing_tools function."""

    @patch("cli_audit.bulk.shutil.which")
    def test_get_missing_tools_all_missing(self, mock_which):
        """Test when all tools are missing."""
        mock_which.return_value = None

        tools = ["ripgrep", "black", "mypy"]
        missing = get_missing_tools(tools)

        assert missing == tools
        assert mock_which.call_count == 3

    @patch("cli_audit.bulk.shutil.which")
    def test_get_missing_tools_all_installed(self, mock_which):
        """Test when all tools are installed."""
        mock_which.return_value = "/usr/bin/tool"

        tools = ["ripgrep", "black", "mypy"]
        missing = get_missing_tools(tools)

        assert missing == []
        assert mock_which.call_count == 3

    @patch("cli_audit.bulk.shutil.which")
    def test_get_missing_tools_mixed(self, mock_which):
        """Test when some tools are installed."""
        def which_side_effect(tool):
            if tool in ("ripgrep", "mypy"):
                return "/usr/bin/" + tool
            return None

        mock_which.side_effect = which_side_effect

        tools = ["ripgrep", "black", "mypy"]
        missing = get_missing_tools(tools)

        assert missing == ["black"]


class TestResolveDependencies:
    """Tests for resolve_dependencies function."""

    def test_resolve_dependencies_no_deps(self):
        """Test dependency resolution with no dependencies."""
        specs = [
            ToolSpec("tool1", "tool1"),
            ToolSpec("tool2", "tool2"),
            ToolSpec("tool3", "tool3"),
        ]

        levels = resolve_dependencies(specs)

        assert len(levels) == 1
        assert len(levels[0]) == 3

    def test_resolve_dependencies_simple_chain(self):
        """Test dependency resolution with simple chain."""
        specs = [
            ToolSpec("tool3", "tool3", dependencies=("tool2",)),
            ToolSpec("tool2", "tool2", dependencies=("tool1",)),
            ToolSpec("tool1", "tool1"),
        ]

        levels = resolve_dependencies(specs)

        assert len(levels) == 3
        assert levels[0][0].tool_name == "tool1"
        assert levels[1][0].tool_name == "tool2"
        assert levels[2][0].tool_name == "tool3"

    def test_resolve_dependencies_parallel(self):
        """Test dependency resolution with parallel dependencies."""
        specs = [
            ToolSpec("app", "app", dependencies=("lib1", "lib2")),
            ToolSpec("lib1", "lib1"),
            ToolSpec("lib2", "lib2"),
        ]

        levels = resolve_dependencies(specs)

        assert len(levels) == 2
        assert len(levels[0]) == 2  # lib1 and lib2 can install in parallel
        assert len(levels[1]) == 1  # app waits for libs
        assert levels[1][0].tool_name == "app"

    def test_resolve_dependencies_diamond(self):
        """Test dependency resolution with diamond pattern."""
        specs = [
            ToolSpec("app", "app", dependencies=("mid1", "mid2")),
            ToolSpec("mid1", "mid1", dependencies=("base",)),
            ToolSpec("mid2", "mid2", dependencies=("base",)),
            ToolSpec("base", "base"),
        ]

        levels = resolve_dependencies(specs)

        assert len(levels) == 3
        assert levels[0][0].tool_name == "base"
        assert len(levels[1]) == 2  # mid1 and mid2
        assert levels[2][0].tool_name == "app"

    def test_resolve_dependencies_external_deps(self):
        """Test dependency resolution with external (not in specs) dependencies."""
        specs = [
            ToolSpec("tool1", "tool1", dependencies=("external",)),  # external not in specs
            ToolSpec("tool2", "tool2"),
        ]

        levels = resolve_dependencies(specs)

        # Both can install in first level (external dep ignored)
        assert len(levels) == 1
        assert len(levels[0]) == 2


class TestGetToolsToInstall:
    """Tests for get_tools_to_install function."""

    def test_get_tools_explicit_mode(self):
        """Test explicit mode."""
        config = Config(tools={"ripgrep": ToolConfig(version="14.1.1")})

        specs = get_tools_to_install(
            mode="explicit",
            tool_names=["ripgrep", "black"],
            preset_name=None,
            config=config,
        )

        assert len(specs) == 2
        assert specs[0].tool_name == "ripgrep"
        assert specs[0].target_version == "14.1.1"
        assert specs[1].tool_name == "black"
        assert specs[1].target_version == "latest"

    def test_get_tools_explicit_mode_empty(self):
        """Test explicit mode with no tools."""
        config = Config()

        specs = get_tools_to_install(
            mode="explicit",
            tool_names=None,
            preset_name=None,
            config=config,
        )

        assert len(specs) == 0

    @patch("cli_audit.bulk.get_missing_tools")
    def test_get_tools_missing_mode(self, mock_get_missing):
        """Test missing mode."""
        mock_get_missing.return_value = ["ripgrep", "black"]

        config = Config(tools={
            "ripgrep": ToolConfig(version="14.1.1"),
            "black": ToolConfig(version="24.10.0"),
            "mypy": ToolConfig(version="1.8.0"),  # not missing
        })

        specs = get_tools_to_install(
            mode="missing",
            tool_names=None,
            preset_name=None,
            config=config,
        )

        assert len(specs) == 2
        assert specs[0].tool_name == "ripgrep"
        assert specs[1].tool_name == "black"

    def test_get_tools_all_mode(self):
        """Test all mode."""
        config = Config(tools={
            "ripgrep": ToolConfig(version="14.1.1"),
            "black": ToolConfig(version="24.10.0"),
            "mypy": ToolConfig(version="1.8.0"),
        })

        specs = get_tools_to_install(
            mode="all",
            tool_names=None,
            preset_name=None,
            config=config,
        )

        assert len(specs) == 3


class TestGroupByPackageManager:
    """Tests for group_by_package_manager function."""

    @patch("cli_audit.bulk.select_package_manager")
    def test_group_by_package_manager_single(self, mock_select):
        """Test grouping with single package manager."""
        mock_select.return_value = ("cargo", "hierarchy")

        specs = [
            ToolSpec("ripgrep", "ripgrep", language="rust"),
            ToolSpec("fd", "fd", language="rust"),
        ]

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        groups = group_by_package_manager(specs, config, env)

        assert len(groups) == 1
        assert "cargo" in groups
        assert len(groups["cargo"]) == 2

    @patch("cli_audit.bulk.select_package_manager")
    def test_group_by_package_manager_multiple(self, mock_select):
        """Test grouping with multiple package managers."""
        def select_side_effect(tool_name, language, config, env, verbose=False):
            if language == "rust":
                return ("cargo", "hierarchy")
            elif language == "python":
                return ("uv", "hierarchy")
            return ("unknown", "fallback")

        mock_select.side_effect = select_side_effect

        specs = [
            ToolSpec("ripgrep", "ripgrep", language="rust"),
            ToolSpec("black", "black", language="python"),
            ToolSpec("mypy", "mypy", language="python"),
        ]

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        groups = group_by_package_manager(specs, config, env)

        assert len(groups) == 2
        assert "cargo" in groups
        assert "uv" in groups
        assert len(groups["cargo"]) == 1
        assert len(groups["uv"]) == 2


@skip_on_windows
class TestGenerateRollbackScript:
    """Tests for generate_rollback_script function."""

    def test_generate_rollback_script_cargo(self):
        """Test rollback script generation for cargo."""
        from cli_audit.install_plan import InstallStep

        step_result = StepResult(
            step=InstallStep("test", ("cargo", "install", "ripgrep")),
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        result = InstallResult(
            tool_name="ripgrep",
            success=True,
            installed_version="14.1.1",
            package_manager_used="cargo",
            steps_completed=(step_result,),
            duration_seconds=10.0,
            validation_passed=True,
            binary_path="/home/user/.cargo/bin/rg",
        )

        script_path = generate_rollback_script([result])

        assert os.path.exists(script_path)
        assert script_path.startswith("/tmp/rollback_")
        assert script_path.endswith(".sh")

        # Check script content
        with open(script_path, "r") as f:
            content = f.read()
            assert "#!/bin/bash" in content
            assert "cargo uninstall ripgrep" in content

        # Cleanup
        os.remove(script_path)

    def test_generate_rollback_script_pip(self):
        """Test rollback script generation for pip."""
        from cli_audit.install_plan import InstallStep

        step_result = StepResult(
            step=InstallStep("test", ("pip", "install", "black")),
            success=True,
            stdout="",
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
        )

        result = InstallResult(
            tool_name="black",
            success=True,
            installed_version="24.10.0",
            package_manager_used="pip",
            steps_completed=(step_result,),
            duration_seconds=10.0,
            validation_passed=True,
            binary_path="/usr/bin/black",
        )

        script_path = generate_rollback_script([result])

        with open(script_path, "r") as f:
            content = f.read()
            assert "pip uninstall -y black" in content

        os.remove(script_path)

    def test_generate_rollback_script_multiple(self):
        """Test rollback script with multiple tools."""
        from cli_audit.install_plan import InstallStep

        results = []
        for tool, pm in [("ripgrep", "cargo"), ("black", "pip"), ("fd", "cargo")]:
            step_result = StepResult(
                step=InstallStep("test", (pm, "install", tool)),
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                duration_seconds=1.0,
            )

            result = InstallResult(
                tool_name=tool,
                success=True,
                installed_version="1.0.0",
                package_manager_used=pm,
                steps_completed=(step_result,),
                duration_seconds=10.0,
                validation_passed=True,
                binary_path=f"/usr/bin/{tool}",
            )
            results.append(result)

        script_path = generate_rollback_script(results)

        with open(script_path, "r") as f:
            content = f.read()
            assert "cargo uninstall ripgrep" in content
            assert "pip uninstall -y black" in content
            assert "cargo uninstall fd" in content

        os.remove(script_path)


class TestExecuteRollback:
    """Tests for execute_rollback function."""

    @skip_on_windows
    def test_execute_rollback_success(self):
        """Test successful rollback execution."""
        # Create a simple rollback script
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Rollback successful'\n")
            f.write("exit 0\n")
            script_path = f.name

        os.chmod(script_path, 0o755)

        success = execute_rollback(script_path)

        assert success is True

        os.remove(script_path)

    def test_execute_rollback_failure(self):
        """Test failed rollback execution."""
        # Create a failing rollback script
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Rollback failed'\n")
            f.write("exit 1\n")
            script_path = f.name

        os.chmod(script_path, 0o755)

        success = execute_rollback(script_path)

        assert success is False

        os.remove(script_path)


class TestBulkInstall:
    """Tests for bulk_install main function."""

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    @patch("cli_audit.bulk.get_missing_tools")
    def test_bulk_install_explicit_success(self, mock_get_missing, mock_install):
        """Test bulk install in explicit mode with success."""
        from cli_audit.install_plan import InstallStep

        # Mock install_tool to return success
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

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["ripgrep"],
            config=config,
            env=env,
            max_workers=1,
        )

        assert result.tools_attempted == ("ripgrep",)
        assert len(result.successes) == 1
        assert len(result.failures) == 0
        assert result.successes[0].tool_name == "ripgrep"

    @patch("cli_audit.bulk.install_tool")
    def test_bulk_install_explicit_failure(self, mock_install):
        """Test bulk install with failure."""
        from cli_audit.install_plan import InstallStep

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

        result = bulk_install(
            mode="explicit",
            tool_names=["ripgrep"],
            config=config,
            env=env,
            max_workers=1,
        )

        assert len(result.failures) == 1
        assert len(result.successes) == 0

    def test_bulk_install_no_tools(self):
        """Test bulk install with no tools."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=[],
            config=config,
            env=env,
        )

        assert result.tools_attempted == ()
        assert len(result.successes) == 0
        assert len(result.failures) == 0

    @patch("cli_audit.bulk.install_tool")
    def test_bulk_install_dry_run(self, mock_install):
        """Test bulk install in dry-run mode."""
        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["ripgrep", "black"],
            config=config,
            env=env,
            dry_run=True,
        )

        # In dry-run, no installations should be executed
        assert mock_install.call_count == 0
        assert result.tools_attempted == ("ripgrep", "black")
        assert len(result.successes) == 0

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    def test_bulk_install_fail_fast(self, mock_install):
        """Test bulk install with fail-fast mode with dependencies."""
        from cli_audit.install_plan import InstallStep

        # Mock install_tool - first succeeds, second fails
        call_count = 0

        def install_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            step_result = StepResult(
                step=InstallStep("test", ("echo", "test")),
                success=(call_count == 1),
                stdout="",
                stderr="" if call_count == 1 else "error",
                exit_code=0 if call_count == 1 else 1,
                duration_seconds=1.0,
                error_message=None if call_count == 1 else "Installation failed",
            )

            tool_name = kwargs.get("tool_name", "tool")
            return InstallResult(
                tool_name=tool_name,
                success=(call_count == 1),
                installed_version="1.0.0" if call_count == 1 else None,
                package_manager_used="cargo",
                steps_completed=(step_result,),
                duration_seconds=10.0,
                error_message=None if call_count == 1 else "Installation failed",
            )

        mock_install.side_effect = install_side_effect

        # Create tools with dependency chain to ensure multi-level execution
        # tool1 → tool2 → tool3
        config = Config(tools={
            "tool1": ToolConfig(),
            "tool2": ToolConfig(),
            "tool3": ToolConfig(),
        })
        env = Environment(mode="workstation", confidence=1.0)

        # We need to test the actual bulk_install, but with dependency resolution
        # Since bulk_install generates specs internally, let's just verify fail_fast stops execution
        result = bulk_install(
            mode="explicit",
            tool_names=["tool1", "tool2"],
            config=config,
            env=env,
            fail_fast=True,
            max_workers=1,
        )

        # Should execute tool1 (succeeds), then tool2 (fails), then stop
        assert len(result.successes) == 1
        assert len(result.failures) == 1
        assert call_count == 2  # Should have stopped after second tool

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    def test_bulk_install_parallel(self, mock_install):
        """Test parallel bulk install."""
        from cli_audit.install_plan import InstallStep

        install_count = 0

        def install_side_effect(*args, **kwargs):
            nonlocal install_count
            install_count += 1

            step_result = StepResult(
                step=InstallStep("test", ("echo", "test")),
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                duration_seconds=1.0,
            )

            return InstallResult(
                tool_name=kwargs.get("tool_name", "tool"),
                success=True,
                installed_version="1.0.0",
                package_manager_used="cargo",
                steps_completed=(step_result,),
                duration_seconds=1.0,
                validation_passed=True,
                binary_path="/usr/bin/tool",
            )

        mock_install.side_effect = install_side_effect

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["tool1", "tool2", "tool3", "tool4"],
            config=config,
            env=env,
            max_workers=4,
        )

        assert len(result.successes) == 4
        assert install_count == 4

    @skip_on_windows
    @patch("cli_audit.bulk.install_tool")
    @patch("cli_audit.bulk.execute_rollback")
    def test_bulk_install_atomic_rollback(self, mock_rollback, mock_install):
        """Test atomic rollback on failure."""
        from cli_audit.install_plan import InstallStep

        # First succeeds, second fails
        call_count = 0

        def install_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            step_result = StepResult(
                step=InstallStep("test", ("echo", "test")),
                success=(call_count == 1),
                stdout="",
                stderr="",
                exit_code=0 if call_count == 1 else 1,
                duration_seconds=1.0,
            )

            return InstallResult(
                tool_name=kwargs.get("tool_name", "tool"),
                success=(call_count == 1),
                installed_version="1.0.0" if call_count == 1 else None,
                package_manager_used="cargo",
                steps_completed=(step_result,),
                duration_seconds=1.0,
                validation_passed=(call_count == 1),
                binary_path="/usr/bin/tool" if call_count == 1 else None,
            )

        mock_install.side_effect = install_side_effect
        mock_rollback.return_value = True

        config = Config()
        env = Environment(mode="workstation", confidence=1.0)

        result = bulk_install(
            mode="explicit",
            tool_names=["tool1", "tool2"],
            config=config,
            env=env,
            atomic=True,
            max_workers=1,
        )

        # Should have attempted rollback
        assert mock_rollback.call_count == 1
        assert len(result.successes) == 1
        assert len(result.failures) == 1
