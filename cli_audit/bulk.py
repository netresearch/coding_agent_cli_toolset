"""
Bulk installation operations with parallel execution.

Executes multiple tool installations in parallel with progress tracking,
dependency resolution, and atomic rollback capability.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from .common import vlog
from .config import Config
from .environment import Environment
from .installer import InstallResult, install_tool
from .package_managers import select_package_manager


@dataclass(frozen=True)
class ToolSpec:
    """
    Specification for a tool to be installed.

    Attributes:
        tool_name: Display name of the tool
        package_name: Package name for installation
        target_version: Target version to install
        language: Tool language/ecosystem (e.g., "python", "rust")
        dependencies: Tool names that must be installed first
    """
    tool_name: str
    package_name: str
    target_version: str = "latest"
    language: str | None = None
    dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "package_name": self.package_name,
            "target_version": self.target_version,
            "language": self.language,
            "dependencies": list(self.dependencies),
        }


@dataclass
class ProgressTracker:
    """
    Thread-safe progress tracking for bulk operations.

    Attributes:
        _lock: Threading lock for thread-safe updates
        _progress: Progress state for each tool
        _callbacks: Callbacks to invoke on progress updates
    """
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _progress: dict[str, dict] = field(default_factory=dict)
    _callbacks: list[Callable[[str, str, str], None]] = field(default_factory=list)

    def register_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """Register a callback for progress updates."""
        with self._lock:
            self._callbacks.append(callback)

    def update(self, tool_name: str, status: str, message: str = "") -> None:
        """
        Update progress for a tool.

        Args:
            tool_name: Name of the tool
            status: Status ("pending", "in_progress", "success", "failed", "skipped")
            message: Optional status message
        """
        with self._lock:
            self._progress[tool_name] = {
                "status": status,
                "message": message,
                "timestamp": time.time(),
            }
            # Invoke callbacks
            for callback in self._callbacks:
                callback(tool_name, status, message)

    def get_progress(self, tool_name: str) -> dict | None:
        """Get progress for a specific tool."""
        with self._lock:
            return self._progress.get(tool_name)

    def get_all_progress(self) -> dict[str, dict]:
        """Get progress for all tools."""
        with self._lock:
            return self._progress.copy()

    def get_summary(self) -> dict[str, int]:
        """Get summary counts by status."""
        with self._lock:
            summary = {
                "pending": 0,
                "in_progress": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
            }
            for progress in self._progress.values():
                status = progress.get("status", "pending")
                summary[status] = summary.get(status, 0) + 1
            return summary


@dataclass(frozen=True)
class BulkInstallResult:
    """
    Complete result of bulk tool installation.

    Attributes:
        tools_attempted: Names of tools that were attempted
        successes: Successful installations
        failures: Failed installations
        skipped: Tools that were skipped (already installed, dependency failures)
        duration_seconds: Total execution time
        rollback_script: Path to generated rollback script (if any)
    """
    tools_attempted: tuple[str, ...]
    successes: tuple[InstallResult, ...]
    failures: tuple[InstallResult, ...]
    skipped: tuple[str, ...]
    duration_seconds: float
    rollback_script: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tools_attempted": list(self.tools_attempted),
            "successes": [r.to_dict() for r in self.successes],
            "failures": [r.to_dict() for r in self.failures],
            "skipped": list(self.skipped),
            "duration_seconds": self.duration_seconds,
            "rollback_script": self.rollback_script,
        }


def get_missing_tools(tool_names: Sequence[str], verbose: bool = False) -> list[str]:
    """
    Identify tools that are not currently installed.

    Args:
        tool_names: Names of tools to check
        verbose: Enable verbose logging

    Returns:
        List of tool names that are not installed
    """
    missing = []
    for tool_name in tool_names:
        binary_path = shutil.which(tool_name)
        if not binary_path:
            missing.append(tool_name)
            vlog(f"Tool not found: {tool_name}", verbose)
        else:
            vlog(f"Tool already installed: {tool_name} at {binary_path}", verbose)
    return missing


def resolve_dependencies(specs: Sequence[ToolSpec], verbose: bool = False) -> list[list[ToolSpec]]:
    """
    Resolve dependencies and return tools grouped by installation level.

    Uses topological sort to ensure dependencies are installed before dependents.

    Args:
        specs: Tool specifications with dependencies
        verbose: Enable verbose logging

    Returns:
        List of lists, where each inner list contains tools that can be installed in parallel
    """
    # Build dependency graph
    spec_map = {spec.tool_name: spec for spec in specs}
    in_degree = {spec.tool_name: 0 for spec in specs}
    adjacency = {spec.tool_name: [] for spec in specs}

    for spec in specs:
        for dep in spec.dependencies:
            if dep in spec_map:
                adjacency[dep].append(spec.tool_name)
                in_degree[spec.tool_name] += 1

    # Topological sort by levels
    levels: list[list[ToolSpec]] = []
    remaining = set(spec_map.keys())

    while remaining:
        # Find tools with no unmet dependencies
        ready = [tool for tool in remaining if in_degree[tool] == 0]
        if not ready:
            # Circular dependency detected
            vlog(f"Circular dependency detected for tools: {remaining}", verbose)
            # Add remaining tools to final level (will likely fail)
            levels.append([spec_map[tool] for tool in remaining])
            break

        # Add this level
        levels.append([spec_map[tool] for tool in ready])
        vlog(f"Installation level {len(levels)}: {ready}", verbose)

        # Remove ready tools and update in-degrees
        for tool in ready:
            remaining.remove(tool)
            for neighbor in adjacency[tool]:
                in_degree[neighbor] -= 1

    return levels


def get_tools_to_install(
    mode: str,
    tool_names: Sequence[str] | None,
    preset_name: str | None,
    config: Config,
    verbose: bool = False,
) -> list[ToolSpec]:
    """
    Determine which tools to install based on mode.

    Args:
        mode: Installation mode ("explicit", "missing", "preset", "all")
        tool_names: Explicit list of tool names (for "explicit" mode)
        preset_name: Preset name (for "preset" mode)
        config: Configuration object
        verbose: Enable verbose logging

    Returns:
        List of ToolSpec objects for tools to install
    """
    specs: list[ToolSpec] = []

    if mode == "explicit":
        if not tool_names:
            return []
        for name in tool_names:
            tool_config = config.get_tool_config(name)
            specs.append(ToolSpec(
                tool_name=name,
                package_name=name,
                target_version=tool_config.version if tool_config else "latest",
                language=None,
                dependencies=(),
            ))

    elif mode == "missing":
        all_tools = list(config.tools.keys())
        missing = get_missing_tools(all_tools, verbose)
        for name in missing:
            tool_config = config.get_tool_config(name)
            specs.append(ToolSpec(
                tool_name=name,
                package_name=name,
                target_version=tool_config.version if tool_config else "latest",
                language=None,
                dependencies=(),
            ))

    elif mode == "preset":
        if not preset_name or not hasattr(config, "presets"):
            vlog(f"Preset '{preset_name}' not found in config", verbose)
            return []
        preset_tools = getattr(config.presets, preset_name, [])
        for name in preset_tools:
            tool_config = config.get_tool_config(name)
            specs.append(ToolSpec(
                tool_name=name,
                package_name=name,
                target_version=tool_config.version if tool_config else "latest",
                language=None,
                dependencies=(),
            ))

    elif mode == "all":
        all_tools = list(config.tools.keys())
        for name in all_tools:
            tool_config = config.get_tool_config(name)
            specs.append(ToolSpec(
                tool_name=name,
                package_name=name,
                target_version=tool_config.version if tool_config else "latest",
                language=None,
                dependencies=(),
            ))

    vlog(f"Mode '{mode}' resolved to {len(specs)} tools", verbose)
    return specs


def group_by_package_manager(
    specs: Sequence[ToolSpec],
    config: Config,
    env: Environment,
    verbose: bool = False,
) -> dict[str, list[ToolSpec]]:
    """
    Group tools by their selected package manager.

    Args:
        specs: Tool specifications
        config: Configuration object
        env: Environment object
        verbose: Enable verbose logging

    Returns:
        Dictionary mapping package manager names to tool specs
    """
    groups: dict[str, list[ToolSpec]] = {}

    for spec in specs:
        pm_name, _ = select_package_manager(
            tool_name=spec.tool_name,
            language=spec.language,
            config=config,
            env=env,
            verbose=verbose,
        )
        if pm_name not in groups:
            groups[pm_name] = []
        groups[pm_name].append(spec)

    vlog(f"Grouped {len(specs)} tools into {len(groups)} package managers", verbose)
    return groups


def generate_rollback_script(results: Sequence[InstallResult], verbose: bool = False) -> str:
    """
    Generate a rollback script for successful installations.

    Args:
        results: Installation results
        verbose: Enable verbose logging

    Returns:
        Path to generated rollback script
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = f"/tmp/rollback_{timestamp}.sh"

    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("set -euo pipefail\n\n")
        f.write("# Rollback script for bulk installation\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n\n")

        for result in results:
            if result.success and result.binary_path:
                f.write(f"# Rollback: {result.tool_name}\n")
                pm = result.package_manager_used

                # Generate uninstall command based on package manager
                if pm in ("apt", "apt-get"):
                    f.write(f"sudo apt-get remove -y {result.tool_name}\n")
                elif pm == "dnf":
                    f.write(f"sudo dnf remove -y {result.tool_name}\n")
                elif pm == "pacman":
                    f.write(f"sudo pacman -R --noconfirm {result.tool_name}\n")
                elif pm == "brew":
                    f.write(f"brew uninstall {result.tool_name}\n")
                elif pm == "cargo":
                    f.write(f"cargo uninstall {result.tool_name}\n")
                elif pm in ("pip", "pipx", "uv"):
                    f.write(f"{pm} uninstall -y {result.tool_name}\n")
                elif pm == "npm":
                    f.write(f"npm uninstall -g {result.tool_name}\n")
                else:
                    f.write(f"# Manual removal required for {result.tool_name} ({pm})\n")

                f.write("\n")

    # Make script executable
    Path(script_path).chmod(0o755)
    vlog(f"Generated rollback script: {script_path}", verbose)
    return script_path


def execute_rollback(script_path: str, verbose: bool = False) -> bool:
    """
    Execute a rollback script.

    Args:
        script_path: Path to rollback script
        verbose: Enable verbose logging

    Returns:
        True if rollback succeeded, False otherwise
    """
    try:
        vlog(f"Executing rollback script: {script_path}", verbose)
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode == 0:
            vlog("Rollback completed successfully", verbose)
            return True
        else:
            vlog(f"Rollback failed: {result.stderr}", verbose)
            return False
    except Exception as e:
        vlog(f"Rollback error: {str(e)}", verbose)
        return False


def bulk_install(
    mode: str = "explicit",
    tool_names: Sequence[str] | None = None,
    preset_name: str | None = None,
    config: Config | None = None,
    env: Environment | None = None,
    max_workers: int | None = None,
    fail_fast: bool = False,
    atomic: bool = False,
    progress_tracker: ProgressTracker | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> BulkInstallResult:
    """
    Install multiple tools in parallel.

    Args:
        mode: Installation mode ("explicit", "missing", "preset", "all")
        tool_names: Explicit list of tool names (for "explicit" mode)
        preset_name: Preset name (for "preset" mode)
        config: Configuration object (loads defaults if None)
        env: Environment object (detects if None)
        max_workers: Maximum parallel workers (auto-detect if None)
        fail_fast: Stop immediately on first failure
        atomic: Automatically rollback on any failure
        progress_tracker: Optional progress tracker
        dry_run: If True, only plan without executing
        verbose: Enable verbose logging

    Returns:
        BulkInstallResult with installation outcomes
    """
    from .config import load_config
    from .environment import detect_environment

    # Load config and environment if not provided
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    start_time = time.time()

    # Determine tools to install
    specs = get_tools_to_install(mode, tool_names, preset_name, config, verbose)
    if not specs:
        vlog("No tools to install", verbose)
        return BulkInstallResult(
            tools_attempted=(),
            successes=(),
            failures=(),
            skipped=(),
            duration_seconds=time.time() - start_time,
        )

    # Resolve dependencies
    levels = resolve_dependencies(specs, verbose)
    vlog(f"Resolved {len(specs)} tools into {len(levels)} dependency levels", verbose)

    if dry_run:
        vlog("Dry-run mode: Not executing installation", verbose)
        return BulkInstallResult(
            tools_attempted=tuple(spec.tool_name for spec in specs),
            successes=(),
            failures=(),
            skipped=(),
            duration_seconds=time.time() - start_time,
        )

    # Initialize progress tracker
    if progress_tracker is None:
        progress_tracker = ProgressTracker()

    # Initialize all tools as pending
    for spec in specs:
        progress_tracker.update(spec.tool_name, "pending")

    # Determine max workers
    if max_workers is None:
        import os
        max_workers = min(16, os.cpu_count() or 4 + 4)

    # Execute installations level by level
    successes: list[InstallResult] = []
    failures: list[InstallResult] = []
    skipped: list[str] = []

    for level_idx, level_specs in enumerate(levels):
        vlog(f"Installing level {level_idx + 1}/{len(levels)}: {[s.tool_name for s in level_specs]}", verbose)

        # Install this level in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_spec = {
                executor.submit(
                    _install_with_progress,
                    spec,
                    config,
                    env,
                    progress_tracker,
                    verbose,
                ): spec
                for spec in level_specs
            }

            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    result = future.result()
                    if result.success:
                        successes.append(result)
                        progress_tracker.update(spec.tool_name, "success", f"v{result.installed_version}")
                    else:
                        failures.append(result)
                        progress_tracker.update(spec.tool_name, "failed", result.error_message or "Unknown error")

                        if fail_fast:
                            vlog(f"Fail-fast: Stopping due to {spec.tool_name} failure", verbose)
                            # Cancel remaining futures
                            for f in future_to_spec:
                                f.cancel()
                            break

                except Exception as e:
                    vlog(f"Unexpected error installing {spec.tool_name}: {str(e)}", verbose)
                    progress_tracker.update(spec.tool_name, "failed", str(e))

        # Stop if fail-fast triggered
        if fail_fast and failures:
            # Mark remaining tools as skipped
            for level in levels[level_idx + 1:]:
                for spec in level:
                    skipped.append(spec.tool_name)
                    progress_tracker.update(spec.tool_name, "skipped", "Skipped due to fail-fast")
            break

    duration = time.time() - start_time

    # Generate rollback script
    rollback_script = None
    if successes:
        rollback_script = generate_rollback_script(successes, verbose)

    # Handle atomic rollback
    if atomic and failures:
        vlog("Atomic rollback triggered due to failures", verbose)
        if rollback_script:
            execute_rollback(rollback_script, verbose)

    return BulkInstallResult(
        tools_attempted=tuple(spec.tool_name for spec in specs),
        successes=tuple(successes),
        failures=tuple(failures),
        skipped=tuple(skipped),
        duration_seconds=duration,
        rollback_script=rollback_script,
    )


def _install_with_progress(
    spec: ToolSpec,
    config: Config,
    env: Environment,
    progress_tracker: ProgressTracker,
    verbose: bool,
) -> InstallResult:
    """
    Install a tool with progress tracking.

    Args:
        spec: Tool specification
        config: Configuration object
        env: Environment object
        progress_tracker: Progress tracker
        verbose: Enable verbose logging

    Returns:
        InstallResult
    """
    progress_tracker.update(spec.tool_name, "in_progress", "Installing...")

    result = install_tool(
        tool_name=spec.tool_name,
        package_name=spec.package_name,
        target_version=spec.target_version,
        config=config,
        env=env,
        language=spec.language,
        dry_run=False,
        verbose=verbose,
    )

    return result
