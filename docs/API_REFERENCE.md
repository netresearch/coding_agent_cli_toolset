# API Reference - v2.0 Modular Architecture

**Version:** 2.0.0
**Last Updated:** 2025-11-06
**Architecture:** 18 specialized Python modules with 100+ public APIs

---

## Overview

This document provides comprehensive API reference for the v2.0 modular architecture of AI CLI Preparation. The codebase has evolved from a 3,387-line monolith into 18 specialized modules with clean separation of concerns.

**Module Organization:**
- **Detection & Auditing**: Version collection, catalog management, snapshot operations
- **Foundation**: Environment detection, configuration, package managers
- **Installation**: Tool installation with retry, validation, and dependency resolution
- **Upgrade Management**: Version comparison, breaking change detection, upgrade workflows
- **Reconciliation**: Multiple installation detection and conflict resolution
- **Utilities**: Logging configuration and common utilities

**Public API Surface:** 100+ exported functions and classes via `cli_audit/__init__.py`

---

## Quick Start

### Basic Usage

```python
from cli_audit import (
    ToolCatalog,
    detect_environment,
    install_tool,
    upgrade_tool,
    bulk_install,
    reconcile_tool,
)

# Load tool catalog
catalog = ToolCatalog()
ripgrep = catalog.get("ripgrep")

# Detect environment
env = detect_environment()
print(f"OS: {env.os}, Arch: {env.arch}")

# Install a tool
result = install_tool("ripgrep", env)
if result.success:
    print(f"Installed: {result.installed_version}")

# Upgrade a tool
upgrade_result = upgrade_tool("ripgrep", env)
if upgrade_result.success:
    print(f"Upgraded: {upgrade_result.old_version} → {upgrade_result.new_version}")

# Bulk install multiple tools
tools = ["ripgrep", "fd", "jq"]
bulk_result = bulk_install(tools, env)
print(f"Installed: {bulk_result.success_count}/{len(tools)}")

# Reconcile duplicate installations
reconcile_result = reconcile_tool("node", env, prefer="nvm")
print(f"Reconciled: {reconcile_result.removed_count} duplicates removed")
```

---

## Module Reference

### Detection and Auditing

#### `cli_audit.catalog` - Tool Catalog Management

**Classes:**

```python
@dataclass
class ToolCatalogEntry:
    """Tool catalog entry from catalog/*.json file."""
    name: str
    description: str = ""
    homepage: str = ""
    github_repo: str = ""
    binary_name: str = ""
    install_method: str = ""
    package_name: str = ""
    script: str = ""
    pinned_version: str = ""
    notes: str = ""
    candidates: list[str] | None = None
    category: str = ""
    hint: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCatalogEntry":
        """Create from catalog JSON data."""

    def to_tool(self) -> "Tool":
        """Convert catalog entry to Tool instance."""

class ToolCatalog:
    """Manages tool catalog entries from catalog/ directory."""

    def __init__(self, catalog_dir: str | Path | None = None):
        """Initialize catalog manager."""

    def load_all(self) -> dict[str, ToolCatalogEntry]:
        """Load all catalog entries from JSON files."""

    def get(self, name: str) -> ToolCatalogEntry | None:
        """Get catalog entry by tool name."""

    def has(self, name: str) -> bool:
        """Check if catalog has entry for tool."""

    def list_all(self) -> list[str]:
        """List all tool names in catalog."""
```

**Usage:**

```python
from cli_audit import ToolCatalog

# Load catalog (73 tools)
catalog = ToolCatalog()
entries = catalog.load_all()

# Get specific tool
ripgrep = catalog.get("ripgrep")
print(f"{ripgrep.name}: {ripgrep.description}")
print(f"Install: {ripgrep.install_method}")
print(f"GitHub: {ripgrep.github_repo}")

# Check if tool exists
if catalog.has("fzf"):
    fzf = catalog.get("fzf")

# List all tools
all_tools = catalog.list_all()  # Returns list of 73 tool names
```

#### `cli_audit.collectors` - Upstream Version Collection

**Functions:**

```python
def collect_github(owner: str, repo: str) -> tuple[str, str]:
    """
    Collect latest version from GitHub releases.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Tuple of (version_tag, version_number)

    Example:
        >>> tag, ver = collect_github("BurntSushi", "ripgrep")
        >>> print(f"ripgrep {ver}")  # ripgrep 14.1.1
    """

def collect_gitlab(owner: str, repo: str) -> tuple[str, str]:
    """
    Collect latest version from GitLab releases.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Tuple of (version_tag, version_number)
    """

def collect_pypi(package: str) -> tuple[str, str]:
    """
    Collect latest version from PyPI.

    Args:
        package: Package name

    Returns:
        Tuple of (version_tag, version_number)

    Example:
        >>> tag, ver = collect_pypi("black")
        >>> print(f"black {ver}")  # black 25.1.0
    """

def collect_npm(package: str) -> tuple[str, str]:
    """
    Collect latest version from npm registry.

    Args:
        package: Package name

    Returns:
        Tuple of (version_tag, version_number)
    """

def collect_crates(crate: str) -> tuple[str, str]:
    """
    Collect latest version from crates.io.

    Args:
        crate: Crate name

    Returns:
        Tuple of (version_tag, version_number)
    """

def normalize_version_tag(tag: str) -> str:
    """
    Normalize version tag by removing common prefixes.

    Args:
        tag: Version tag (e.g., "v1.2.3", "release-1.2.3")

    Returns:
        Normalized version (e.g., "1.2.3")
    """

def extract_version_number(text: str) -> str:
    """
    Extract semantic version number from text.

    Args:
        text: Text containing version

    Returns:
        Extracted version or empty string

    Example:
        >>> extract_version_number("ripgrep 14.1.1")
        "14.1.1"
    """

def get_github_rate_limit() -> tuple[int, int]:
    """
    Get GitHub API rate limit status.

    Returns:
        Tuple of (remaining, total)

    Example:
        >>> remaining, total = get_github_rate_limit()
        >>> print(f"{remaining}/{total} remaining")
    """
```

#### `cli_audit.tools` - Tool Registry

**Classes:**

```python
@dataclass(frozen=True)
class Tool:
    """Tool definition with upstream source information."""
    name: str                    # Display name (e.g., "ripgrep")
    candidates: tuple[str, ...]  # Executable names to search (e.g., ("rg",))
    source_kind: str            # "gh" | "pypi" | "npm" | "crates" | "gnu" | "skip"
    source_args: tuple[str, ...] # Source-specific parameters
    category: str = "other"      # Tool category for grouping
    hint: str = ""              # Installation hint
```

**Functions:**

```python
def all_tools() -> tuple[Tool, ...]:
    """
    Get all registered tools (catalog + fallback).

    Returns:
        Tuple of Tool instances (73+ tools)
    """

def filter_tools(category: str | None = None,
                 only: list[str] | None = None) -> tuple[Tool, ...]:
    """
    Filter tools by category or name list.

    Args:
        category: Filter by category ("runtimes", "search", etc.)
        only: Filter by tool names

    Returns:
        Filtered tuple of Tool instances

    Example:
        >>> tools = filter_tools(category="runtimes")
        >>> # Returns: go, python, node, rust, ruby

        >>> tools = filter_tools(only=["ripgrep", "fd", "jq"])
        >>> # Returns: specified tools only
    """

def get_tool(name: str) -> Tool | None:
    """
    Get tool by name.

    Args:
        name: Tool name

    Returns:
        Tool instance or None
    """

def tool_homepage_url(tool: Tool) -> str:
    """Get tool homepage URL from catalog or construct from source."""

def latest_target_url(tool: Tool, version: str) -> str:
    """Construct URL for latest release based on tool source."""
```

#### `cli_audit.detection` - Installation Detection

**Functions:**

```python
def find_paths(candidates: tuple[str, ...]) -> list[str]:
    """
    Find all paths for executable candidates.

    Args:
        candidates: Executable names to search

    Returns:
        List of absolute paths

    Example:
        >>> paths = find_paths(("rg", "ripgrep"))
        >>> # ["/usr/bin/rg", "/home/user/.cargo/bin/rg"]
    """

def get_version_line(path: str, timeout: float = 2.0) -> str:
    """
    Get version line from executable.

    Args:
        path: Absolute path to executable
        timeout: Command timeout in seconds

    Returns:
        Version output string

    Example:
        >>> ver = get_version_line("/usr/bin/rg")
        >>> # "ripgrep 14.1.1"
    """

def extract_version_number(text: str) -> str:
    """
    Extract version number from text.

    Args:
        text: Text containing version

    Returns:
        Extracted version or empty string
    """

def detect_install_method(path: str) -> str:
    """
    Detect installation method from path.

    Args:
        path: Absolute path to executable

    Returns:
        Install method string (e.g., "rustup/cargo", "pip", "apt")

    Example:
        >>> method = detect_install_method("/home/user/.cargo/bin/rg")
        >>> # "rustup/cargo"
    """

def audit_tool_installation(tool: Tool) -> dict[str, Any]:
    """
    Audit tool installation status.

    Args:
        tool: Tool instance

    Returns:
        Dict with installation details

    Example:
        >>> from cli_audit import get_tool
        >>> tool = get_tool("ripgrep")
        >>> audit = audit_tool_installation(tool)
        >>> audit["installed_version"]  # "14.1.1"
        >>> audit["install_method"]     # "rustup/cargo"
    """
```

#### `cli_audit.snapshot` - Snapshot Management

**Functions:**

```python
def load_snapshot(paths: list[str] | None = None) -> dict[str, Any]:
    """
    Load snapshot from file.

    Args:
        paths: List of paths to try (defaults to standard locations)

    Returns:
        Snapshot data dict

    Example:
        >>> snap = load_snapshot()
        >>> snap["tools"]["ripgrep"]["version"]  # "14.1.1"
    """

def write_snapshot(data: dict[str, Any],
                   path: str | None = None) -> None:
    """
    Write snapshot to file.

    Args:
        data: Snapshot data
        path: Output path (defaults to tools_snapshot.json)
    """

def render_from_snapshot(snapshot: dict[str, Any]) -> None:
    """
    Render audit table from snapshot data.

    Args:
        snapshot: Snapshot data from load_snapshot()
    """

def get_snapshot_path() -> str:
    """
    Get default snapshot path.

    Returns:
        Path to tools_snapshot.json
    """
```

#### `cli_audit.render` - Output Formatting

**Functions:**

```python
def status_icon(status: str, use_emoji: bool = True) -> str:
    """
    Get status icon for tool state.

    Args:
        status: Status string ("UP-TO-DATE", "OUTDATED", "NOT INSTALLED")
        use_emoji: Whether to use emoji icons

    Returns:
        Icon string
    """

def osc8(url: str, text: str) -> str:
    """
    Create OSC 8 clickable hyperlink.

    Args:
        url: Target URL
        text: Display text

    Returns:
        ANSI escape sequence for clickable link
    """

def render_table(rows: list[list[str]],
                 headers: list[str] | None = None) -> None:
    """
    Render formatted table with ANSI/emoji preservation.

    Args:
        rows: Table data rows
        headers: Optional header row
    """

def print_summary(snapshot: dict[str, Any]) -> None:
    """
    Print audit summary statistics.

    Args:
        snapshot: Snapshot data
    """
```

---

### Foundation Modules

#### `cli_audit.environment` - Environment Detection

**Classes:**

```python
@dataclass
class Environment:
    """System environment information."""
    os: str              # "linux" | "darwin" | "windows"
    arch: str            # "x86_64" | "aarch64" | "arm64"
    distro: str          # Distribution name (Linux)
    distro_version: str  # Distribution version
    in_ci: bool          # Running in CI/CD
    python_version: str  # Python version
    shell: str           # Current shell

**Functions:**

```python
def detect_environment() -> Environment:
    """
    Detect current system environment.

    Returns:
        Environment instance with system details

    Example:
        >>> env = detect_environment()
        >>> env.os      # "linux"
        >>> env.arch    # "x86_64"
        >>> env.distro  # "ubuntu"
    """

def get_environment_from_config(config: Config) -> Environment:
    """
    Get environment with config overrides.

    Args:
        config: Configuration instance

    Returns:
        Environment with config-specified values
    """
```

#### `cli_audit.config` - Configuration Management

**Classes:**

```python
@dataclass
class ToolConfig:
    """Per-tool configuration."""
    version: str = ""           # Required version
    skip: bool = False          # Skip this tool
    install_method: str = ""    # Preferred install method

@dataclass
class Preferences:
    """Installation preferences."""
    package_manager: str = ""   # Preferred package manager
    confirm_breaking: bool = True
    auto_cleanup: bool = False

@dataclass
class BulkPreferences:
    """Bulk operation preferences."""
    max_parallel: int = 4
    fail_fast: bool = False
    skip_breaking: bool = False

@dataclass
class Config:
    """Project configuration from .cli-audit.yml."""
    tools: dict[str, ToolConfig]
    preferences: Preferences
    bulk: BulkPreferences
    environment: dict[str, str]
```

**Functions:**

```python
def load_config(path: str | None = None) -> Config:
    """
    Load configuration from file.

    Args:
        path: Config file path (defaults to .cli-audit.yml)

    Returns:
        Config instance

    Example:
        >>> config = load_config()
        >>> config.tools["ripgrep"].version  # "14.1.0"
    """

def load_config_file(path: str) -> dict[str, Any]:
    """Load and parse YAML config file."""

def validate_config(config: dict[str, Any]) -> list[str]:
    """
    Validate config structure.

    Args:
        config: Config dict

    Returns:
        List of validation errors (empty if valid)
    """
```

#### `cli_audit.package_managers` - Package Manager Abstraction

**Classes:**

```python
@dataclass
class PackageManager:
    """Package manager abstraction."""
    name: str
    install_cmd: list[str]
    upgrade_cmd: list[str]
    remove_cmd: list[str]
    available: bool
```

**Functions:**

```python
def select_package_manager(env: Environment,
                           prefer: str | None = None) -> PackageManager | None:
    """
    Select best package manager for environment.

    Args:
        env: Environment instance
        prefer: Preferred package manager name

    Returns:
        PackageManager instance or None

    Example:
        >>> env = detect_environment()
        >>> pm = select_package_manager(env, prefer="apt")
        >>> pm.install_cmd  # ["sudo", "apt", "install", "-y"]
    """

def get_available_package_managers(env: Environment) -> list[PackageManager]:
    """
    Get all available package managers.

    Args:
        env: Environment instance

    Returns:
        List of available PackageManager instances
    """
```

#### `cli_audit.install_plan` - Installation Planning

**Classes:**

```python
@dataclass
class InstallStep:
    """Single installation step."""
    command: list[str]
    description: str
    retryable: bool = True
    timeout: int = 300

@dataclass
class InstallPlan:
    """Complete installation plan for a tool."""
    tool_name: str
    steps: list[InstallStep]
    dependencies: list[str]
    estimated_time: int
```

**Functions:**

```python
def generate_install_plan(tool_name: str,
                          env: Environment,
                          config: Config | None = None) -> InstallPlan:
    """
    Generate installation plan for tool.

    Args:
        tool_name: Tool to install
        env: Environment instance
        config: Optional configuration

    Returns:
        InstallPlan with steps and dependencies

    Example:
        >>> env = detect_environment()
        >>> plan = generate_install_plan("ripgrep", env)
        >>> for step in plan.steps:
        ...     print(step.description)
    """

def dry_run_install(tool_name: str, env: Environment) -> None:
    """
    Print installation plan without executing.

    Args:
        tool_name: Tool to preview
        env: Environment instance
    """
```

---

### Installation Modules

#### `cli_audit.installer` - Tool Installation

**Classes:**

```python
@dataclass
class StepResult:
    """Result of single installation step."""
    success: bool
    output: str
    error: str | None = None
    duration: float = 0.0

@dataclass
class InstallResult:
    """Complete installation result."""
    tool_name: str
    success: bool
    installed_version: str
    install_method: str
    steps: list[StepResult]
    duration: float
    error: str | None = None

class InstallError(Exception):
    """Installation error exception."""
    pass
```

**Functions:**

```python
def install_tool(tool_name: str,
                 env: Environment,
                 config: Config | None = None,
                 force: bool = False) -> InstallResult:
    """
    Install a tool.

    Args:
        tool_name: Tool to install
        env: Environment instance
        config: Optional configuration
        force: Force reinstall if already installed

    Returns:
        InstallResult with installation details

    Example:
        >>> env = detect_environment()
        >>> result = install_tool("ripgrep", env)
        >>> if result.success:
        ...     print(f"Installed {result.installed_version}")
    """

def execute_step(step: InstallStep) -> StepResult:
    """
    Execute single installation step.

    Args:
        step: Installation step

    Returns:
        StepResult with execution details
    """

def execute_step_with_retry(step: InstallStep,
                            max_retries: int = 3) -> StepResult:
    """
    Execute step with retry logic.

    Args:
        step: Installation step
        max_retries: Maximum retry attempts

    Returns:
        StepResult from final attempt
    """

def verify_checksum(file_path: str, expected: str) -> bool:
    """
    Verify file checksum.

    Args:
        file_path: File to verify
        expected: Expected checksum (SHA256)

    Returns:
        True if checksum matches
    """

def validate_installation(tool_name: str) -> bool:
    """
    Validate tool installation.

    Args:
        tool_name: Tool to validate

    Returns:
        True if tool is properly installed
    """
```

---

### Bulk Operations

#### `cli_audit.bulk` - Parallel Bulk Operations

**Classes:**

```python
@dataclass
class ToolSpec:
    """Tool specification for bulk operations."""
    name: str
    version: str | None = None
    force: bool = False

@dataclass
class ProgressTracker:
    """Progress tracker for bulk operations."""
    total: int
    completed: int
    failed: int
    current: str

    def update(self, tool: str, success: bool) -> None:
        """Update progress."""

@dataclass
class BulkInstallResult:
    """Result of bulk installation."""
    total: int
    success_count: int
    failed_count: int
    results: dict[str, InstallResult]
    duration: float
```

**Functions:**

```python
def bulk_install(tools: list[str] | list[ToolSpec],
                 env: Environment,
                 config: Config | None = None,
                 max_parallel: int = 4,
                 fail_fast: bool = False) -> BulkInstallResult:
    """
    Install multiple tools in parallel.

    Args:
        tools: List of tool names or ToolSpec instances
        env: Environment instance
        config: Optional configuration
        max_parallel: Maximum parallel installations
        fail_fast: Stop on first failure

    Returns:
        BulkInstallResult with all installation results

    Example:
        >>> env = detect_environment()
        >>> tools = ["ripgrep", "fd", "jq", "bat"]
        >>> result = bulk_install(tools, env, max_parallel=2)
        >>> print(f"{result.success_count}/{result.total} succeeded")
    """

def get_missing_tools(tools: list[str]) -> list[str]:
    """
    Get list of tools not currently installed.

    Args:
        tools: Tool names to check

    Returns:
        List of missing tool names
    """

def resolve_dependencies(tools: list[str]) -> list[str]:
    """
    Resolve and order tools by dependencies.

    Args:
        tools: Tool names

    Returns:
        Ordered list with dependencies first
    """

def generate_rollback_script(result: BulkInstallResult) -> str:
    """
    Generate rollback script for bulk operation.

    Args:
        result: Bulk install result

    Returns:
        Shell script to rollback installations
    """

def execute_rollback(script: str) -> bool:
    """
    Execute rollback script.

    Args:
        script: Rollback script from generate_rollback_script

    Returns:
        True if rollback succeeded
    """
```

---

### Breaking Change Management

#### `cli_audit.breaking_changes` - Semver Analysis

**Functions:**

```python
def is_major_upgrade(old_version: str, new_version: str) -> bool:
    """
    Check if upgrade is a major version bump.

    Args:
        old_version: Current version
        new_version: Target version

    Returns:
        True if major version increased

    Example:
        >>> is_major_upgrade("1.4.0", "2.0.0")
        True
        >>> is_major_upgrade("1.4.0", "1.5.0")
        False
    """

def check_breaking_change_policy(tool: str,
                                 old_version: str,
                                 new_version: str) -> bool:
    """
    Check if upgrade violates breaking change policy.

    Args:
        tool: Tool name
        old_version: Current version
        new_version: Target version

    Returns:
        True if policy allows upgrade
    """

def format_breaking_change_warning(tool: str,
                                   old_version: str,
                                   new_version: str) -> str:
    """
    Format breaking change warning message.

    Args:
        tool: Tool name
        old_version: Current version
        new_version: Target version

    Returns:
        Formatted warning string
    """

def confirm_breaking_change(tool: str,
                            old_version: str,
                            new_version: str) -> bool:
    """
    Prompt user to confirm breaking change.

    Args:
        tool: Tool name
        old_version: Current version
        new_version: Target version

    Returns:
        True if user confirms
    """

def confirm_bulk_breaking_changes(changes: list[tuple[str, str, str]]) -> bool:
    """
    Confirm multiple breaking changes.

    Args:
        changes: List of (tool, old_version, new_version) tuples

    Returns:
        True if user confirms all
    """

def filter_by_breaking_changes(candidates: list,
                               allow_breaking: bool = False) -> list:
    """
    Filter upgrade candidates by breaking change policy.

    Args:
        candidates: List of upgrade candidates
        allow_breaking: Allow breaking changes

    Returns:
        Filtered list
    """
```

---

### Upgrade Management

#### `cli_audit.upgrade` - Version Upgrades

**Classes:**

```python
@dataclass
class UpgradeCandidate:
    """Tool that can be upgraded."""
    tool_name: str
    current_version: str
    available_version: str
    is_major: bool
    install_method: str

@dataclass
class UpgradeBackup:
    """Backup before upgrade."""
    tool_name: str
    version: str
    binary_path: str
    backup_path: str
    created_at: str

@dataclass
class UpgradeResult:
    """Result of tool upgrade."""
    tool_name: str
    success: bool
    old_version: str
    new_version: str
    backup: UpgradeBackup | None
    duration: float
    error: str | None = None

@dataclass
class BulkUpgradeResult:
    """Result of bulk upgrade."""
    total: int
    success_count: int
    failed_count: int
    skipped_count: int
    results: dict[str, UpgradeResult]
    duration: float
```

**Functions:**

```python
def compare_versions(v1: str, v2: str) -> int:
    """
    Compare semantic versions.

    Args:
        v1: First version
        v2: Second version

    Returns:
        -1 if v1 < v2, 0 if equal, 1 if v1 > v2

    Example:
        >>> compare_versions("1.2.3", "1.3.0")
        -1
    """

def get_available_version(tool_name: str) -> str | None:
    """
    Get latest available version for tool.

    Args:
        tool_name: Tool name

    Returns:
        Latest version string or None
    """

def check_upgrade_available(tool_name: str) -> UpgradeCandidate | None:
    """
    Check if upgrade is available for tool.

    Args:
        tool_name: Tool name

    Returns:
        UpgradeCandidate if upgrade available, else None
    """

def clear_version_cache() -> None:
    """Clear cached version information."""

def upgrade_tool(tool_name: str,
                 env: Environment,
                 config: Config | None = None,
                 create_backup: bool = True) -> UpgradeResult:
    """
    Upgrade a tool to latest version.

    Args:
        tool_name: Tool to upgrade
        env: Environment instance
        config: Optional configuration
        create_backup: Create backup before upgrade

    Returns:
        UpgradeResult with upgrade details

    Example:
        >>> env = detect_environment()
        >>> result = upgrade_tool("ripgrep", env)
        >>> if result.success:
        ...     print(f"Upgraded: {result.old_version} → {result.new_version}")
    """

def bulk_upgrade(tools: list[str] | None = None,
                 env: Environment,
                 config: Config | None = None,
                 max_parallel: int = 4,
                 skip_breaking: bool = False) -> BulkUpgradeResult:
    """
    Upgrade multiple tools in parallel.

    Args:
        tools: Tool names (None = all upgradeable)
        env: Environment instance
        config: Optional configuration
        max_parallel: Maximum parallel upgrades
        skip_breaking: Skip breaking changes

    Returns:
        BulkUpgradeResult with all upgrade results
    """

def get_upgrade_candidates(skip_breaking: bool = False) -> list[UpgradeCandidate]:
    """
    Get all tools that can be upgraded.

    Args:
        skip_breaking: Exclude major version upgrades

    Returns:
        List of UpgradeCandidate instances
    """

def create_upgrade_backup(tool_name: str) -> UpgradeBackup:
    """
    Create backup before upgrade.

    Args:
        tool_name: Tool to backup

    Returns:
        UpgradeBackup with backup details
    """

def restore_from_backup(backup: UpgradeBackup) -> bool:
    """
    Restore tool from backup.

    Args:
        backup: UpgradeBackup instance

    Returns:
        True if restore succeeded
    """

def cleanup_backup(backup: UpgradeBackup) -> None:
    """Remove backup files."""
```

---

### Reconciliation

#### `cli_audit.reconcile` - Duplicate Installation Management

**Classes:**

```python
@dataclass
class Installation:
    """Detected tool installation."""
    path: str
    version: str
    install_method: str
    preferred: bool

@dataclass
class ReconciliationResult:
    """Result of reconciliation."""
    tool_name: str
    success: bool
    kept: Installation
    removed: list[Installation]
    removed_count: int
    error: str | None = None

@dataclass
class BulkReconciliationResult:
    """Result of bulk reconciliation."""
    total: int
    success_count: int
    failed_count: int
    total_removed: int
    results: dict[str, ReconciliationResult]
```

**Constants:**

```python
SYSTEM_TOOL_SAFELIST: set[str]
"""Tools that should not be removed from system paths."""
```

**Functions:**

```python
def detect_installations(tool_name: str) -> list[Installation]:
    """
    Detect all installations of a tool.

    Args:
        tool_name: Tool name

    Returns:
        List of Installation instances

    Example:
        >>> installs = detect_installations("node")
        >>> for inst in installs:
        ...     print(f"{inst.version} via {inst.install_method}")
    """

def classify_install_method(path: str) -> str:
    """
    Classify installation method from path.

    Args:
        path: Installation path

    Returns:
        Install method string
    """

def clear_detection_cache() -> None:
    """Clear installation detection cache."""

def sort_by_preference(installations: list[Installation],
                      prefer: str | None = None) -> list[Installation]:
    """
    Sort installations by preference.

    Args:
        installations: List of installations
        prefer: Preferred install method

    Returns:
        Sorted list (preferred first)
    """

def reconcile_tool(tool_name: str,
                   env: Environment,
                   prefer: str | None = None,
                   keep_system: bool = True) -> ReconciliationResult:
    """
    Reconcile duplicate tool installations.

    Args:
        tool_name: Tool to reconcile
        env: Environment instance
        prefer: Preferred install method ("nvm", "rustup", etc.)
        keep_system: Keep system-installed version

    Returns:
        ReconciliationResult with removed installations

    Example:
        >>> env = detect_environment()
        >>> result = reconcile_tool("node", env, prefer="nvm")
        >>> print(f"Removed {result.removed_count} duplicates")
    """

def bulk_reconcile(tools: list[str],
                   env: Environment,
                   prefer: dict[str, str] | None = None) -> BulkReconciliationResult:
    """
    Reconcile multiple tools.

    Args:
        tools: Tool names
        env: Environment instance
        prefer: Dict of tool -> preferred method

    Returns:
        BulkReconciliationResult with all results
    """

def verify_path_ordering(tool_name: str) -> bool:
    """
    Verify PATH ordering after reconciliation.

    Args:
        tool_name: Tool to verify

    Returns:
        True if preferred installation comes first in PATH
    """
```

---

### Logging Configuration

#### `cli_audit.logging_config` - Logging Setup

**Functions:**

```python
def setup_logging(level: str = "INFO",
                  log_file: str | None = None,
                  format: str = "standard") -> None:
    """
    Configure logging for cli_audit.

    Args:
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: Optional log file path
        format: Format preset ("standard", "json", "detailed")

    Example:
        >>> setup_logging(level="DEBUG", log_file="audit.log")
    """

def get_logger(name: str) -> logging.Logger:
    """
    Get logger for module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting installation")
    """
```

---

## Advanced Usage

### Custom Tool Installation

```python
from cli_audit import (
    detect_environment,
    generate_install_plan,
    execute_step_with_retry,
    validate_installation,
)

# Custom installation with fine control
env = detect_environment()
plan = generate_install_plan("custom-tool", env)

# Execute with custom logic
for step in plan.steps:
    result = execute_step_with_retry(step, max_retries=5)
    if not result.success:
        print(f"Step failed: {result.error}")
        break

# Validate
if validate_installation("custom-tool"):
    print("Installation successful!")
```

### Parallel Bulk Operations

```python
from cli_audit import bulk_install, bulk_upgrade, bulk_reconcile, detect_environment

env = detect_environment()

# Install core tools in parallel
core_tools = ["ripgrep", "fd", "jq", "bat", "delta"]
install_result = bulk_install(core_tools, env, max_parallel=3)

# Upgrade all outdated tools
upgrade_result = bulk_upgrade(env=env, max_parallel=2, skip_breaking=True)

# Reconcile all tools with nvm/rustup preference
reconcile_result = bulk_reconcile(
    ["node", "rust", "python"],
    env,
    prefer={"node": "nvm", "rust": "rustup", "python": "pyenv"}
)
```

### Version Comparison and Breaking Changes

```python
from cli_audit import (
    compare_versions,
    is_major_upgrade,
    check_upgrade_available,
    format_breaking_change_warning,
)

# Compare versions
if compare_versions("1.4.0", "2.0.0") < 0:
    print("Upgrade available")

# Check for breaking changes
candidate = check_upgrade_available("ripgrep")
if candidate and candidate.is_major:
    warning = format_breaking_change_warning(
        "ripgrep",
        candidate.current_version,
        candidate.available_version
    )
    print(warning)
```

---

## Environment Variables

The API respects these environment variables:

```bash
# Logging
CLI_AUDIT_DEBUG=1              # Enable debug logging
CLI_AUDIT_LOG_FILE=audit.log   # Log file path

# Installation
CLI_AUDIT_INSTALL_TIMEOUT=600  # Install timeout (seconds)
CLI_AUDIT_MAX_RETRIES=3        # Max retry attempts
CLI_AUDIT_PARALLEL_INSTALLS=4  # Parallel installation limit

# Upgrade
CLI_AUDIT_AUTO_UPGRADE=0       # Disable auto-upgrade prompts
CLI_AUDIT_SKIP_BREAKING=1      # Skip breaking changes

# Reconciliation
CLI_AUDIT_KEEP_SYSTEM=1        # Keep system installations
CLI_AUDIT_PREFER_METHOD=nvm    # Global preference

# Cache
CLI_AUDIT_CACHE_DIR=~/.cache/cli-audit  # Cache directory
CLI_AUDIT_CLEAR_CACHE=1        # Clear cache on startup
```

---

## Error Handling

All installation, upgrade, and reconciliation operations return result objects with success indicators and error messages:

```python
from cli_audit import install_tool, InstallError

try:
    result = install_tool("ripgrep", env)
    if not result.success:
        print(f"Installation failed: {result.error}")
        for step in result.steps:
            if not step.success:
                print(f"  Step failed: {step.error}")
except InstallError as e:
    print(f"Critical error: {e}")
```

---

## Migration from v1.x

The v2.0 API maintains backward compatibility via `__init__.py` exports. Most v1.x code will work without changes:

```python
# v1.x code (still works)
from cli_audit import Tool, TOOLS, audit_tool

# v2.0 code (recommended)
from cli_audit import ToolCatalog, all_tools, audit_tool_installation

catalog = ToolCatalog()
tools = all_tools()  # Returns catalog + fallback TOOLS
```

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed migration instructions.

---

## See Also

- [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) - Detailed Phase 2 API documentation (78 symbols)
- [FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md) - Categorized function quick lookup
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - v1.x → v2.0 migration guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Module organization and design patterns
- [INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md) - Real-world usage examples

---

**API Version:** 2.0.0
**Last Updated:** 2025-11-06
**Next Review:** After additional module expansions
