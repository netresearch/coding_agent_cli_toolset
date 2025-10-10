"""
Tests for install plan generation (cli_audit/install_plan.py).

Target coverage: 85%+
"""

import json
import pytest

from cli_audit.install_plan import (
    InstallStep,
    InstallPlan,
    generate_install_plan,
    dry_run_install,
)


class TestInstallStep:
    """Tests for InstallStep dataclass."""

    def test_install_step_creation(self):
        """Test InstallStep object creation."""
        step = InstallStep(
            description="Install ripgrep",
            command=("cargo", "install", "ripgrep"),
            requires_sudo=False,
            estimated_time_seconds=60,
        )
        assert step.description == "Install ripgrep"
        assert step.command == ("cargo", "install", "ripgrep")
        assert step.requires_sudo is False
        assert step.estimated_time_seconds == 60

    def test_install_step_defaults(self):
        """Test InstallStep with default values."""
        step = InstallStep(
            description="Test step",
            command=("test", "command"),
        )
        assert step.requires_sudo is False
        assert step.estimated_time_seconds == 30  # Default

    def test_install_step_to_dict(self):
        """Test InstallStep to_dict method."""
        step = InstallStep(
            description="Install tool",
            command=("npm", "install", "-g", "tool"),
            requires_sudo=False,
            estimated_time_seconds=45,
        )
        data = step.to_dict()
        assert data["description"] == "Install tool"
        assert data["command"] == ["npm", "install", "-g", "tool"]
        assert data["requires_sudo"] is False
        assert data["estimated_time_seconds"] == 45

    def test_install_step_immutable(self):
        """Test that InstallStep is immutable."""
        step = InstallStep(description="Test", command=("test",))
        with pytest.raises(AttributeError):
            step.description = "Changed"  # Should fail (frozen)


class TestInstallPlan:
    """Tests for InstallPlan dataclass."""

    def test_install_plan_creation(self):
        """Test InstallPlan object creation."""
        steps = (
            InstallStep("Check cargo", ("cargo", "--version"), estimated_time_seconds=2),
            InstallStep("Install ripgrep", ("cargo", "install", "ripgrep"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="ripgrep",
            target_version="14.1.1",
            package_manager="cargo",
            steps=steps,
            dependencies=("rust", "cargo"),
            disk_space_mb=50,
        )
        assert plan.tool_name == "ripgrep"
        assert plan.target_version == "14.1.1"
        assert plan.package_manager == "cargo"
        assert len(plan.steps) == 2
        assert "rust" in plan.dependencies
        assert plan.disk_space_mb == 50

    def test_install_plan_calculates_total_time(self):
        """Test that total estimated time is calculated from steps."""
        steps = (
            InstallStep("Step 1", ("cmd1",), estimated_time_seconds=10),
            InstallStep("Step 2", ("cmd2",), estimated_time_seconds=20),
            InstallStep("Step 3", ("cmd3",), estimated_time_seconds=30),
        )
        plan = InstallPlan(
            tool_name="test",
            target_version="1.0.0",
            package_manager="test",
            steps=steps,
        )
        assert plan.estimated_total_time == 60  # 10 + 20 + 30

    def test_install_plan_empty_steps(self):
        """Test InstallPlan with no steps."""
        plan = InstallPlan(
            tool_name="test",
            target_version="1.0.0",
            package_manager="test",
            steps=(),
        )
        assert plan.estimated_total_time == 0

    def test_install_plan_explicit_total_time(self):
        """Test InstallPlan with explicit total time."""
        steps = (
            InstallStep("Step 1", ("cmd1",), estimated_time_seconds=10),
        )
        plan = InstallPlan(
            tool_name="test",
            target_version="1.0.0",
            package_manager="test",
            steps=steps,
            estimated_total_time=100,  # Explicit
        )
        assert plan.estimated_total_time == 100  # Uses explicit value

    def test_install_plan_to_dict(self):
        """Test InstallPlan to_dict method."""
        steps = (
            InstallStep("Install", ("cargo", "install", "tool"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
            dependencies=("rust",),
            warnings=("Requires sudo",),
        )
        data = plan.to_dict()
        assert data["tool_name"] == "tool"
        assert data["target_version"] == "1.0.0"
        assert data["package_manager"] == "cargo"
        assert len(data["steps"]) == 1
        assert data["dependencies"] == ["rust"]
        assert data["warnings"] == ["Requires sudo"]

    def test_install_plan_to_json(self):
        """Test InstallPlan to_json method."""
        steps = (
            InstallStep("Install", ("cargo", "install", "tool"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
        )
        json_str = plan.to_json()
        data = json.loads(json_str)
        assert data["tool_name"] == "tool"
        assert data["target_version"] == "1.0.0"

    def test_install_plan_to_script_bash(self):
        """Test InstallPlan to_script method for bash."""
        steps = (
            InstallStep("Check cargo", ("cargo", "--version"), estimated_time_seconds=2),
            InstallStep("Install tool", ("cargo", "install", "tool"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
            dependencies=("rust",),
        )
        script = plan.to_script(shell="bash")
        assert "#!/bin/bash" in script
        assert "set -euo pipefail" in script
        assert "cargo install tool" in script
        assert "command -v rust" in script  # Dependency check

    def test_install_plan_to_script_with_sudo(self):
        """Test InstallPlan to_script with sudo steps."""
        steps = (
            InstallStep("Install via apt", ("apt", "install", "tool"), requires_sudo=True, estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="apt",
            steps=steps,
        )
        script = plan.to_script()
        assert "sudo apt install tool" in script

    def test_install_plan_to_script_with_warnings(self):
        """Test InstallPlan to_script includes warnings."""
        steps = (
            InstallStep("Install", ("cargo", "install", "tool"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
            warnings=("This is a warning", "Another warning"),
        )
        script = plan.to_script()
        assert "This is a warning" in script
        assert "Another warning" in script

    def test_install_plan_to_table(self):
        """Test InstallPlan to_table method."""
        steps = (
            InstallStep("Check cargo", ("cargo", "--version"), estimated_time_seconds=2),
            InstallStep("Install tool", ("cargo", "install", "tool"), estimated_time_seconds=60),
            InstallStep("Verify", ("tool", "--version"), estimated_time_seconds=2),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
            dependencies=("rust", "cargo"),
            disk_space_mb=50,
        )
        table = plan.to_table(width=80)
        assert "Installation Plan for tool" in table
        assert "Target Version:     1.0.0" in table
        assert "Package Manager:    cargo" in table
        assert "Dependencies:       rust, cargo" in table
        assert "Disk Space:         50 MB" in table
        assert "Check cargo" in table
        assert "Install tool" in table
        assert "Verify" in table
        assert "dry-run" in table.lower()

    def test_install_plan_to_table_with_warnings(self):
        """Test InstallPlan to_table includes warnings."""
        steps = (
            InstallStep("Install", ("cargo", "install", "tool"), estimated_time_seconds=60),
        )
        plan = InstallPlan(
            tool_name="tool",
            target_version="1.0.0",
            package_manager="cargo",
            steps=steps,
            warnings=("Requires sudo", "May take a long time"),
        )
        table = plan.to_table()
        assert "Warnings:" in table
        assert "Requires sudo" in table
        assert "May take a long time" in table


class TestGenerateInstallPlan:
    """Tests for generate_install_plan function."""

    def test_generate_plan_cargo(self):
        """Test generating plan for cargo installation."""
        plan = generate_install_plan(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            package_manager_name="cargo",
        )
        assert plan.tool_name == "ripgrep"
        assert plan.target_version == "14.1.1"
        assert plan.package_manager == "cargo"
        assert len(plan.steps) >= 2  # At least check and install steps
        assert "rust" in plan.dependencies or "cargo" in plan.dependencies

    def test_generate_plan_npm(self):
        """Test generating plan for npm installation."""
        plan = generate_install_plan(
            tool_name="prettier",
            package_name="prettier",
            target_version="3.0.0",
            package_manager_name="npm",
        )
        assert plan.tool_name == "prettier"
        assert plan.target_version == "3.0.0"
        assert plan.package_manager == "npm"

    def test_generate_plan_system_pm_requires_sudo(self):
        """Test that system package managers require sudo."""
        plan = generate_install_plan(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="latest",
            package_manager_name="apt",
        )
        # Check that install step requires sudo
        install_steps = [step for step in plan.steps if "Install" in step.description]
        assert any(step.requires_sudo for step in install_steps)
        assert any("sudo" in warning.lower() for warning in plan.warnings)

    def test_generate_plan_with_dependencies(self):
        """Test generating plan with explicit dependencies."""
        plan = generate_install_plan(
            tool_name="tool",
            package_name="tool",
            target_version="1.0.0",
            package_manager_name="cargo",
            dependencies=("dependency1", "dependency2"),
        )
        assert "dependency1" in plan.dependencies
        assert "dependency2" in plan.dependencies

    def test_generate_plan_with_disk_space(self):
        """Test generating plan with disk space estimate."""
        plan = generate_install_plan(
            tool_name="tool",
            package_name="tool",
            target_version="1.0.0",
            package_manager_name="cargo",
            disk_space_mb=100,
        )
        assert plan.disk_space_mb == 100

    def test_generate_plan_invalid_package_manager(self):
        """Test that invalid package manager raises ValueError."""
        with pytest.raises(ValueError, match="Package manager not found"):
            generate_install_plan(
                tool_name="tool",
                package_name="tool",
                target_version="1.0.0",
                package_manager_name="nonexistent",
            )

    def test_generate_plan_has_verification_step(self):
        """Test that generated plan includes verification step."""
        plan = generate_install_plan(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            package_manager_name="cargo",
        )
        verify_steps = [step for step in plan.steps if "Verify" in step.description or "verify" in step.description]
        assert len(verify_steps) > 0


class TestDryRunInstall:
    """Tests for dry_run_install function."""

    def test_dry_run_table_format(self):
        """Test dry_run with table format."""
        output = dry_run_install(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            package_manager_name="cargo",
            output_format="table",
        )
        assert "Installation Plan for ripgrep" in output
        assert "14.1.1" in output
        assert "cargo" in output
        assert "dry-run" in output.lower()

    def test_dry_run_json_format(self):
        """Test dry_run with JSON format."""
        output = dry_run_install(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            package_manager_name="cargo",
            output_format="json",
        )
        data = json.loads(output)
        assert data["tool_name"] == "ripgrep"
        assert data["target_version"] == "14.1.1"
        assert data["package_manager"] == "cargo"

    def test_dry_run_script_format(self):
        """Test dry_run with script format."""
        output = dry_run_install(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="14.1.1",
            package_manager_name="cargo",
            output_format="script",
        )
        assert "#!/bin/bash" in output
        assert "cargo install ripgrep" in output
        assert "set -euo pipefail" in output

    def test_dry_run_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid output format"):
            dry_run_install(
                tool_name="tool",
                package_name="tool",
                target_version="1.0.0",
                package_manager_name="cargo",
                output_format="invalid",
            )

    def test_dry_run_no_package_manager(self):
        """Test that missing package manager raises ValueError."""
        with pytest.raises(ValueError, match="Package manager must be specified"):
            dry_run_install(
                tool_name="tool",
                package_name="tool",
                target_version="1.0.0",
                package_manager_name=None,
            )

    def test_dry_run_latest_version(self):
        """Test dry_run with latest version."""
        output = dry_run_install(
            tool_name="tool",
            package_name="tool",
            target_version="latest",
            package_manager_name="cargo",
            output_format="json",
        )
        data = json.loads(output)
        assert data["target_version"] == "latest"
