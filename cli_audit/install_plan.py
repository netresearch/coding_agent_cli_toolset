"""
Installation plan generation and dry-run mode.

Generates detailed installation plans without executing them.
Supports serialization to JSON, shell scripts, and human-readable tables.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from .package_managers import PackageManager, get_package_manager


@dataclass(frozen=True)
class InstallStep:
    """
    Single step in an installation plan.

    Attributes:
        description: Human-readable description of the step
        command: Command tuple to execute
        requires_sudo: Whether this step requires sudo/root privileges
        estimated_time_seconds: Estimated time for this step
    """
    description: str
    command: tuple[str, ...]
    requires_sudo: bool = False
    estimated_time_seconds: int = 30

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "description": self.description,
            "command": list(self.command),
            "requires_sudo": self.requires_sudo,
            "estimated_time_seconds": self.estimated_time_seconds,
        }


@dataclass(frozen=True)
class InstallPlan:
    """
    Complete installation plan for a tool.

    Attributes:
        tool_name: Name of the tool to install
        target_version: Target version to install
        package_manager: Package manager to use
        steps: Sequence of installation steps
        dependencies: Tools that must be installed first
        disk_space_mb: Estimated disk space required (MB)
        estimated_total_time: Total estimated time (seconds)
        warnings: List of warning messages
    """
    tool_name: str
    target_version: str
    package_manager: str
    steps: tuple[InstallStep, ...] = ()
    dependencies: tuple[str, ...] = ()
    disk_space_mb: int = 0
    estimated_total_time: int = 0
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        """Calculate total estimated time from steps."""
        if self.estimated_total_time == 0 and self.steps:
            # Calculate from steps
            total = sum(step.estimated_time_seconds for step in self.steps)
            # Use object.__setattr__ for frozen dataclass
            object.__setattr__(self, "estimated_total_time", total)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "target_version": self.target_version,
            "package_manager": self.package_manager,
            "steps": [step.to_dict() for step in self.steps],
            "dependencies": list(self.dependencies),
            "disk_space_mb": self.disk_space_mb,
            "estimated_total_time": self.estimated_total_time,
            "warnings": list(self.warnings),
        }

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize to JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    def to_script(self, shell: str = "bash") -> str:
        """
        Generate executable shell script.

        Args:
            shell: Shell type (bash, sh, zsh)

        Returns:
            Shell script as string
        """
        lines = []

        # Shebang
        if shell == "bash":
            lines.append("#!/bin/bash")
        elif shell == "zsh":
            lines.append("#!/bin/zsh")
        else:
            lines.append("#!/bin/sh")

        # Strict mode
        lines.append("set -euo pipefail")
        lines.append("")

        # Header comment
        lines.append(f"# Installation script for {self.tool_name}")
        lines.append(f"# Target version: {self.target_version}")
        lines.append(f"# Package manager: {self.package_manager}")
        lines.append(f"# Estimated time: {self.estimated_total_time}s")
        if self.disk_space_mb:
            lines.append(f"# Disk space required: {self.disk_space_mb} MB")
        lines.append("")

        # Warnings
        if self.warnings:
            lines.append("# Warnings:")
            for warning in self.warnings:
                lines.append(f"#   - {warning}")
            lines.append("")

        # Dependencies check
        if self.dependencies:
            lines.append("# Check dependencies")
            for dep in self.dependencies:
                lines.append(f'command -v {dep} >/dev/null 2>&1 || {{ echo "Error: {dep} not found"; exit 1; }}')
            lines.append("")

        # Installation steps
        for i, step in enumerate(self.steps, 1):
            lines.append(f"# Step {i}: {step.description}")

            # Build command
            if step.requires_sudo:
                command_str = "sudo " + " ".join(step.command)
            else:
                command_str = " ".join(step.command)

            lines.append(f"echo 'Executing: {step.description}...'")
            lines.append(command_str)
            lines.append("")

        # Success message
        lines.append(f'echo "Successfully installed {self.tool_name} {self.target_version}"')

        return "\n".join(lines)

    def to_table(self, width: int = 80) -> str:
        """
        Generate human-readable table representation.

        Args:
            width: Maximum table width

        Returns:
            Formatted table string
        """
        lines = []

        # Header
        lines.append("=" * width)
        lines.append(f"Installation Plan for {self.tool_name}")
        lines.append("=" * width)
        lines.append("")

        # Metadata
        lines.append(f"Target Version:     {self.target_version}")
        lines.append(f"Package Manager:    {self.package_manager}")
        if self.dependencies:
            lines.append(f"Dependencies:       {', '.join(self.dependencies)}")
        if self.disk_space_mb:
            lines.append(f"Disk Space:         {self.disk_space_mb} MB")
        lines.append(f"Estimated Time:     {self.estimated_total_time}s (~{self.estimated_total_time // 60}m {self.estimated_total_time % 60}s)")
        lines.append("")

        # Warnings
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠️  {warning}")
            lines.append("")

        # Steps
        lines.append("Installation Steps:")
        lines.append("-" * width)
        for i, step in enumerate(self.steps, 1):
            sudo_marker = " [SUDO]" if step.requires_sudo else ""
            lines.append(f"{i}. {step.description}{sudo_marker}")
            lines.append(f"   Command: {' '.join(step.command)}")
            lines.append(f"   Estimated time: {step.estimated_time_seconds}s")
            if i < len(self.steps):
                lines.append("")

        lines.append("-" * width)
        lines.append("")
        lines.append("This is a dry-run. No changes will be made.")
        lines.append("To execute, generate a script with: --script")

        return "\n".join(lines)


def generate_install_plan(
    tool_name: str,
    package_name: str,
    target_version: str,
    package_manager_name: str,
    dependencies: Sequence[str] = (),
    disk_space_mb: int = 0,
) -> InstallPlan:
    """
    Generate installation plan for a tool.

    Args:
        tool_name: Display name of the tool
        package_name: Package name for installation
        target_version: Target version to install
        package_manager_name: Package manager to use
        dependencies: List of required dependencies
        disk_space_mb: Estimated disk space required

    Returns:
        InstallPlan object

    Raises:
        ValueError: If package manager not found
    """
    pm = get_package_manager(package_manager_name)
    if pm is None:
        raise ValueError(f"Package manager not found: {package_manager_name}")

    steps = []
    warnings = []

    # Step 1: Check package manager availability
    steps.append(
        InstallStep(
            description=f"Check for {pm.display_name}",
            command=pm.check_command,
            requires_sudo=False,
            estimated_time_seconds=2,
        )
    )

    # Step 2: Install the tool
    install_cmd = pm.get_install_command(package_name, target_version)
    requires_sudo = pm.category == "system"  # System package managers need sudo

    steps.append(
        InstallStep(
            description=f"Install {tool_name} via {pm.display_name}",
            command=install_cmd,
            requires_sudo=requires_sudo,
            estimated_time_seconds=60,  # Conservative estimate
        )
    )

    # Step 3: Verify installation
    # Use tool_name as command to verify (may need to be customized per tool)
    verify_cmd = (tool_name.lower(), "--version")
    steps.append(
        InstallStep(
            description=f"Verify {tool_name} installation",
            command=verify_cmd,
            requires_sudo=False,
            estimated_time_seconds=2,
        )
    )

    # Add warnings
    if requires_sudo:
        warnings.append("This installation requires sudo/root privileges")

    if not dependencies:
        # Common dependency for Rust tools
        if pm.name == "cargo":
            dependencies = ("rust", "cargo")

    return InstallPlan(
        tool_name=tool_name,
        target_version=target_version,
        package_manager=package_manager_name,
        steps=tuple(steps),
        dependencies=tuple(dependencies),
        disk_space_mb=disk_space_mb,
        warnings=tuple(warnings),
    )


def dry_run_install(
    tool_name: str,
    package_name: str,
    target_version: str = "latest",
    package_manager_name: str | None = None,
    output_format: str = "table",
) -> str:
    """
    Generate dry-run installation plan and format for output.

    Args:
        tool_name: Display name of the tool
        package_name: Package name for installation
        target_version: Target version to install
        package_manager_name: Package manager to use (auto-detect if None)
        output_format: Output format ("table", "json", "script")

    Returns:
        Formatted installation plan as string

    Raises:
        ValueError: If package manager not found or invalid format
    """
    if package_manager_name is None:
        # Would need config and environment to auto-detect
        raise ValueError("Package manager must be specified for dry-run")

    plan = generate_install_plan(
        tool_name=tool_name,
        package_name=package_name,
        target_version=target_version,
        package_manager_name=package_manager_name,
    )

    if output_format == "json":
        return plan.to_json()
    elif output_format == "script":
        return plan.to_script()
    elif output_format == "table":
        return plan.to_table()
    else:
        raise ValueError(f"Invalid output format: {output_format}. Must be 'table', 'json', or 'script'")
