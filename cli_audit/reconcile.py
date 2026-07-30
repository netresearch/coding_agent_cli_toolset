"""
Reconciliation of multiple tool installations.

Detects and manages situations where the same tool is installed via multiple
package managers (e.g., both apt and cargo). Provides parallel (safe, keep all)
and aggressive (remove non-preferred) reconciliation modes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from functools import cmp_to_key
from itertools import groupby
from typing import Sequence

from .common import vlog
from .config import Config
from .environment import Environment
from .upgrade import compare_versions

# Installation detection cache with TTL
_detection_cache: dict[str, tuple[list[Installation], float]] = {}
CACHE_TTL = 3600  # 1 hour


# Critical system tools that should never be removed
SYSTEM_TOOL_SAFELIST = {
    "python",
    "python3",
    "bash",
    "sh",
    "sudo",
    "rm",
    "cp",
    "mv",
    "ls",
    "cat",
    "chmod",
    "chown",
    "grep",
    "sed",
    "awk",
    "tar",
    "gzip",
    "gunzip",
    "find",
    "xargs",
    "ps",
    "kill",
    "systemctl",
    "apt",
    "dnf",
    "yum",
    "pacman",
}


@dataclass(frozen=True)
class Installation:
    """
    Single installation of a tool.

    Attributes:
        tool: Tool name
        version: Installed version
        method: Installation method (cargo, pipx, apt, brew, etc.)
        path: Full path to binary
        active: Whether this is the active installation (via which())
        valid: Whether the installation can be executed successfully
        preference_score: Tuple for sorting (tier, version, -path_index)
    """

    tool: str
    version: str
    method: str
    path: str
    active: bool
    valid: bool = True
    preference_score: tuple[int, str, int] = (0, "0.0.0", 0)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool": self.tool,
            "version": self.version,
            "method": self.method,
            "path": self.path,
            "active": self.active,
            "valid": self.valid,
        }


@dataclass(frozen=True)
class ReconciliationResult:
    """
    Result of reconciling a single tool.

    Attributes:
        tool: Tool name
        installations: All detected installations
        preferred: Preferred installation (highest priority)
        active: Currently active installation (via which())
        path_issues: List of PATH ordering issues
        action_taken: Action performed ("none", "path_guidance", "removed")
        removed_installations: Installations that were removed (aggressive mode)
        success: Whether reconciliation succeeded
        error_message: Error message if failed
    """

    tool: str
    installations: tuple[Installation, ...]
    preferred: Installation | None
    active: Installation | None
    path_issues: tuple[str, ...]
    action_taken: str = "none"
    removed_installations: tuple[Installation, ...] = ()
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool": self.tool,
            "installations": [i.to_dict() for i in self.installations],
            "preferred": self.preferred.to_dict() if self.preferred else None,
            "active": self.active.to_dict() if self.active else None,
            "path_issues": list(self.path_issues),
            "action_taken": self.action_taken,
            "removed_installations": [i.to_dict() for i in self.removed_installations],
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class BulkReconciliationResult:
    """
    Result of bulk reconciliation operation.

    Attributes:
        tools_checked: Number of tools checked
        conflicts_found: Number of tools with multiple installations
        conflicts_resolved: Number of conflicts successfully resolved
        results: Individual reconciliation results
        duration_seconds: Total execution time
    """

    tools_checked: int
    conflicts_found: int
    conflicts_resolved: int
    results: tuple[ReconciliationResult, ...]
    duration_seconds: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tools_checked": self.tools_checked,
            "conflicts_found": self.conflicts_found,
            "conflicts_resolved": self.conflicts_resolved,
            "results": [r.to_dict() for r in self.results],
            "duration_seconds": self.duration_seconds,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        manual = sum(1 for r in self.results if r.action_taken == "manual_required")
        manual_line = f"\n  Manual action required: {manual}" if manual else ""
        return f"""
Reconciliation Summary:
  Checked: {self.tools_checked} tools
  Conflicts found: {self.conflicts_found}
  Conflicts resolved: {self.conflicts_resolved}{manual_line}
  Duration: {self.duration_seconds:.1f}s
"""


# Environment-name patterns for env managers without a pyvenv.cfg (conda etc.).
# Mirrors the venv skip list in scripts/lib/capability.sh:detect_all_installations.
_ENV_DIR_PATTERNS = (
    "/venv/bin",
    "/.venv/bin",
    "/env/bin",
    "/venvs/",
    "/.venvs/",
    "/virtualenvs/",
    "/.virtualenvs/",
    "/envs/",
    "/conda/",
    "/miniconda",
    "/anaconda",
)


def _is_virtualenv_bin(bin_dir: str) -> bool:
    """True if bin_dir is a virtualenv/conda environment's bin directory.

    Environments are not installations: their binaries vanish with the env,
    and classifying them by method (e.g. `uv` because the tool also appears
    in `uv tool list`) makes removal delete a DIFFERENT installation.
    """
    # Definitive signal: PEP 405 venvs carry pyvenv.cfg next to bin/
    if os.path.isfile(os.path.join(os.path.dirname(bin_dir), "pyvenv.cfg")):
        return True
    # Name-based fallback for conda/virtualenvwrapper layouts
    normalized = bin_dir.rstrip("/") + "/"
    return any(pat in normalized for pat in _ENV_DIR_PATTERNS)


def detect_installations(
    tool_name: str,
    candidates: Sequence[str] | None = None,
    verbose: bool = False,
) -> list[Installation]:
    """
    Detect all installations of a tool across PATH.

    Args:
        tool_name: Name of the tool
        candidates: List of executable names to search for
        verbose: Enable verbose logging

    Returns:
        List of Installation objects, sorted by preference
    """
    import time

    # Check cache
    cache_key = tool_name
    if cache_key in _detection_cache:
        cached_installs, cached_time = _detection_cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            vlog(f"Using cached installations for {tool_name}", verbose)
            return cached_installs

    vlog(f"Detecting installations of {tool_name}...", verbose)

    if candidates is None:
        candidates = [tool_name]

    installations = []
    seen_paths = set()

    # Get PATH directories
    path_env = os.environ.get("PATH", "")
    path_dirs = [d for d in path_env.split(os.pathsep) if d]

    # Search each PATH directory
    for path_dir in path_dirs:
        # Virtualenv/conda bins are environments, not installations
        if _is_virtualenv_bin(path_dir):
            vlog(f"  Skipping environment dir: {path_dir}", verbose)
            continue
        for candidate in candidates:
            full_path = os.path.join(path_dir, candidate)

            # Skip if already seen (e.g., symlink to same binary)
            if full_path in seen_paths:
                continue

            # Check if exists and executable
            if not os.path.exists(full_path):
                continue

            if not os.access(full_path, os.X_OK):
                continue

            # Resolve symlinks to get real path
            real_path = os.path.realpath(full_path)
            if real_path in seen_paths:
                continue

            # A symlink can point into an environment as well
            if _is_virtualenv_bin(os.path.dirname(real_path)):
                vlog(f"  Skipping environment binary: {real_path}", verbose)
                continue

            seen_paths.add(real_path)

            # Get THIS install's own version by running its actual binary path.
            # validate_installation(tool_name) only ever runs the PATH-active
            # binary, so it would report the same version for every duplicate.
            # version_command is deliberately omitted (it runs the tool by name,
            # i.e. the active binary) to force path-based detection.
            version = None
            valid = True
            try:
                from .collectors import extract_version_number
                from .detection import get_version_line

                meta = _catalog_meta(tool_name)
                line = get_version_line(real_path, tool_name, meta.get("version_flag"), None)
                if line:
                    version = extract_version_number(line) or line.strip()
                else:
                    valid = False
            except Exception:
                valid = False

            if not version:
                version = "unknown"

            # Classify installation method
            method = classify_install_method(real_path, tool_name, verbose)

            # Check if this is the active installation
            active_path = shutil.which(candidate)
            is_active = (os.path.realpath(active_path) == real_path) if active_path else False

            installations.append(
                Installation(
                    tool=tool_name,
                    version=version,
                    method=method,
                    path=real_path,
                    active=is_active,
                    valid=valid,
                )
            )

            vlog(f"  Found: {real_path} ({method}, {version})", verbose)

    # Sort by preference (highest first) so installations[0] is the preferred
    # install — callers and the guide's "keep" marker rely on this ordering.
    installations = sort_by_preference(installations)

    # Cache results
    _detection_cache[cache_key] = (installations, time.time())

    return installations


def classify_install_method(
    path: str,
    tool_name: str,
    verbose: bool = False,
) -> str:
    """
    Classify installation method using multi-signal approach.

    Priority:
    1. Package manager queries (most accurate)
    2. Path-based heuristics (fallback)

    Args:
        path: Full path to binary
        tool_name: Name of the tool
        verbose: Enable verbose logging

    Returns:
        Installation method string (cargo, pipx, apt, brew, etc.)
    """
    # Try package manager queries first
    method = _classify_via_queries(path, tool_name, verbose)
    if method != "unknown":
        return method

    # Fallback to path-based heuristics
    return _classify_via_path(path)


# Any of these characters in a path means it is not a plain absolute binary
# path and must never be forwarded to a package-manager OS command.
_UNSAFE_PATH_CHARS = re.compile(r"[\s;&|`$(){}<>*?!\"'\\]")


def _is_safe_binary_path(path: str) -> bool:
    """Validate a resolved binary path before passing it to OS commands.

    Detected paths are os.path.realpath() of executables on PATH, so they are
    always absolute and free of shell metacharacters — but validate explicitly
    so untrusted-looking data never reaches a package-manager query.
    """
    return bool(path) and path.startswith("/") and not _UNSAFE_PATH_CHARS.search(path)


def _classify_via_queries(path: str, tool_name: str, verbose: bool) -> str:
    """Classify via package manager queries."""
    # Validate the path before any package-manager OS command: it must be a
    # plain absolute path with no shell metacharacters.
    if not _is_safe_binary_path(path):
        return _classify_via_path(path)

    # dpkg (Debian/Ubuntu)
    if shutil.which("dpkg"):
        try:
            result = subprocess.run(
                ["dpkg", "-S", path],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                vlog("  Classified as apt via dpkg query", verbose)
                return "apt"
        except Exception:
            pass

    # rpm (Fedora/RHEL)
    if shutil.which("rpm"):
        try:
            result = subprocess.run(
                ["rpm", "-qf", path],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                vlog("  Classified as dnf/rpm via rpm query", verbose)
                return "dnf"
        except Exception:
            pass

    # brew
    if shutil.which("brew"):
        try:
            result = subprocess.run(
                ["brew", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and tool_name in result.stdout:
                # Verify this tool is from brew
                formula_result = subprocess.run(
                    ["brew", "list", tool_name],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if formula_result.returncode == 0 and path in formula_result.stdout:
                    vlog("  Classified as brew via brew list", verbose)
                    return "brew"
        except Exception:
            pass

    # cargo
    if shutil.which("cargo"):
        try:
            result = subprocess.run(
                ["cargo", "install", "--list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and tool_name in result.stdout:
                vlog("  Classified as cargo via cargo install --list", verbose)
                return "cargo"
        except Exception:
            pass

    # pipx
    if shutil.which("pipx"):
        try:
            result = subprocess.run(
                ["pipx", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and tool_name in result.stdout:
                vlog("  Classified as pipx via pipx list", verbose)
                return "pipx"
        except Exception:
            pass

    # uv tool
    if shutil.which("uv"):
        try:
            result = subprocess.run(
                ["uv", "tool", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and tool_name in result.stdout:
                vlog("  Classified as uv via uv tool list", verbose)
                return "uv"
        except Exception:
            pass

    return "unknown"


def _classify_via_path(path: str) -> str:
    """Classify via path-based heuristics."""
    # User-level installations
    if "/.cargo/bin" in path:
        return "cargo"
    elif "/.local/bin" in path:
        # Could be pip --user, pipx, or uv
        # Default to pipx as most common
        return "pipx"
    elif "/.uv/bin" in path or "/uv-python" in path:
        return "uv"
    elif "/.nvm/" in path:
        return "nvm"
    elif "/.pyenv/" in path:
        return "pyenv"
    elif "/.rbenv/" in path:
        return "rbenv"
    elif "/go/bin" in path:
        # GOPATH bin (`go install` target); must precede the generic '/bin'
        # fallback or user-owned binaries get labeled 'system'.
        return "go"

    # System-level installations (check specific patterns before generic ones)
    elif "/snap/bin" in path:
        return "snap"
    elif "/opt/homebrew" in path:
        # Without brew installed these are manual installs (curl'd binaries);
        # labeling them 'brew' makes removal run a nonexistent `brew uninstall`.
        return "brew" if shutil.which("brew") else "manual"
    elif "/usr/local/bin" in path or "/usr/local/sbin" in path:
        return "brew" if shutil.which("brew") else "manual"
    elif "/usr/bin" in path or "/usr/sbin" in path:
        return "apt"  # Generic system PM
    elif "/bin" in path or "/sbin" in path:
        return "system"

    return "unknown"


def clear_detection_cache():
    """Clear the installation detection cache."""
    _detection_cache.clear()


def sort_by_preference(
    installations: Sequence[Installation],
    config: Config | None = None,
    verbose: bool = False,
) -> list[Installation]:
    """
    Sort installations by preference (highest to lowest).

    Preference hierarchy:
    1. User-level vendor tools (uv, pipx, rustup, nvm) - Tier 1
    2. User-level generic (cargo, pip --user, npm user) - Tier 2
    3. Homebrew - Tier 3
    4. System package managers (apt, dnf, pacman) - Tier 4

    Tiebreaker rules:
    - Same tier → prefer newer version
    - Same version → prefer first in PATH
    - Identical → prefer shorter path

    Args:
        installations: List of installations to sort
        config: Configuration for preference overrides
        verbose: Enable verbose logging

    Returns:
        Sorted list (highest preference first)
    """

    def get_preference_tier(installation: Installation) -> int:
        """Get preference tier (lower number = higher preference)."""
        method = installation.method

        # Tier 1: User-level vendor tools (highest priority)
        if method in ("uv", "pipx", "rustup", "nvm", "pyenv", "rbenv"):
            return 1

        # Tier 2: User-level generic
        if method in ("cargo", "pip", "npm", "go"):
            return 2
        if "/.cargo/" in installation.path or "/.local/" in installation.path:
            return 2

        # Tier 3: Homebrew
        if method == "brew":
            return 3

        # Tier 4: System package managers (lowest priority)
        if method in ("apt", "dnf", "yum", "pacman", "zypper", "snap", "system"):
            return 4

        # Unknown: treat as Tier 5
        return 5

    # Score each installation
    scored = []
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    for installation in installations:
        tier = get_preference_tier(installation)

        # Get version for comparison (use as-is, we'll compare semantically)
        version = installation.version

        # Get PATH index (earlier in PATH = higher priority)
        path_idx = 9999
        for idx, path_dir in enumerate(path_dirs):
            if installation.path.startswith(path_dir):
                path_idx = idx
                break

        scored.append((tier, installation, version, path_idx))

    # Sort by tier first
    scored.sort(key=lambda x: x[0])

    # Within same tier, sort by version (descending) using semantic version comparison
    # Group by tier
    result = []
    for tier_key, group_items in groupby(scored, key=lambda x: x[0]):
        items = list(group_items)
        # Sort by version descending using compare_versions
        # compare_versions returns: <0 if v1 < v2, 0 if equal, >0 if v1 > v2
        # We want descending (newer first), so negate the comparison
        items.sort(key=cmp_to_key(lambda a, b: -compare_versions(a[2], b[2])))  # type: ignore[index]
        result.extend(items)

    # Extract sorted installations
    sorted_installs = [inst for _, inst, _, _ in result]

    if verbose and len(sorted_installs) > 1:
        vlog("Sorted installations by preference:", verbose)
        for idx, inst in enumerate(sorted_installs, 1):
            tier = get_preference_tier(inst)
            vlog(f"  [{idx}] Tier {tier}: {inst.method} - {inst.path}", verbose)

    return sorted_installs


_catalog_cache: dict[str, dict] = {}
_catalog_instance = None
_catalog_lock = threading.Lock()


def _catalog_meta(tool_name: str) -> dict:
    """Return cached catalog metadata for a tool: candidates + version command.

    Thread-safe (bulk_reconcile detects tools in a ThreadPool). Returns an empty
    dict for unknown tools so callers fall back to sane defaults.
    """
    global _catalog_instance
    with _catalog_lock:
        if tool_name in _catalog_cache:
            return _catalog_cache[tool_name]
        meta: dict = {}
        try:
            inst = _catalog_instance
            if inst is None:
                from .catalog import ToolCatalog

                inst = ToolCatalog()
                # Only cache a catalog that actually loaded, so a transiently
                # empty/unavailable filesystem doesn't poison later calls.
                if inst.all_tools():
                    _catalog_instance = inst
            entry = inst.get(tool_name)
            if entry:
                meta["candidates"] = tuple(entry.to_tool().candidates)
                raw = getattr(entry, "_raw_data", None) or {}
                meta["version_flag"] = raw.get("version_flag")
                meta["version_command"] = raw.get("version_command")
        except Exception:
            meta = {}
        # Only cache successful lookups — an empty result may be transient.
        if meta:
            _catalog_cache[tool_name] = meta
        return meta


def _resolve_candidates(tool_name: str) -> tuple[str, ...] | None:
    """Look up catalog candidates for a tool (cached).

    Lets reconcile detect alternate-named duplicates (e.g. ``pip``/``pip3``,
    ``fd``/``fdfind``) even when a caller (such as bulk_reconcile) does not pass
    candidates. Returns None if the tool is unknown, so detection falls back to
    the bare tool name.
    """
    return _catalog_meta(tool_name).get("candidates")


def reconcile_tool(
    tool_name: str,
    mode: str = "parallel",
    candidates: Sequence[str] | None = None,
    config: Config | None = None,
    env: Environment | None = None,
    force: bool = False,
    verbose: bool = False,
) -> ReconciliationResult:
    """
    Reconcile installations of a single tool.

    Args:
        tool_name: Name of the tool to reconcile
        mode: "parallel" (keep all) or "aggressive" (remove non-preferred)
        candidates: List of executable names to search for
        config: Configuration object
        env: Environment object
        force: Skip confirmation prompts
        verbose: Enable verbose logging

    Returns:
        ReconciliationResult with outcome
    """
    from .config import load_config
    from .environment import detect_environment

    # Load config and environment
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    # Resolve catalog candidates when a caller (e.g. bulk_reconcile) omits them,
    # so alternate-named duplicates (pip/pip3, fd/fdfind) are still detected.
    if candidates is None:
        candidates = _resolve_candidates(tool_name)

    # Detect installations
    installations = detect_installations(tool_name, candidates, verbose)

    if not installations:
        return ReconciliationResult(
            tool=tool_name,
            installations=(),
            preferred=None,
            active=None,
            path_issues=(),
            action_taken="none",
            success=False,
            error_message="No installations found",
        )

    # Single installation - no reconciliation needed
    if len(installations) == 1:
        inst = installations[0]
        return ReconciliationResult(
            tool=tool_name,
            installations=(inst,),
            preferred=inst,
            active=inst if inst.active else None,
            path_issues=(),
            action_taken="none",
            success=True,
        )

    # Multiple installations - need reconciliation
    sorted_installs = sort_by_preference(installations, config, verbose)
    preferred = sorted_installs[0]
    active = next((i for i in sorted_installs if i.active), None)

    # Verify PATH ordering
    path_issues = _check_path_ordering(preferred, active, verbose)

    # Execute reconciliation based on mode
    if mode == "aggressive":
        return _reconcile_aggressive(tool_name, sorted_installs, preferred, active, path_issues, force, verbose)
    else:  # parallel (default)
        return _reconcile_parallel(tool_name, sorted_installs, preferred, active, path_issues, verbose)


def _reconcile_parallel(
    tool_name: str,
    installations: list[Installation],
    preferred: Installation,
    active: Installation | None,
    path_issues: tuple[str, ...],
    verbose: bool,
) -> ReconciliationResult:
    """
    Parallel reconciliation: keep all, verify PATH ordering.

    Non-destructive mode that guides user to fix PATH if needed.
    """
    vlog(f"\nReconciling {tool_name} (parallel mode):", verbose)
    vlog(f"  Found {len(installations)} installations", verbose)

    # Display installations
    if verbose:
        for idx, inst in enumerate(installations, 1):
            active_marker = "[ACTIVE]" if inst.active else ""
            preferred_marker = "[PREFERRED]" if inst == preferred else ""
            vlog(f"  [{idx}] {inst.version} ({inst.method}, {inst.path}) {active_marker} {preferred_marker}", verbose)

    # Check if preferred is active
    action = "none"
    if preferred.active:
        vlog("  ✓ PATH ordering ensures preferred is active", verbose)
        action = "none"
    else:
        vlog("  ⚠️  PATH ordering issue: preferred is not active", verbose)
        if path_issues:
            for issue in path_issues:
                vlog(f"    {issue}", verbose)
        action = "path_guidance"

    return ReconciliationResult(
        tool=tool_name,
        installations=tuple(installations),
        preferred=preferred,
        active=active,
        path_issues=path_issues,
        action_taken=action,
        success=True,
    )


def _reconcile_aggressive(
    tool_name: str,
    installations: list[Installation],
    preferred: Installation,
    active: Installation | None,
    path_issues: tuple[str, ...],
    force: bool,
    verbose: bool,
) -> ReconciliationResult:
    """
    Aggressive reconciliation: remove non-preferred installations.

    Requires confirmation and checks system tool safelist.
    """
    vlog(f"\nReconciling {tool_name} (aggressive mode):", verbose)

    # Check safelist
    if tool_name in SYSTEM_TOOL_SAFELIST:
        return ReconciliationResult(
            tool=tool_name,
            installations=tuple(installations),
            preferred=preferred,
            active=active,
            path_issues=path_issues,
            action_taken="blocked",
            success=False,
            error_message=f"Tool '{tool_name}' is on system safelist and cannot be removed",
        )

    # Identify installations to remove
    to_remove = [inst for inst in installations if inst != preferred]

    if not to_remove:
        return _reconcile_parallel(tool_name, installations, preferred, active, path_issues, verbose)

    # Display removal plan
    vlog(f"  ⚠️  Will remove {len(to_remove)} installation(s):", verbose)
    for inst in to_remove:
        vlog(f"    - {inst.version} ({inst.method}, {inst.path})", verbose)
    vlog(f"  Keeping: {preferred.version} ({preferred.method}, {preferred.path})", verbose)

    # Require confirmation
    if not force:
        if not _confirm_removal(tool_name, to_remove):
            vlog("  Aborted by user", verbose)
            return ReconciliationResult(
                tool=tool_name,
                installations=tuple(installations),
                preferred=preferred,
                active=active,
                path_issues=path_issues,
                action_taken="aborted",
                success=False,
                error_message="User declined removal",
            )

    # Remove installations
    removed = []
    errors = []

    for inst in to_remove:
        try:
            success, error = _uninstall_installation(inst, verbose)
            if success:
                removed.append(inst)
                vlog(f"  ✓ Removed {inst.path}", verbose)
            else:
                errors.append(f"Failed to remove {inst.path}: {error}")
                vlog(f"  ✗ {error}", verbose)
        except Exception as e:
            errors.append(f"Error removing {inst.path}: {str(e)}")
            vlog(f"  ✗ Error: {e}", verbose)

    # Determine success
    # Verify the kept installation still works: a survivor can be a wrapper
    # script depending on files the removed package owned (byobu's launcher
    # sources /usr/lib/byobu), in which case the removal silently broke it.
    if removed:
        try:
            from .detection import get_version_line

            meta = _catalog_meta(tool_name)
            probe = get_version_line(preferred.path, tool_name, meta.get("version_flag"), None)
        except Exception:
            probe = None
        if not probe:
            errors.append(
                f"kept installation {preferred.path} no longer works after removal — "
                f"reinstall the removed package (e.g. sudo {removed[0].method} install {tool_name}) "
                f"or remove the broken survivor"
            )

    success = len(removed) == len(to_remove) and not errors
    error_msg = "; ".join(errors) if errors else None
    # Failures that only need a manual sudo command are the designed outcome
    # (this tool never runs sudo itself), not errors — callers exit 0 on them.
    action = "manual_required" if errors and all(_is_manual_removal_error(e) for e in errors) else "removed"

    return ReconciliationResult(
        tool=tool_name,
        installations=tuple(installations),
        preferred=preferred,
        active=active,
        path_issues=path_issues,
        action_taken=action,
        removed_installations=tuple(removed),
        success=success,
        error_message=error_msg,
    )


def _check_path_ordering(
    preferred: Installation,
    active: Installation | None,
    verbose: bool,
) -> tuple[str, ...]:
    """Check if PATH ordering is correct."""
    issues = []

    if not active:
        issues.append("No active installation found (tool not in PATH)")
        return tuple(issues)

    if preferred.path != active.path:
        issues.append(
            f"Preferred installation is not active\n"
            f"  Preferred: {preferred.path}\n"
            f"  Active:    {active.path}\n"
            f"  Fix: Ensure {os.path.dirname(preferred.path)} appears first in PATH"
        )

    return tuple(issues)


# Serializes prompt output; prompts themselves run on the main thread only
# (a worker blocked in input() hangs Python's atexit thread-join on Ctrl-C).
_prompt_lock = threading.Lock()

# Sticky answers for a bulk prompt run: 'a' confirms all remaining prompts,
# 'q' (or Ctrl-C / EOF) declines all remaining ones.
_bulk_prompt_state = {"all": False, "quit": False}


def _reset_bulk_prompt_state() -> None:
    """Reset the sticky all/quit prompt answers (start of each bulk run)."""
    _bulk_prompt_state["all"] = False
    _bulk_prompt_state["quit"] = False


def _confirm_removal(tool_name: str, to_remove: list[Installation]) -> bool:
    """Prompt user to confirm removal. Supports y/n/a(ll)/q(uit); Ctrl-C = quit."""
    if not sys.stdin.isatty():
        # Non-interactive mode
        return False

    with _prompt_lock:
        if _bulk_prompt_state["quit"]:
            return False
        if _bulk_prompt_state["all"]:
            return True

        print(f"\n⚠️  WARNING: About to remove {len(to_remove)} installation(s) of {tool_name}")
        for inst in to_remove:
            print(f"  - {inst.version} ({inst.method}, {inst.path})")

        print("\nProceed with removal? [y/N/a=all/q=quit]: ", end="")
        try:
            response = input().strip().lower()
        except KeyboardInterrupt, EOFError:
            print()
            _bulk_prompt_state["quit"] = True
            return False
        if response in ("a", "all"):
            _bulk_prompt_state["all"] = True
            return True
        if response in ("q", "quit"):
            _bulk_prompt_state["quit"] = True
            return False
        return response in ("y", "yes")


# Failure messages that only require a manual sudo command — an expected
# limitation (this tool never runs sudo itself), not an error.
_MANUAL_REMOVAL_MARKERS = (
    "System package removal requires manual sudo:",
    "Permission denied — remove manually:",
    "Unmanaged system binary — remove manually:",
)


def _is_manual_removal_error(message: str | None) -> bool:
    """True if a removal failure only needs the user to run a sudo command."""
    return bool(message) and any(marker in message for marker in _MANUAL_REMOVAL_MARKERS)


def _cargo_package_for(binary: str, tool: str) -> str:
    """Map an installed binary to its owning cargo package.

    `cargo uninstall` needs the crate name, which can differ from the binary
    (git-delta installs `delta`, watchexec-cli installs `watchexec`). Parses
    `cargo install --list`; falls back to the tool name.
    """
    try:
        result = subprocess.run(
            ["cargo", "install", "--list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return tool
        package = None
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                package = line.split()[0]
            elif package and line.strip() in (binary, tool):
                return package
    except Exception:
        pass
    return tool


def _uninstall_installation(installation: Installation, verbose: bool) -> tuple[bool, str | None]:
    """
    Uninstall a single installation.

    Returns:
        (success, error_message)
    """
    method = installation.method
    tool = installation.tool
    path = installation.path

    vlog(f"  Uninstalling {tool} via {method}...", verbose)

    # Cargo
    if method == "cargo":
        try:
            result = subprocess.run(
                ["cargo", "uninstall", _cargo_package_for(os.path.basename(path), tool)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return (True, None)
            else:
                return (False, result.stderr or "cargo uninstall failed")
        except Exception as e:
            return (False, str(e))

    # Pipx
    elif method == "pipx":
        try:
            result = subprocess.run(
                ["pipx", "uninstall", tool],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return (True, None)
            else:
                return (False, result.stderr or "pipx uninstall failed")
        except Exception as e:
            return (False, str(e))

    # UV
    elif method == "uv":
        try:
            result = subprocess.run(
                ["uv", "tool", "uninstall", tool],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return (True, None)
            else:
                return (False, result.stderr or "uv tool uninstall failed")
        except Exception as e:
            return (False, str(e))

    # Brew
    elif method == "brew":
        try:
            result = subprocess.run(
                ["brew", "uninstall", tool],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return (True, None)
            else:
                return (False, result.stderr or "brew uninstall failed")
        except Exception as e:
            return (False, str(e))

    # System package managers (require sudo - don't auto-execute)
    elif method in ("apt", "dnf", "pacman"):
        return (False, f"System package removal requires manual sudo: sudo {method} remove {tool}")

    # Unmanaged system-location binary — no package manager to invoke
    elif method == "system":
        return (False, f"Unmanaged system binary — remove manually: sudo rm {path}")

    # Manual removal (GitHub releases, `go install` binaries, etc.)
    elif method in ("unknown", "manual", "go"):
        try:
            if os.path.exists(path):
                os.remove(path)
                return (True, None)
            else:
                return (False, "Binary not found")
        except PermissionError:
            return (False, f"Permission denied — remove manually: sudo rm {path}")
        except Exception as e:
            return (False, str(e))

    else:
        return (False, f"Unknown uninstall method for {method}")


def bulk_reconcile(
    mode: str = "all",
    tool_names: Sequence[str] | None = None,
    reconcile_mode: str = "parallel",
    config: Config | None = None,
    env: Environment | None = None,
    max_workers: int | None = None,
    force: bool = False,
    verbose: bool = False,
) -> BulkReconciliationResult:
    """
    Reconcile multiple tools in parallel.

    Args:
        mode: "all" (all installed), "conflicts" (only conflicts), or "explicit"
        tool_names: Explicit tool names (for "explicit" mode)
        reconcile_mode: "parallel" or "aggressive"
        config: Configuration object
        env: Environment object
        max_workers: Maximum parallel workers
        force: Skip confirmation prompts
        verbose: Enable verbose logging

    Returns:
        BulkReconciliationResult with outcomes
    """
    import time

    from .config import load_config
    from .environment import detect_environment

    # Load config/env
    if config is None:
        config = load_config(verbose=verbose)
    if env is None:
        env = detect_environment(verbose=verbose)

    start_time = time.time()

    # Determine tools to check
    if mode == "explicit":
        if not tool_names:
            return BulkReconciliationResult(
                tools_checked=0,
                conflicts_found=0,
                conflicts_resolved=0,
                results=(),
                duration_seconds=time.time() - start_time,
            )
        tools_to_check = list(tool_names)
    elif mode in ("all", "conflicts"):
        # Get all tools from config
        tools_to_check = list(config.tools.keys()) if config.tools else []
    else:
        return BulkReconciliationResult(
            tools_checked=0,
            conflicts_found=0,
            conflicts_resolved=0,
            results=(),
            duration_seconds=time.time() - start_time,
        )

    # Detect installations in parallel
    if max_workers is None:
        max_workers = min(16, os.cpu_count() or 4 + 4)

    vlog(f"Checking {len(tools_to_check)} tools for conflicts...", verbose)

    _reset_bulk_prompt_state()
    results = []

    # Phase 1 — parallel DETECTION only. Workers must never prompt: input()
    # in a worker survives Ctrl-C in the main thread and then deadlocks
    # Python's atexit thread-join.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tool = {
            executor.submit(
                reconcile_tool,
                tool,
                "parallel",
                None,
                config,
                env,
                force,
                verbose,
            ): tool
            for tool in tools_to_check
        }

        try:
            for future in as_completed(future_to_tool):
                tool = future_to_tool[future]
                try:
                    result = future.result()
                    results.append(result)
                    if verbose:
                        status = "✓" if result.success else "✗"
                        vlog(f"{status} {tool}: {len(result.installations)} installation(s)", verbose)
                except Exception as e:
                    vlog(f"✗ {tool}: Error - {e}", verbose)
                    results.append(
                        ReconciliationResult(
                            tool=tool,
                            installations=(),
                            preferred=None,
                            active=None,
                            path_issues=(),
                            action_taken="error",
                            success=False,
                            error_message=str(e),
                        )
                    )
        except KeyboardInterrupt:
            # Abort: skip everything not yet detected; workers finish their
            # bounded probes (no stdin involved), so shutdown cannot hang.
            _bulk_prompt_state["quit"] = True
            for f in future_to_tool:
                f.cancel()

    # Phase 2 — aggressive resolution on the MAIN thread (prompts + removal).
    if reconcile_mode == "aggressive":
        finalized = []
        for r in results:
            if len(r.installations) <= 1 or r.preferred is None:
                finalized.append(r)
                continue
            if _bulk_prompt_state["quit"]:
                finalized.append(replace(r, action_taken="aborted", success=False, error_message="Skipped (quit)"))
                continue
            try:
                finalized.append(
                    _reconcile_aggressive(r.tool, list(r.installations), r.preferred, r.active, r.path_issues, force, verbose)
                )
            except KeyboardInterrupt:
                _bulk_prompt_state["quit"] = True
                finalized.append(replace(r, action_taken="aborted", success=False, error_message="Skipped (quit)"))
        results = finalized

    # Filter by mode
    if mode == "conflicts":
        results = [r for r in results if len(r.installations) > 1]

    duration = time.time() - start_time

    # Calculate statistics
    tools_checked = len(results)
    conflicts_found = sum(1 for r in results if len(r.installations) > 1)
    conflicts_resolved = sum(1 for r in results if len(r.installations) > 1 and r.success and r.action_taken != "none")

    return BulkReconciliationResult(
        tools_checked=tools_checked,
        conflicts_found=conflicts_found,
        conflicts_resolved=conflicts_resolved,
        results=tuple(results),
        duration_seconds=duration,
    )


def verify_path_ordering(config: Config | None = None, verbose: bool = False) -> list[str]:
    """
    Verify PATH ordering ensures user bins appear before system bins.

    Args:
        config: Configuration object
        verbose: Enable verbose logging

    Returns:
        List of PATH ordering issues found
    """
    issues = []

    # User bin directories (should come first)
    user_bins = [
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.cargo/bin"),
        os.path.expanduser("~/.uv/bin"),
        os.path.expanduser("~/.pyenv/bin"),
        os.path.expanduser("~/.rbenv/bin"),
    ]

    # System bin directories (should come later)
    system_bins = ["/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]

    # Get PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    # Check each user bin that exists
    for user_bin in user_bins:
        if not os.path.exists(user_bin):
            continue

        if user_bin not in path_dirs:
            issues.append(
                f"Missing from PATH: {user_bin}\n"
                f"  Fix: Add to ~/.bashrc or ~/.zshrc:\n"
                f'    export PATH="{user_bin}:$PATH"'
            )
            continue

        user_idx = path_dirs.index(user_bin)

        # Check if any system bin comes before this user bin
        for sys_bin in system_bins:
            if sys_bin not in path_dirs:
                continue

            sys_idx = path_dirs.index(sys_bin)

            if sys_idx < user_idx:
                # BAD: system bin before user bin
                issues.append(
                    f"PATH ordering issue: {sys_bin} appears before {user_bin}\n"
                    f"  Current PATH index: {sys_bin}={sys_idx}, {user_bin}={user_idx}\n"
                    f"  Fix: Add to ~/.bashrc or ~/.zshrc:\n"
                    f'    export PATH="{user_bin}:$PATH"'
                )

    if verbose:
        if issues:
            vlog(f"Found {len(issues)} PATH ordering issue(s):", verbose)
            for issue in issues:
                vlog(f"  {issue}", verbose)
        else:
            vlog("PATH ordering is correct", verbose)

    return issues
