"""
Prerequisite resolution for tool installation.

Handles dependency chain resolution and interactive user prompts
for installing missing prerequisites before tool installation.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .common import vlog

if TYPE_CHECKING:
    from .catalog import ToolCatalog


# Mapping from install_method to required tools
# These tools must be available before using that install method
INSTALL_METHOD_PREREQUISITES: dict[str, list[str]] = {
    "uv_tool": ["uv"],
    "npm_global": ["node"],
    "npm_self_update": ["node"],
    "pip": ["python"],
    "pipx": ["pipx"],
    "cargo": ["rust"],
    "go_install": ["go"],
    "composer": ["composer"],
}

# Mapping from runtime/tool to its own prerequisites
# These are recursive dependencies (e.g., uv needs python)
RUNTIME_PREREQUISITES: dict[str, list[str]] = {
    "uv": ["python"],
    "pipx": ["python"],
    "composer": ["php"],
    "npm": ["node"],
    "pnpm": ["node"],
    "yarn": ["node"],
}

# Binary names for checking if a runtime is installed
# Maps logical tool name to actual binary to check
RUNTIME_BINARIES: dict[str, str] = {
    "python": "python3",
    "node": "node",
    "php": "php",
    "go": "go",
    "rust": "rustc",
    "composer": "composer",
    "uv": "uv",
    "pipx": "pipx",
    "npm": "npm",
    "pnpm": "pnpm",
    "yarn": "yarn",
}


@dataclass
class PrerequisiteResult:
    """Result of prerequisite check and resolution."""

    tool_name: str
    prerequisites: list[str]  # Ordered list of prerequisites (install order)
    missing: list[str]  # Prerequisites that are not installed
    installed: list[str]  # Prerequisites that are already installed
    user_approved: bool  # Whether user approved installing missing prereqs
    user_declined: list[str]  # Prerequisites user declined to install


def is_tool_installed(tool_name: str, verbose: bool = False) -> bool:
    """
    Check if a tool/runtime is installed and available.

    Args:
        tool_name: Logical tool name (e.g., "python", "node", "uv")
        verbose: Enable verbose logging

    Returns:
        True if tool is available in PATH
    """
    # Get binary name for this tool
    binary = RUNTIME_BINARIES.get(tool_name, tool_name)

    # Check if binary exists
    path = shutil.which(binary)
    if path:
        vlog(f"Found {tool_name} at: {path}", verbose)
        return True

    # Special case: python might be python3
    if tool_name == "python":
        if shutil.which("python"):
            vlog(f"Found python (as python)", verbose)
            return True

    vlog(f"{tool_name} not found in PATH", verbose)
    return False


def get_install_method_for_tool(tool_name: str, catalog: ToolCatalog) -> str | None:
    """
    Get the install_method for a tool from the catalog.

    Args:
        tool_name: Tool name
        catalog: Tool catalog

    Returns:
        Install method string or None if not found
    """
    entry = catalog.get(tool_name)
    if entry:
        return entry.install_method
    return None


def resolve_prerequisites(
    tool_name: str,
    catalog: ToolCatalog,
    verbose: bool = False,
    _seen: set[str] | None = None,
) -> list[str]:
    """
    Resolve all prerequisites for a tool in installation order.

    Returns an ordered list where each prerequisite comes before
    tools that depend on it. The tool itself is NOT included.

    Args:
        tool_name: Tool to resolve prerequisites for
        catalog: Tool catalog for looking up install methods
        verbose: Enable verbose logging
        _seen: Internal set for cycle detection

    Returns:
        Ordered list of prerequisites (empty if none needed)
    """
    if _seen is None:
        _seen = set()

    # Cycle detection
    if tool_name in _seen:
        vlog(f"Cycle detected for {tool_name}, skipping", verbose)
        return []

    _seen.add(tool_name)
    result: list[str] = []

    # Get direct prerequisites based on install method
    install_method = get_install_method_for_tool(tool_name, catalog)
    direct_prereqs: list[str] = []

    if install_method and install_method in INSTALL_METHOD_PREREQUISITES:
        direct_prereqs = INSTALL_METHOD_PREREQUISITES[install_method].copy()
        vlog(f"{tool_name} (install_method={install_method}) needs: {direct_prereqs}", verbose)

    # Also check if tool itself has runtime prerequisites
    if tool_name in RUNTIME_PREREQUISITES:
        for prereq in RUNTIME_PREREQUISITES[tool_name]:
            if prereq not in direct_prereqs:
                direct_prereqs.append(prereq)
        vlog(f"{tool_name} runtime needs: {RUNTIME_PREREQUISITES[tool_name]}", verbose)

    # Recursively resolve prerequisites of prerequisites
    for prereq in direct_prereqs:
        # First, get this prereq's own prerequisites
        sub_prereqs = resolve_prerequisites(prereq, catalog, verbose, _seen.copy())
        for sub in sub_prereqs:
            if sub not in result:
                result.append(sub)

        # Then add the prereq itself
        if prereq not in result:
            result.append(prereq)

    vlog(f"Full prerequisite chain for {tool_name}: {result}", verbose)
    return result


def check_prerequisites(
    prerequisites: list[str],
    verbose: bool = False,
) -> tuple[list[str], list[str]]:
    """
    Check which prerequisites are installed and which are missing.

    Args:
        prerequisites: List of prerequisite tool names
        verbose: Enable verbose logging

    Returns:
        Tuple of (installed, missing)
    """
    installed = []
    missing = []

    for prereq in prerequisites:
        if is_tool_installed(prereq, verbose):
            installed.append(prereq)
        else:
            missing.append(prereq)

    return installed, missing


def prompt_install_prerequisite(
    prereq: str,
    for_tool: str,
    remaining: list[str] | None = None,
) -> bool:
    """
    Prompt user to install a missing prerequisite.

    Args:
        prereq: Prerequisite tool name
        for_tool: Tool that requires this prerequisite
        remaining: Other prerequisites that will also be needed

    Returns:
        True if user approves, False if user declines
    """
    print(f"\n{for_tool} requires {prereq} (not installed)", file=sys.stderr)

    if remaining:
        print(f"  Also needed: {', '.join(remaining)}", file=sys.stderr)

    try:
        response = input(f"Install {prereq} now? [Y/n] ").strip().lower()
        return response in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nInstallation cancelled.", file=sys.stderr)
        return False


def prompt_install_all_prerequisites(
    missing: list[str],
    for_tool: str,
) -> bool:
    """
    Prompt user to install all missing prerequisites at once.

    Args:
        missing: List of missing prerequisite tool names
        for_tool: Tool that requires these prerequisites

    Returns:
        True if user approves, False if user declines
    """
    if not missing:
        return True

    print(f"\n{for_tool} requires the following tools (not installed):", file=sys.stderr)
    for prereq in missing:
        print(f"  - {prereq}", file=sys.stderr)

    try:
        response = input(f"\nInstall all prerequisites? [Y/n] ").strip().lower()
        return response in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nInstallation cancelled.", file=sys.stderr)
        return False


def ensure_prerequisites(
    tool_name: str,
    catalog: ToolCatalog,
    install_func: callable | None = None,
    interactive: bool = True,
    verbose: bool = False,
) -> PrerequisiteResult:
    """
    Ensure all prerequisites for a tool are installed.

    This is the main entry point for prerequisite resolution. It:
    1. Resolves the full prerequisite chain
    2. Checks which are already installed
    3. Prompts user for missing prerequisites (if interactive)
    4. Installs approved prerequisites in order

    Args:
        tool_name: Tool to check prerequisites for
        catalog: Tool catalog
        install_func: Function to call for installing tools.
                     Signature: install_func(tool_name: str) -> bool
                     If None, prerequisites are not installed (dry-run mode)
        interactive: Whether to prompt user (False for non-interactive mode)
        verbose: Enable verbose logging

    Returns:
        PrerequisiteResult with resolution outcome
    """
    # Resolve full prerequisite chain
    prerequisites = resolve_prerequisites(tool_name, catalog, verbose)

    if not prerequisites:
        vlog(f"No prerequisites needed for {tool_name}", verbose)
        return PrerequisiteResult(
            tool_name=tool_name,
            prerequisites=[],
            missing=[],
            installed=[],
            user_approved=True,
            user_declined=[],
        )

    # Check what's installed
    installed, missing = check_prerequisites(prerequisites, verbose)

    if not missing:
        vlog(f"All prerequisites for {tool_name} are installed", verbose)
        return PrerequisiteResult(
            tool_name=tool_name,
            prerequisites=prerequisites,
            missing=[],
            installed=installed,
            user_approved=True,
            user_declined=[],
        )

    vlog(f"Missing prerequisites for {tool_name}: {missing}", verbose)

    # Non-interactive mode: report missing but don't prompt
    if not interactive:
        return PrerequisiteResult(
            tool_name=tool_name,
            prerequisites=prerequisites,
            missing=missing,
            installed=installed,
            user_approved=False,
            user_declined=missing,
        )

    # Interactive mode: prompt user
    user_declined = []

    # Ask about all missing at once for better UX
    if not prompt_install_all_prerequisites(missing, tool_name):
        return PrerequisiteResult(
            tool_name=tool_name,
            prerequisites=prerequisites,
            missing=missing,
            installed=installed,
            user_approved=False,
            user_declined=missing,
        )

    # User approved - install prerequisites in order
    if install_func is not None:
        newly_installed = []
        for prereq in missing:
            print(f"\nInstalling {prereq}...", file=sys.stderr)
            try:
                success = install_func(prereq)
                if success:
                    print(f"  {prereq} installed successfully", file=sys.stderr)
                    newly_installed.append(prereq)
                else:
                    print(f"  Failed to install {prereq}", file=sys.stderr)
                    user_declined.append(prereq)
                    # Stop on first failure - can't continue without prereq
                    user_declined.extend([p for p in missing if p not in newly_installed and p not in user_declined])
                    break
            except Exception as e:
                print(f"  Error installing {prereq}: {e}", file=sys.stderr)
                user_declined.append(prereq)
                user_declined.extend([p for p in missing if p not in newly_installed and p not in user_declined])
                break

        # Update installed/missing lists
        installed.extend(newly_installed)
        missing = [m for m in missing if m not in newly_installed]

    return PrerequisiteResult(
        tool_name=tool_name,
        prerequisites=prerequisites,
        missing=missing,
        installed=installed,
        user_approved=len(user_declined) == 0,
        user_declined=user_declined,
    )


def format_prerequisite_error(result: PrerequisiteResult) -> str:
    """
    Format a human-readable error message for failed prerequisite resolution.

    Args:
        result: PrerequisiteResult from ensure_prerequisites

    Returns:
        Error message string
    """
    if result.user_approved and not result.missing:
        return ""

    if result.user_declined:
        declined = ", ".join(result.user_declined)
        return f"Prerequisites not installed (user declined): {declined}"

    if result.missing:
        missing = ", ".join(result.missing)
        return f"Missing prerequisites: {missing}"

    return "Unknown prerequisite error"
