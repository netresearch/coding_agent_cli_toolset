"""
Upgrade management with version comparison and rollback support.

Handles single and bulk tool upgrades with breaking change detection,
automatic rollback, and version verification.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys  # noqa: F401 - used by test patches
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Sequence

from .breaking_changes import (
    check_breaking_change_policy,
    confirm_breaking_change,
    confirm_bulk_breaking_changes,
    filter_by_breaking_changes,
    format_breaking_change_warning,
    is_major_upgrade,
)
from .common import vlog
from .config import Config
from .environment import Environment
from .installer import InstallResult, install_tool, validate_installation
from .package_managers import select_package_manager


# Version cache with configurable TTL
_version_cache: dict[tuple[str, str], tuple[str, float]] = {}


@dataclass(frozen=True)
class UpgradeBackup:
    """
    Backup of tool state before upgrade.

    Attributes:
        tool_name: Name of the tool
        version: Version before upgrade
        binary_path: Path to binary that was backed up
        backup_path: Temp directory containing backups
        config_paths: Config files that were backed up
        timestamp: When backup was created
        package_manager: Package manager used
        checksum: SHA256 checksum of backed up binary
    """
    tool_name: str
    version: str
    binary_path: str
    backup_path: str
    config_paths: tuple[str, ...]
    timestamp: float
    package_manager: str
    checksum: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "version": self.version,
            "binary_path": self.binary_path,
            "backup_path": self.backup_path,
            "config_paths": list(self.config_paths),
            "timestamp": self.timestamp,
            "package_manager": self.package_manager,
            "checksum": self.checksum,
        }


@dataclass(frozen=True)
class UpgradeResult:
    """
    Result of upgrading a single tool.

    Attributes:
        tool_name: Name of the tool
        success: Whether upgrade succeeded
        previous_version: Version before upgrade
        new_version: Version after upgrade (if successful)
        backup: Backup information (if created)
        breaking_change: Whether this was a major version upgrade
        breaking_change_accepted: Whether user accepted breaking change
        rollback_executed: Whether automatic rollback was triggered
        rollback_success: Whether rollback succeeded (if executed)
        install_result: Underlying installation result from Phase 2.2
        duration_seconds: Total upgrade time
        error_message: Human-readable error message if failed
    """
    tool_name: str
    success: bool
    previous_version: str | None
    new_version: str | None
    backup: UpgradeBackup | None
    breaking_change: bool = False
    breaking_change_accepted: bool = False
    rollback_executed: bool = False
    rollback_success: bool | None = None
    install_result: InstallResult | None = None
    duration_seconds: float = 0.0
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "backup": self.backup.to_dict() if self.backup else None,
            "breaking_change": self.breaking_change,
            "breaking_change_accepted": self.breaking_change_accepted,
            "rollback_executed": self.rollback_executed,
            "rollback_success": self.rollback_success,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class UpgradeCandidate:
    """
    Tool that has an available upgrade.

    Attributes:
        tool_name: Name of the tool
        current_version: Currently installed version
        available_version: Latest available version
        breaking_change: Whether upgrade is a major version bump
        package_manager: Package manager to use for upgrade
    """
    tool_name: str
    current_version: str
    available_version: str
    breaking_change: bool
    package_manager: str

    def version_jump_description(self) -> str:
        """Human-readable version jump description."""
        if self.breaking_change:
            return f"{self.current_version} → {self.available_version} (BREAKING)"
        else:
            return f"{self.current_version} → {self.available_version}"


@dataclass(frozen=True)
class BulkUpgradeResult:
    """
    Result of bulk upgrade operation.

    Attributes:
        tools_attempted: Names of tools that were attempted
        upgrades: Successful upgrades
        skipped: Tools that were skipped (up-to-date, blocked by policy, etc.)
        failures: Failed upgrades
        duration_seconds: Total execution time
        breaking_changes_count: Number of breaking changes encountered
        rollbacks_executed: Number of automatic rollbacks performed
    """
    tools_attempted: tuple[str, ...]
    upgrades: tuple[UpgradeResult, ...]
    skipped: tuple[str, ...]
    failures: tuple[UpgradeResult, ...]
    duration_seconds: float
    breaking_changes_count: int
    rollbacks_executed: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tools_attempted": list(self.tools_attempted),
            "upgrades": [u.to_dict() for u in self.upgrades],
            "skipped": list(self.skipped),
            "failures": [f.to_dict() for f in self.failures],
            "duration_seconds": self.duration_seconds,
            "breaking_changes_count": self.breaking_changes_count,
            "rollbacks_executed": self.rollbacks_executed,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        return f"""
Upgrade Summary:
  ✅ Upgraded: {len(self.upgrades)}
  ❌ Failed: {len(self.failures)}
  ⏭️  Skipped: {len(self.skipped)}
  ⚠️  Breaking changes: {self.breaking_changes_count}
  🔄 Rollbacks: {self.rollbacks_executed}
  ⏱️  Duration: {self.duration_seconds:.1f}s
"""


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.

    Args:
        v1: First version
        v2: Second version

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    try:
        from packaging import version
        ver1 = version.parse(v1)
        ver2 = version.parse(v2)

        if ver1 < ver2:
            return -1
        elif ver1 > ver2:
            return 1
        else:
            return 0
    except Exception:
        # Fallback to string comparison
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0


def get_available_version(
    tool_name: str,
    package_manager: str,
    current_version: str | None = None,
    cache_ttl: int = 3600,
    verbose: bool = False,
) -> str | None:
    """
    Query package manager for latest available version.

    Args:
        tool_name: Name of the tool
        package_manager: Package manager to query
        current_version: Currently installed version (unused, for future optimizations)
        cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
        verbose: Enable verbose logging

    Returns:
        Latest available version, or None if cannot determine
    """
    # Check cache first
    cache_key = (tool_name, package_manager)
    if cache_key in _version_cache:
        cached_version, cached_time = _version_cache[cache_key]
        if time.time() - cached_time < cache_ttl:
            vlog(f"Using cached version for {tool_name}: {cached_version}", verbose)
            return cached_version

    vlog(f"Querying {package_manager} for {tool_name} latest version...", verbose)

    try:
        if package_manager == "cargo":
            result = subprocess.run(
                ["cargo", "search", tool_name, "--limit", "1"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                # Parse: 'ripgrep = "14.1.1"    # Description'
                match = re.search(rf'{re.escape(tool_name)}\s*=\s*"([^"]+)"', result.stdout)
                if match:
                    version_str = match.group(1)
                    _version_cache[cache_key] = (version_str, time.time())
                    return version_str

        elif package_manager in ("pip", "uv", "pipx"):
            # Use PyPI JSON API for reliability
            import json
            import urllib.request
            try:
                url = f"https://pypi.org/pypi/{tool_name}/json"
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read())
                    pypi_version: str | None = data.get("info", {}).get("version")
                    version_str = pypi_version
                    if version_str:
                        _version_cache[cache_key] = (version_str, time.time())
                        return version_str
            except Exception:
                pass

        elif package_manager == "npm":
            result = subprocess.run(
                ["npm", "view", tool_name, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_str = result.stdout.strip()
                if version_str:
                    _version_cache[cache_key] = (version_str, time.time())
                    return version_str

        elif package_manager == "apt":
            result = subprocess.run(
                ["apt-cache", "policy", tool_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                # Parse: "  Candidate: 14.1.1-1"
                match = re.search(r'Candidate:\s+([^\s]+)', result.stdout)
                if match:
                    version_str = match.group(1).split('-')[0]  # Remove Debian revision
                    _version_cache[cache_key] = (version_str, time.time())
                    return version_str

        elif package_manager == "brew":
            result = subprocess.run(
                ["brew", "info", tool_name, "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                if data and len(data) > 0:
                    go_version: str | None = data[0].get("versions", {}).get("stable")
                    version_str = go_version
                    if version_str:
                        _version_cache[cache_key] = (version_str, time.time())
                        return version_str

        # More package managers can be added here

    except Exception as e:
        vlog(f"Error querying version for {tool_name}: {e}", verbose)

    return None


def check_upgrade_available(
    tool_name: str,
    package_manager: str,
    cache_ttl: int = 3600,
    verbose: bool = False,
) -> tuple[bool, str | None, str | None]:
    """
    Check if upgrade is available for a tool.

    Args:
        tool_name: Name of the tool
        package_manager: Package manager to use
        cache_ttl: Cache time-to-live in seconds
        verbose: Enable verbose logging

    Returns:
        (upgrade_available, current_version, latest_version)
    """
    # Get current version
    success, binary_path, current_version = validate_installation(tool_name, verbose=verbose)
    if not success or not current_version:
        return (False, None, None)

    # Get latest version
    latest_version = get_available_version(tool_name, package_manager, current_version, cache_ttl, verbose)
    if not latest_version:
        return (False, current_version, None)

    # Compare versions
    if compare_versions(current_version, latest_version) < 0:
        return (True, current_version, latest_version)
    else:
        return (False, current_version, latest_version)


def clear_version_cache():
    """Clear the version query cache."""
    _version_cache.clear()


def get_config_paths(tool_name: str) -> list[str]:
    """
    Get common config file paths for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        List of existing config file paths
    """
    paths = []

    # User config
    home = os.path.expanduser("~")
    potential_paths = [
        os.path.join(home, f".{tool_name}rc"),
        os.path.join(home, ".config", tool_name, "config"),
        os.path.join(home, ".config", tool_name, f"{tool_name}.conf"),
        os.path.join(home, ".config", tool_name, f"{tool_name}.yml"),
        os.path.join(home, ".config", tool_name, f"{tool_name}.yaml"),
    ]

    # Project config (if in project directory)
    potential_paths.extend([
        f".{tool_name}.yml",
        f".{tool_name}.yaml",
        f".{tool_name}.json",
        f".{tool_name}rc",
    ])

    # Validate paths stay within safe boundaries
    for path in potential_paths:
        if os.path.exists(path):
            real_path = os.path.realpath(path)
            # Ensure path is within user home or current directory
            if real_path.startswith(home) or real_path.startswith(os.getcwd()):
                paths.append(path)

    return paths


def create_upgrade_backup(
    tool_name: str,
    binary_path: str,
    version: str,
    package_manager: str,
    verbose: bool = False,
) -> UpgradeBackup:
    """
    Create backup before upgrade.

    Args:
        tool_name: Name of tool
        binary_path: Path to binary
        version: Current version
        package_manager: Package manager used
        verbose: Enable verbose logging

    Returns:
        UpgradeBackup with backup location

    Raises:
        OSError: If backup creation fails
    """
    # Create backup directory
    backup_dir = tempfile.mkdtemp(prefix=f"upgrade_backup_{tool_name}_")
    vlog(f"Creating backup in: {backup_dir}", verbose)

    # Calculate checksum of binary
    with open(binary_path, 'rb') as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    # Backup binary
    binary_backup = os.path.join(backup_dir, os.path.basename(binary_path))
    shutil.copy2(binary_path, binary_backup)
    vlog(f"Backed up binary: {binary_path} → {binary_backup}", verbose)

    # Backup configs
    config_paths = get_config_paths(tool_name)
    backed_up_configs = []

    for config_path in config_paths:
        try:
            config_backup = os.path.join(backup_dir, os.path.basename(config_path))
            shutil.copy2(config_path, config_backup)
            backed_up_configs.append(config_path)
            vlog(f"Backed up config: {config_path}", verbose)
        except Exception as e:
            vlog(f"Failed to backup config {config_path}: {e}", verbose)
            # Continue with other configs

    return UpgradeBackup(
        tool_name=tool_name,
        version=version,
        binary_path=binary_path,
        backup_path=backup_dir,
        config_paths=tuple(backed_up_configs),
        timestamp=time.time(),
        package_manager=package_manager,
        checksum=checksum,
    )


def restore_from_backup(backup: UpgradeBackup, verbose: bool = False) -> bool:
    """
    Restore tool from backup.

    Args:
        backup: Backup to restore from
        verbose: Enable verbose logging

    Returns:
        True if restore succeeded, False otherwise
    """
    try:
        vlog(f"Restoring {backup.tool_name} from backup...", verbose)

        # Verify backup integrity
        binary_backup = os.path.join(backup.backup_path, os.path.basename(backup.binary_path))
        with open(binary_backup, 'rb') as f:
            actual_checksum = hashlib.sha256(f.read()).hexdigest()

        if actual_checksum != backup.checksum:
            vlog(f"Backup checksum mismatch! Expected: {backup.checksum}, got: {actual_checksum}", verbose)
            return False

        # Restore binary
        shutil.copy2(binary_backup, backup.binary_path)
        vlog(f"Restored binary: {backup.binary_path}", verbose)

        # Restore configs
        for config_path in backup.config_paths:
            config_backup = os.path.join(backup.backup_path, os.path.basename(config_path))
            if os.path.exists(config_backup):
                shutil.copy2(config_backup, config_path)
                vlog(f"Restored config: {config_path}", verbose)

        vlog(f"Rollback successful: {backup.tool_name} → {backup.version}", verbose)
        return True

    except Exception as e:
        vlog(f"Restore failed: {e}", verbose)
        return False


def cleanup_backup(backup: UpgradeBackup, verbose: bool = False):
    """
    Clean up backup directory.

    Args:
        backup: Backup to clean up
        verbose: Enable verbose logging
    """
    try:
        if os.path.exists(backup.backup_path):
            shutil.rmtree(backup.backup_path)
            vlog(f"Cleaned up backup: {backup.backup_path}", verbose)
    except Exception as e:
        vlog(f"Failed to cleanup backup: {e}", verbose)


def cleanup_old_backups(retention_days: int = 7, verbose: bool = False):
    """
    Clean up backups older than retention period.

    Args:
        retention_days: Number of days to keep backups
        verbose: Enable verbose logging
    """
    import glob

    backup_dirs = glob.glob("/tmp/upgrade_backup_*")
    cutoff = time.time() - (retention_days * 86400)

    for backup_dir in backup_dirs:
        try:
            if os.path.getmtime(backup_dir) < cutoff:
                shutil.rmtree(backup_dir)
                vlog(f"Cleaned up old backup: {backup_dir}", verbose)
        except Exception as e:
            vlog(f"Failed to cleanup {backup_dir}: {e}", verbose)


def upgrade_tool(
    tool_name: str,
    target_version: str = "latest",
    config: Config | None = None,
    env: Environment | None = None,
    force: bool = False,
    skip_backup: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> UpgradeResult:
    """
    Upgrade a single tool to a newer version.

    Args:
        tool_name: Name of the tool to upgrade
        target_version: Target version ("latest" or specific version)
        config: Configuration object (loads defaults if None)
        env: Environment object (detects if None)
        force: Skip breaking change confirmation
        skip_backup: Don't create backup (faster but no rollback)
        dry_run: Show what would be upgraded without executing
        verbose: Enable verbose logging

    Returns:
        UpgradeResult with upgrade outcome
    """
    from .config import load_config
    from .environment import detect_environment

    # Load config and environment
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    start_time = time.time()

    # 1. Validate tool is installed
    success, binary_path, current_version = validate_installation(tool_name, verbose=verbose)
    if not success or not current_version:
        return UpgradeResult(
            tool_name=tool_name,
            success=False,
            previous_version=None,
            new_version=None,
            backup=None,
            error_message=f"Tool '{tool_name}' is not currently installed",
            duration_seconds=time.time() - start_time,
        )

    vlog(f"Current version: {current_version}", verbose)

    # 2. Select package manager
    pm_name, reason = select_package_manager(
        tool_name=tool_name,
        language=None,
        config=config,
        env=env,
        verbose=verbose,
    )
    vlog(f"Using package manager: {pm_name}", verbose)

    # 3. Determine target version
    if target_version == "latest":
        cache_ttl = config.preferences.cache_ttl_seconds
        available_version = get_available_version(tool_name, pm_name, current_version, cache_ttl, verbose)
        if not available_version:
            return UpgradeResult(
                tool_name=tool_name,
                success=False,
                previous_version=current_version,
                new_version=None,
                backup=None,
                error_message="Could not determine latest version",
                duration_seconds=time.time() - start_time,
            )
        target_version = available_version

    vlog(f"Target version: {target_version}", verbose)

    # 4. Compare versions
    version_cmp = compare_versions(current_version, target_version)
    if version_cmp == 0:
        return UpgradeResult(
            tool_name=tool_name,
            success=True,
            previous_version=current_version,
            new_version=current_version,
            backup=None,
            error_message="Already at target version",
            duration_seconds=time.time() - start_time,
        )
    elif version_cmp > 0:
        return UpgradeResult(
            tool_name=tool_name,
            success=False,
            previous_version=current_version,
            new_version=None,
            backup=None,
            error_message=f"Downgrade not supported ({current_version} > {target_version})",
            duration_seconds=time.time() - start_time,
        )

    # 5. Check breaking change policy
    is_breaking = is_major_upgrade(current_version, target_version)
    if is_breaking:
        allowed, reason = check_breaking_change_policy(config, current_version, target_version)
        if not allowed and not force:
            return UpgradeResult(
                tool_name=tool_name,
                success=False,
                previous_version=current_version,
                new_version=None,
                backup=None,
                breaking_change=True,
                breaking_change_accepted=False,
                error_message=f"Breaking change blocked by policy: {reason}",
                duration_seconds=time.time() - start_time,
            )

        # Show warning for "warn" policy
        if reason == "breaking_warning" and not force and not dry_run:
            warning = format_breaking_change_warning(tool_name, current_version, target_version)
            if not confirm_breaking_change(warning):
                return UpgradeResult(
                    tool_name=tool_name,
                    success=False,
                    previous_version=current_version,
                    new_version=None,
                    backup=None,
                    breaking_change=True,
                    breaking_change_accepted=False,
                    error_message="User declined breaking change upgrade",
                    duration_seconds=time.time() - start_time,
                )

    if dry_run:
        return UpgradeResult(
            tool_name=tool_name,
            success=True,
            previous_version=current_version,
            new_version=target_version,
            backup=None,
            breaking_change=is_breaking,
            breaking_change_accepted=is_breaking,
            error_message="Dry-run mode",
            duration_seconds=time.time() - start_time,
        )

    # 6. Create backup
    backup = None
    if not skip_backup:
        try:
            backup = create_upgrade_backup(tool_name, binary_path or "", current_version or "", pm_name, verbose)
            vlog(f"Created backup: {backup.backup_path}", verbose)
        except Exception as e:
            vlog(f"Backup creation failed: {e}", verbose)
            # Continue without backup if not critical

    # 7. Execute upgrade
    try:
        install_result = install_tool(
            tool_name=tool_name,
            package_name=tool_name,
            target_version=target_version,
            config=config,
            env=env,
            dry_run=False,
            verbose=verbose,
        )

        if install_result.success:
            # Success
            duration = time.time() - start_time
            return UpgradeResult(
                tool_name=tool_name,
                success=True,
                previous_version=current_version,
                new_version=install_result.installed_version,
                backup=backup,
                breaking_change=is_breaking,
                breaking_change_accepted=is_breaking,
                install_result=install_result,
                duration_seconds=duration,
            )
        else:
            # Auto-rollback on failure
            vlog("Upgrade failed, attempting rollback...", verbose)
            rollback_success = False
            if backup:
                rollback_success = restore_from_backup(backup, verbose)
                vlog(f"Rollback {'succeeded' if rollback_success else 'failed'}", verbose)

            duration = time.time() - start_time
            return UpgradeResult(
                tool_name=tool_name,
                success=False,
                previous_version=current_version,
                new_version=None,
                backup=backup if not rollback_success else None,
                breaking_change=is_breaking,
                rollback_executed=True,
                rollback_success=rollback_success,
                error_message=install_result.error_message,
                duration_seconds=duration,
            )

    except Exception as e:
        # Unexpected error - attempt rollback
        vlog(f"Unexpected error: {e}", verbose)
        if backup:
            restore_from_backup(backup, verbose)
        raise


def get_upgrade_candidates(
    mode: str,
    tool_names: Sequence[str] | None,
    config: Config,
    env: Environment,
    verbose: bool = False,
) -> list[UpgradeCandidate]:
    """
    Get list of tools that can be upgraded based on mode.

    Args:
        mode: "all", "outdated", or "explicit"
        tool_names: Explicit tool names (for "explicit" mode)
        config: Configuration object
        env: Environment object
        verbose: Enable verbose logging

    Returns:
        List of upgrade candidates
    """
    candidates = []

    if mode == "explicit":
        if not tool_names:
            return []
        tools_to_check = list(tool_names)
    elif mode in ("all", "outdated"):
        tools_to_check = list(config.tools.keys())
    else:
        return []

    # Check each tool for upgrades
    cache_ttl = config.preferences.cache_ttl_seconds
    for tool in tools_to_check:
        # Check if installed
        success, _, current_version = validate_installation(tool, verbose=verbose)
        if not success or not current_version:
            vlog(f"{tool}: not installed, skipping", verbose)
            continue

        # Select package manager
        pm_name, _ = select_package_manager(tool, None, config, env, verbose=verbose)

        # Check for update
        upgrade_available, current, available = check_upgrade_available(tool, pm_name, cache_ttl, verbose)

        if upgrade_available and current and available:
            is_breaking = is_major_upgrade(current, available)
            candidates.append(UpgradeCandidate(
                tool_name=tool,
                current_version=current,
                available_version=available,
                breaking_change=is_breaking,
                package_manager=pm_name,
            ))
            vlog(f"{tool}: {current} → {available} {'(BREAKING)' if is_breaking else ''}", verbose)
        else:
            vlog(f"{tool}: up-to-date at {current}", verbose)

    return candidates


def bulk_upgrade(
    mode: str = "all",
    tool_names: Sequence[str] | None = None,
    config: Config | None = None,
    env: Environment | None = None,
    max_workers: int | None = None,
    force: bool = False,
    skip_backup: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> BulkUpgradeResult:
    """
    Upgrade multiple tools in parallel.

    Args:
        mode: "all", "outdated", or "explicit"
        tool_names: Explicit tool names (for "explicit" mode)
        config: Configuration object (loads defaults if None)
        env: Environment object (detects if None)
        max_workers: Maximum parallel workers (auto-detect if None)
        force: Skip all breaking change confirmations
        skip_backup: Don't create backups (faster but no rollback)
        dry_run: Show what would be upgraded without executing
        verbose: Enable verbose logging

    Returns:
        BulkUpgradeResult with upgrade outcomes
    """
    from .config import load_config
    from .environment import detect_environment

    # Load config/env
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    start_time = time.time()

    # 1. Determine candidates based on mode
    candidates = get_upgrade_candidates(mode, tool_names, config, env, verbose)

    if not candidates:
        return BulkUpgradeResult(
            tools_attempted=(),
            upgrades=(),
            skipped=(),
            failures=(),
            duration_seconds=time.time() - start_time,
            breaking_changes_count=0,
            rollbacks_executed=0,
        )

    # 2. Filter by breaking change policy
    allowed, blocked = filter_by_breaking_changes(candidates, config.preferences.breaking_changes)

    # 3. Prompt for breaking changes if needed
    if config.preferences.breaking_changes == "warn" and not force and not dry_run:
        if not confirm_bulk_breaking_changes(allowed):
            # User declined - block all breaking changes
            still_allowed = [c for c in allowed if not c.breaking_change]
            blocked.extend([c for c in allowed if c.breaking_change])
            allowed = still_allowed

    if dry_run:
        # Show what would be upgraded
        vlog(f"Dry-run: would upgrade {len(allowed)} tools", verbose)
        for candidate in allowed:
            vlog(f"  {candidate.tool_name}: {candidate.version_jump_description()}", verbose)
        for candidate in blocked:
            vlog(f"  {candidate.tool_name}: BLOCKED (breaking change)", verbose)

        return BulkUpgradeResult(
            tools_attempted=tuple(c.tool_name for c in allowed),
            upgrades=(),
            skipped=tuple(c.tool_name for c in blocked),
            failures=(),
            duration_seconds=time.time() - start_time,
            breaking_changes_count=len([c for c in candidates if c.breaking_change]),
            rollbacks_executed=0,
        )

    # 4. Execute upgrades in parallel
    upgrades: list[UpgradeResult] = []
    failures: list[UpgradeResult] = []

    # Determine max workers
    if max_workers is None:
        import os
        max_workers = min(16, os.cpu_count() or 4 + 4)

    vlog(f"Upgrading {len(allowed)} tools with {max_workers} workers...", verbose)

    # Use ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_candidate = {
            executor.submit(
                upgrade_tool,
                candidate.tool_name,
                candidate.available_version,
                config,
                env,
                force,
                skip_backup,
                False,  # not dry_run
                verbose,
            ): candidate
            for candidate in allowed
        }

        for future in as_completed(future_to_candidate):
            candidate = future_to_candidate[future]
            try:
                result = future.result()
                if result.success:
                    upgrades.append(result)
                    vlog(f"✓ {result.tool_name}: {result.previous_version} → {result.new_version}", verbose)
                else:
                    failures.append(result)
                    vlog(f"✗ {result.tool_name}: {result.error_message}", verbose)
            except Exception as e:
                vlog(f"Unexpected error upgrading {candidate.tool_name}: {e}", verbose)
                # Create failure result
                failures.append(UpgradeResult(
                    tool_name=candidate.tool_name,
                    success=False,
                    previous_version=candidate.current_version,
                    new_version=None,
                    backup=None,
                    error_message=str(e),
                ))

    duration = time.time() - start_time

    return BulkUpgradeResult(
        tools_attempted=tuple(c.tool_name for c in allowed),
        upgrades=tuple(upgrades),
        skipped=tuple(c.tool_name for c in blocked),
        failures=tuple(failures),
        duration_seconds=duration,
        breaking_changes_count=len([c for c in candidates if c.breaking_change]),
        rollbacks_executed=sum(1 for r in failures if r.rollback_executed),
    )
