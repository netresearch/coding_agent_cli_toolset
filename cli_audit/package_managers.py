"""
Package manager registry and selection logic.

Implements the package manager hierarchy:
1. Vendor-specific tools (uv, rustup, nvm) - highest priority
2. GitHub releases (standalone binaries) - medium priority
3. System package managers (apt, brew) - lowest priority
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .common import vlog
from .config import Config, Preferences
from .environment import Environment


# Cache for package manager availability checks
_PM_CACHE: dict[str, bool] = {}
_PM_CACHE_LOCK = threading.Lock()


@dataclass(frozen=True)
class PackageManager:
    """
    Package manager definition.

    Attributes:
        name: Package manager identifier (e.g., "uv", "cargo", "npm")
        display_name: Human-readable name
        check_command: Command to check if manager is available
        install_command_template: Template for install command (use {package} placeholder)
        category: Package manager category ("vendor", "github", "system")
        languages: Languages/ecosystems this manager supports
    """
    name: str
    display_name: str
    check_command: tuple[str, ...]
    install_command_template: tuple[str, ...]
    category: str
    languages: tuple[str, ...] = ()

    def is_available(self, timeout: int = 1) -> bool:
        """
        Check if this package manager is available on the system.

        Args:
            timeout: Timeout in seconds for check command

        Returns:
            True if package manager is installed and accessible
        """
        # Check cache first
        with _PM_CACHE_LOCK:
            if self.name in _PM_CACHE:
                return _PM_CACHE[self.name]

        try:
            result = subprocess.run(
                self.check_command,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
            available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            available = False

        # Cache result
        with _PM_CACHE_LOCK:
            _PM_CACHE[self.name] = available

        return available

    def get_install_command(self, package: str, version: str = "latest") -> tuple[str, ...]:
        """
        Get install command for a package.

        Args:
            package: Package name
            version: Target version (may be ignored by some managers)

        Returns:
            Command tuple to install the package
        """
        # Replace placeholders in template
        command = []
        for part in self.install_command_template:
            part = part.replace("{package}", package)
            if version != "latest":
                part = part.replace("{version}", version)
            command.append(part)
        return tuple(command)


# Package Manager Registry
# Ordered by general preference within each category

PACKAGE_MANAGERS = (
    # Python package managers (vendor tools)
    PackageManager(
        name="uv",
        display_name="uv",
        check_command=("uv", "--version"),
        install_command_template=("uv", "tool", "install", "{package}"),
        category="vendor",
        languages=("python",),
    ),
    PackageManager(
        name="pipx",
        display_name="pipx",
        check_command=("pipx", "--version"),
        install_command_template=("pipx", "install", "{package}"),
        category="vendor",
        languages=("python",),
    ),
    PackageManager(
        name="pip",
        display_name="pip",
        check_command=("pip", "--version"),
        install_command_template=("pip", "install", "--user", "{package}"),
        category="vendor",
        languages=("python",),
    ),

    # Rust package managers (vendor tools)
    PackageManager(
        name="rustup",
        display_name="rustup",
        check_command=("rustup", "--version"),
        install_command_template=("rustup", "install", "{package}"),
        category="vendor",
        languages=("rust",),
    ),
    PackageManager(
        name="cargo",
        display_name="cargo",
        check_command=("cargo", "--version"),
        install_command_template=("cargo", "install", "{package}"),
        category="vendor",
        languages=("rust",),
    ),

    # Node.js package managers (vendor tools)
    PackageManager(
        name="nvm",
        display_name="nvm",
        check_command=("nvm", "--version"),
        install_command_template=("nvm", "install", "{package}"),
        category="vendor",
        languages=("node", "javascript"),
    ),
    PackageManager(
        name="npm",
        display_name="npm",
        check_command=("npm", "--version"),
        install_command_template=("npm", "install", "-g", "{package}"),
        category="vendor",
        languages=("node", "javascript"),
    ),
    PackageManager(
        name="yarn",
        display_name="yarn",
        check_command=("yarn", "--version"),
        install_command_template=("yarn", "global", "add", "{package}"),
        category="vendor",
        languages=("node", "javascript"),
    ),
    PackageManager(
        name="pnpm",
        display_name="pnpm",
        check_command=("pnpm", "--version"),
        install_command_template=("pnpm", "add", "-g", "{package}"),
        category="vendor",
        languages=("node", "javascript"),
    ),

    # Go package manager
    PackageManager(
        name="go",
        display_name="go install",
        check_command=("go", "version"),
        install_command_template=("go", "install", "{package}@latest"),
        category="vendor",
        languages=("go",),
    ),

    # GitHub releases (for standalone binaries)
    PackageManager(
        name="github",
        display_name="GitHub Releases",
        check_command=("curl", "--version"),  # Requires curl or wget
        install_command_template=("curl", "-fsSL", "{package}"),  # Placeholder
        category="github",
        languages=(),
    ),

    # System package managers
    PackageManager(
        name="apt",
        display_name="apt",
        check_command=("apt", "--version"),
        install_command_template=("apt", "install", "-y", "{package}"),
        category="system",
        languages=(),
    ),
    PackageManager(
        name="brew",
        display_name="Homebrew",
        check_command=("brew", "--version"),
        install_command_template=("brew", "install", "{package}"),
        category="system",
        languages=(),
    ),
    PackageManager(
        name="pacman",
        display_name="pacman",
        check_command=("pacman", "--version"),
        install_command_template=("pacman", "-S", "--noconfirm", "{package}"),
        category="system",
        languages=(),
    ),
    PackageManager(
        name="dnf",
        display_name="dnf",
        check_command=("dnf", "--version"),
        install_command_template=("dnf", "install", "-y", "{package}"),
        category="system",
        languages=(),
    ),
)


# Package manager lookup by name
_PM_BY_NAME = {pm.name: pm for pm in PACKAGE_MANAGERS}


def get_package_manager(name: str) -> PackageManager | None:
    """
    Get package manager by name.

    Args:
        name: Package manager name

    Returns:
        PackageManager object, or None if not found
    """
    return _PM_BY_NAME.get(name)


def get_available_package_managers(
    languages: Sequence[str] | None = None,
    timeout: int = 1,
    max_workers: int = 8,
) -> list[PackageManager]:
    """
    Get list of available package managers, optionally filtered by language.

    Args:
        languages: Optional list of languages to filter by
        timeout: Timeout for availability checks
        max_workers: Maximum parallel workers for checks

    Returns:
        List of available PackageManager objects
    """
    # Filter by language if specified
    managers_to_check = PACKAGE_MANAGERS
    if languages:
        lang_set = set(languages)
        managers_to_check = tuple(
            pm for pm in PACKAGE_MANAGERS
            if not pm.languages or lang_set.intersection(pm.languages)
        )

    # Check availability in parallel
    available = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(pm.is_available, timeout): pm
            for pm in managers_to_check
        }
        for future in as_completed(futures):
            pm = futures[future]
            try:
                if future.result():
                    available.append(pm)
            except Exception:
                pass  # Skip managers that fail availability check

    return available


def get_default_hierarchy(language: str) -> list[str]:
    """
    Get default package manager hierarchy for a language.

    Args:
        language: Language/ecosystem name

    Returns:
        List of package manager names in preference order
    """
    hierarchies = {
        "python": ["uv", "pipx", "pip"],
        "rust": ["rustup", "cargo"],
        "node": ["nvm", "npm"],
        "javascript": ["nvm", "npm", "yarn", "pnpm"],
        "go": ["go"],
    }
    return hierarchies.get(language, [])


def select_package_manager(
    tool_name: str,
    language: str | None,
    config: Config,
    env: Environment,
    verbose: bool = False,
) -> tuple[str, str]:
    """
    Select best package manager for installing a tool.

    Selection priority:
    1. Explicit config override (config.tools[tool_name].method)
    2. Custom language hierarchy (config.preferences.package_managers[language])
    3. Environment-specific preferences
    4. Default language hierarchy
    5. First available package manager

    Args:
        tool_name: Name of the tool to install
        language: Language/ecosystem of the tool (e.g., "python", "rust")
        config: Configuration object
        env: Environment object
        verbose: Enable verbose logging

    Returns:
        Tuple of (package_manager_name, selection_reason)

    Raises:
        ValueError: If no suitable package manager found
    """
    # Check for explicit config override
    tool_config = config.get_tool_config(tool_name)
    if tool_config.method:
        pm = get_package_manager(tool_config.method)
        if pm and pm.is_available():
            vlog(f"Using explicit config method for {tool_name}: {tool_config.method}", verbose)
            return (tool_config.method, "config_override")
        elif pm:
            vlog(f"Config method {tool_config.method} not available for {tool_name}", verbose)
            # Fall through to other methods
        else:
            vlog(f"Unknown package manager {tool_config.method} for {tool_name}", verbose)

    # Get hierarchy to check
    hierarchy = []

    # Check for custom language hierarchy in config
    if language and language in config.preferences.package_managers:
        hierarchy = config.preferences.package_managers[language]
        vlog(f"Using custom hierarchy for {language}: {hierarchy}", verbose)
    # Use default language hierarchy
    elif language:
        hierarchy = get_default_hierarchy(language)
        vlog(f"Using default hierarchy for {language}: {hierarchy}", verbose)

    # Adjust hierarchy based on environment
    if env.mode == "ci":
        # CI prefers speed: favor vendor tools, then GitHub
        pass  # Default hierarchy is usually fine
    elif env.mode == "server":
        # Server prefers stability: favor system packages
        # Move system managers to front
        system_managers = ["apt", "brew", "pacman", "dnf"]
        hierarchy = [pm for pm in system_managers if pm in hierarchy] + \
                    [pm for pm in hierarchy if pm not in system_managers]
    # Workstation uses default hierarchy (vendor tools preferred)

    # Try hierarchy in order
    for pm_name in hierarchy:
        pm = get_package_manager(pm_name)
        if pm and pm.is_available():
            reason = f"hierarchy_{language or 'default'}"
            if env.mode != "workstation":
                reason += f"_env_{env.mode}"
            vlog(f"Selected {pm_name} for {tool_name} (reason: {reason})", verbose)
            return (pm_name, reason)

    # Fallback: try config fallback method
    if tool_config.fallback:
        pm = get_package_manager(tool_config.fallback)
        if pm and pm.is_available():
            vlog(f"Using fallback method for {tool_name}: {tool_config.fallback}", verbose)
            return (tool_config.fallback, "config_fallback")

    # Last resort: any available package manager
    available = get_available_package_managers(
        languages=[language] if language else None,
        max_workers=8,
    )
    if available:
        # Prefer vendor tools over system
        vendor = [pm for pm in available if pm.category == "vendor"]
        if vendor:
            vlog(f"Using first available vendor tool for {tool_name}: {vendor[0].name}", verbose)
            return (vendor[0].name, "first_available_vendor")
        vlog(f"Using first available manager for {tool_name}: {available[0].name}", verbose)
        return (available[0].name, "first_available")

    # No package managers available
    raise ValueError(
        f"No suitable package manager found for {tool_name}. "
        f"Please install a package manager for {language or 'this tool'}."
    )


def clear_cache() -> None:
    """Clear the package manager availability cache."""
    with _PM_CACHE_LOCK:
        _PM_CACHE.clear()
