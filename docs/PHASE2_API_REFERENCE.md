# Phase 2 API Reference

**Version:** 2.0.0-alpha.6
**Package:** `cli_audit`
**Complete:** 78 public API symbols across 11 modules

---

## Quick Start

```python
# Complete import example
from cli_audit import (
    # Phase 2.1: Foundation
    Environment, Config, PackageManager,
    detect_environment, load_config, select_package_manager,

    # Phase 2.2: Installation
    install_tool, InstallResult,

    # Phase 2.3: Bulk Operations
    bulk_install, BulkInstallResult,

    # Phase 2.4: Upgrade Management
    upgrade_tool, get_upgrade_candidates, UpgradeResult,

    # Phase 2.5: Reconciliation
    reconcile_tool, detect_installations, ReconciliationResult,
)

# Typical workflow
config = load_config()
env = detect_environment()

result = install_tool(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,
    language="rust",
)

if result.success:
    print(f"✓ Installed {result.installed_version}")
```

---

## Module Overview

### Phase 2.1: Foundation

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **[environment](phase2_api/environment.md)** | Environment detection | `Environment`, `detect_environment()` |
| **config** | Configuration management | `Config`, `Preferences`, `load_config()` |
| **package_managers** | PM abstraction | `PackageManager`, `select_package_manager()` |
| **install_plan** | Installation planning | `InstallPlan`, `generate_install_plan()` |

### Phase 2.2: Core Installation

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **installer** | Single tool installation | `install_tool()`, `InstallResult` |

### Phase 2.3: Bulk Operations

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **bulk** | Parallel operations | `bulk_install()`, `BulkInstallResult` |

### Phase 2.4: Upgrade Management

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **upgrade** | Version management | `upgrade_tool()`, `get_upgrade_candidates()` |
| **breaking_changes** | Breaking change detection | `is_major_upgrade()`, `confirm_breaking_change()` |

### Phase 2.5: Reconciliation

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **reconcile** | Conflict resolution | `reconcile_tool()`, `detect_installations()` |

### Shared Infrastructure

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| **logging_config** | Logging framework | `setup_logging()`, `get_logger()` |
| **common** | Utilities | `vlog()` |

---

## Complete API Reference

### Phase 2.1: Foundation

#### environment.py

**Detailed Documentation:** [environment.md](phase2_api/environment.md)

```python
@dataclass(frozen=True)
class Environment:
    mode: str                     # "ci", "server", or "workstation"
    confidence: float             # 0.0-1.0
    indicators: tuple[str, ...]   # Detection evidence
    override: bool                # Explicit override flag

def detect_environment(
    override: str | None = None,
    verbose: bool = False
) -> Environment

def get_environment_from_config(
    config_mode: str | None,
    verbose: bool = False
) -> Environment
```

**Usage:**
```python
env = detect_environment()
if env.mode == "ci":
    # CI-specific logic
elif env.mode == "server":
    # Server-specific logic
else:  # workstation
    # Workstation-specific logic
```

#### config.py

```python
@dataclass(frozen=True)
class Config:
    version: int                           # Schema version
    environment_mode: str                  # "auto", "ci", "server", "workstation"
    tools: dict[str, ToolConfig]           # Per-tool overrides
    preferences: Preferences               # Global preferences
    presets: dict[str, list[str]]          # Named tool sets
    source: str                            # Config file path

@dataclass(frozen=True)
class ToolConfig:
    version: str                           # "latest", "1.2.*", "1.2.3"
    method: str | None                     # Preferred PM
    fallback: str | None                   # Fallback PM

@dataclass(frozen=True)
class Preferences:
    reconciliation: str                    # "parallel" or "aggressive"
    breaking_changes: str                  # "accept", "warn", or "reject"
    auto_upgrade: bool                     # Auto-upgrade minor/patch
    timeout_seconds: int                   # Network timeout (1-60)
    max_workers: int                       # Parallel workers (1-32)
    cache_ttl_seconds: int                 # Version cache TTL (60-86400)
    package_managers: dict[str, list[str]] # PM hierarchies
    bulk: BulkPreferences                  # Bulk operation prefs

@dataclass(frozen=True)
class BulkPreferences:
    fail_fast: bool                        # Stop on first failure
    auto_rollback: bool                    # Auto-rollback on failure
    generate_rollback_script: bool         # Create rollback script

def load_config(
    custom_path: str | None = None,
    verbose: bool = False
) -> Config

def validate_config(config: Config) -> list[str]
```

**Usage:**
```python
# Load from standard locations
config = load_config()

# Custom path
config = load_config(custom_path=".my-config.yml")

# Access settings
print(config.preferences.max_workers)  # 16
print(config.preferences.cache_ttl_seconds)  # 3600

# Tool-specific config
tool_cfg = config.get_tool_config("black")
print(tool_cfg.version)  # "latest"
```

#### package_managers.py

```python
class PackageManager(Enum):
    CARGO = "cargo"
    PIPX = "pipx"
    UV = "uv"
    NPM = "npm"
    PIP = "pip"
    APT = "apt"
    DNF = "dnf"
    BREW = "brew"
    # ... more

def select_package_manager(
    language: str,
    config: Config | None = None,
    env: Environment | None = None,
    verbose: bool = False
) -> PackageManager

def get_available_package_managers(
    language: str,
    verbose: bool = False
) -> list[PackageManager]
```

**Usage:**
```python
# Auto-select best PM
pm = select_package_manager("python", config, env)
print(pm)  # PackageManager.PIPX

# List available PMs
available = get_available_package_managers("rust")
print(available)  # [PackageManager.CARGO]
```

#### install_plan.py

```python
@dataclass(frozen=True)
class InstallStep:
    description: str
    command: tuple[str, ...]
    required: bool = True
    timeout_seconds: int = 300

@dataclass(frozen=True)
class InstallPlan:
    tool_name: str
    package_name: str
    target_version: str
    package_manager: PackageManager
    steps: tuple[InstallStep, ...]

def generate_install_plan(
    tool_name: str,
    package_name: str,
    target_version: str,
    config: Config,
    env: Environment,
    language: str,
    verbose: bool = False
) -> InstallPlan

def dry_run_install(
    plan: InstallPlan,
    verbose: bool = False
) -> InstallResult
```

**Usage:**
```python
# Generate plan
plan = generate_install_plan(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,
    language="rust",
)

# Inspect plan
for step in plan.steps:
    print(f"{step.description}: {' '.join(step.command)}")

# Dry run (no actual execution)
result = dry_run_install(plan, verbose=True)
```

---

### Phase 2.2: Core Installation

#### installer.py

```python
@dataclass(frozen=True)
class InstallResult:
    tool_name: str
    success: bool
    installed_version: str | None
    package_manager_used: str
    steps_completed: tuple[str, ...]
    duration_seconds: float
    validation_passed: bool = False
    binary_path: str | None = None
    error_message: str | None = None

def install_tool(
    tool_name: str,
    package_name: str,
    target_version: str,
    config: Config,
    env: Environment,
    language: str,
    verbose: bool = False
) -> InstallResult

def execute_step_with_retry(
    step: InstallStep,
    max_retries: int = 3,
    base_delay: float = 1.0,
    verbose: bool = False
) -> StepResult

def validate_installation(
    tool_name: str,
    expected_version: str | None = None,
    verbose: bool = False
) -> tuple[bool, str | None]

def verify_checksum(
    file_path: str,
    expected_checksum: str,
    algorithm: str = "sha256"
) -> bool
```

**Usage:**
```python
# Install single tool
result = install_tool(
    tool_name="black",
    package_name="black",
    target_version="latest",
    config=config,
    env=env,
    language="python",
    verbose=True,
)

if result.success:
    print(f"✓ Installed {result.installed_version}")
    print(f"  Location: {result.binary_path}")
    print(f"  Time: {result.duration_seconds:.2f}s")
else:
    print(f"✗ Failed: {result.error_message}")
```

---

### Phase 2.3: Bulk Operations

#### bulk.py

```python
@dataclass(frozen=True)
class BulkInstallResult:
    successes: tuple[InstallResult, ...]
    failures: tuple[InstallResult, ...]
    skipped: tuple[str, ...]
    duration_seconds: float
    rollback_script_path: str | None = None

def bulk_install(
    mode: str,  # "explicit", "preset", "auto"
    tool_names: list[str] | None = None,
    preset_name: str | None = None,
    config: Config | None = None,
    env: Environment | None = None,
    max_workers: int = 16,
    fail_fast: bool = False,
    atomic: bool = False,
    verbose: bool = False
) -> BulkInstallResult

def get_missing_tools(
    tool_names: list[str],
    verbose: bool = False
) -> list[str]

def resolve_dependencies(
    specs: list[ToolSpec]
) -> list[list[ToolSpec]]

def generate_rollback_script(
    successes: list[InstallResult],
    output_path: str | None = None
) -> str

class ProgressTracker:
    def update(self, tool_name: str, status: str, message: str = "")
    def get_progress(self, tool_name: str) -> dict[str, str]
```

**Usage:**
```python
# Bulk install explicit tools
result = bulk_install(
    mode="explicit",
    tool_names=["ripgrep", "fd", "bat"],
    config=config,
    env=env,
    max_workers=3,
    fail_fast=False,
)

print(f"✓ Installed: {len(result.successes)}")
print(f"✗ Failed: {len(result.failures)}")

# Install from preset
result = bulk_install(
    mode="preset",
    preset_name="dev-essentials",
    config=config,
    env=env,
)
```

---

### Phase 2.4: Upgrade Management

#### upgrade.py

```python
@dataclass(frozen=True)
class UpgradeResult:
    tool_name: str
    success: bool
    previous_version: str | None
    installed_version: str | None
    package_manager_used: str
    breaking_change: bool
    backup_created: bool
    backup_path: str | None = None
    duration_seconds: float = 0.0
    error_message: str | None = None

@dataclass(frozen=True)
class UpgradeCandidate:
    tool_name: str
    current_version: str
    available_version: str
    package_manager: str
    breaking_change: bool

def upgrade_tool(
    tool_name: str,
    target_version: str,
    current_version: str | None = None,
    config: Config | None = None,
    env: Environment | None = None,
    verbose: bool = False
) -> UpgradeResult

def get_upgrade_candidates(
    tools: list[str],
    config: Config | None = None,
    env: Environment | None = None,
    verbose: bool = False
) -> list[UpgradeCandidate]

def compare_versions(v1: str, v2: str) -> int

def check_upgrade_available(
    tool_name: str,
    package_manager: str,
    cache_ttl: int = 3600,
    verbose: bool = False
) -> tuple[bool, str | None, str | None]
```

**Usage:**
```python
# Get upgrade candidates
candidates = get_upgrade_candidates(
    tools=["black", "ripgrep"],
    config=config,
    env=env,
)

for candidate in candidates:
    print(f"{candidate.tool_name}: {candidate.current_version} → {candidate.available_version}")
    if candidate.breaking_change:
        print("  ⚠️ Breaking change!")

# Upgrade specific tool
result = upgrade_tool(
    tool_name="black",
    target_version="24.0.0",
    config=config,
    env=env,
)
```

#### breaking_changes.py

```python
def is_major_upgrade(v1: str, v2: str) -> bool

def check_breaking_change_policy(
    config: Config,
    current_version: str,
    target_version: str
) -> tuple[bool, str]

def confirm_breaking_change(warning_message: str) -> bool

def filter_by_breaking_changes(
    candidates: Sequence,
    policy: str
) -> tuple[list, list]
```

---

### Phase 2.5: Reconciliation

#### reconcile.py

```python
@dataclass(frozen=True)
class Installation:
    path: str
    method: str
    version: str | None
    priority: int

@dataclass(frozen=True)
class ReconciliationResult:
    tool_name: str
    reconciled: bool
    kept_installation: Installation | None
    removed_installations: tuple[Installation, ...]
    protected: bool = False
    dry_run: bool = False

def reconcile_tool(
    tool_name: str,
    config: Config | None = None,
    env: Environment | None = None,
    dry_run: bool = False,
    verbose: bool = False
) -> ReconciliationResult

def detect_installations(
    tool_name: str,
    verbose: bool = False
) -> list[Installation]

def bulk_reconcile(
    tools: list[str],
    config: Config | None = None,
    env: Environment | None = None,
    dry_run: bool = False,
    max_workers: int = 4,
    verbose: bool = False
) -> BulkReconciliationResult

def verify_path_ordering(
    tool_name: str,
    preferred_method: str,
    verbose: bool = False
) -> tuple[bool, str]

SYSTEM_TOOL_SAFELIST: set[str]  # 26 protected system tools
```

**Usage:**
```python
# Detect multiple installations
installations = detect_installations("python")
for install in installations:
    print(f"{install.method}: {install.path} (v{install.version})")

# Reconcile (keep best, remove others)
result = reconcile_tool(
    tool_name="python",
    config=config,
    env=env,
    dry_run=False,
)

if result.reconciled:
    print(f"✓ Kept: {result.kept_installation.path}")
    print(f"✗ Removed: {len(result.removed_installations)} installations")
```

---

## Common Patterns

### Pattern 1: Standard Workflow

```python
from cli_audit import load_config, detect_environment, install_tool

# 1. Load configuration
config = load_config()

# 2. Detect environment
env = detect_environment()

# 3. Install tool
result = install_tool(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,
    language="rust",
)

# 4. Check result
if result.success:
    print(f"✓ Success: {result.installed_version} at {result.binary_path}")
else:
    print(f"✗ Failed: {result.error_message}")
```

### Pattern 2: Bulk Installation

```python
from cli_audit import bulk_install, load_config, detect_environment

config = load_config()
env = detect_environment()

result = bulk_install(
    mode="explicit",
    tool_names=["ripgrep", "fd", "bat", "delta"],
    config=config,
    env=env,
    max_workers=4,
    fail_fast=False,
)

print(f"Results: {len(result.successes)}/{len(result.successes) + len(result.failures)} succeeded")
```

### Pattern 3: Upgrade Management

```python
from cli_audit import get_upgrade_candidates, upgrade_tool, filter_by_breaking_changes

# Find candidates
candidates = get_upgrade_candidates(
    tools=["black", "ripgrep", "fd"],
    config=config,
    env=env,
)

# Filter by breaking changes
allowed, blocked = filter_by_breaking_changes(
    candidates,
    policy=config.preferences.breaking_changes
)

# Upgrade allowed tools
for candidate in allowed:
    result = upgrade_tool(
        tool_name=candidate.tool_name,
        target_version=candidate.available_version,
        config=config,
        env=env,
    )
```

### Pattern 4: Reconciliation

```python
from cli_audit import detect_installations, reconcile_tool

# Check for duplicates
installations = detect_installations("python")

if len(installations) > 1:
    print(f"Found {len(installations)} Python installations")

    # Reconcile (keep best)
    result = reconcile_tool(
        tool_name="python",
        config=config,
        env=env,
        dry_run=False,  # Set True to preview
    )
```

---

## Error Handling

### InstallError

```python
from cli_audit import InstallError

try:
    result = install_tool(...)
except InstallError as e:
    print(f"Installation failed: {e.message}")
    if e.retryable:
        print("This is a transient error - retrying may succeed")
    if e.remediation:
        print(f"Suggested action: {e.remediation}")
```

### Result Objects

All operation functions return result objects with `success` boolean:

```python
result = install_tool(...)
if not result.success:
    print(f"Error: {result.error_message}")
    # Handle failure
```

---

## Type Hints

All Phase 2 modules use comprehensive type hints:

```python
from cli_audit import Config, Environment, InstallResult

def my_installer(config: Config, env: Environment) -> InstallResult:
    return install_tool(
        tool_name="ripgrep",
        package_name="ripgrep",
        target_version="latest",
        config=config,
        env=env,
        language="rust",
    )
```

Enable type checking:
```bash
mypy your_script.py
```

---

## Logging

```python
from cli_audit import setup_logging, get_logger

# Setup logging
setup_logging(level="DEBUG")

# Get module logger
logger = get_logger(__name__)

logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

---

## Related Documentation

- **User Guide:** [../README.md](../README.md) - End-user documentation
- **Project Guide:** [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Master navigation
- **Architecture:** [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) - System design
- **Contributing:** [../CONTRIBUTING.md](../CONTRIBUTING.md) - Development guide
- **Logging:** [LOGGING.md](LOGGING.md) - Logging framework documentation
- **Code Review:** [CODE_REVIEW.md](CODE_REVIEW.md) - Quality assessment
- **Completion Report:** [PHASE2_COMPLETION_REPORT.md](PHASE2_COMPLETION_REPORT.md) - Phase 2 status
- **Phase Implementation:**
  - [../claudedocs/phase2_1_implementation.md](../claudedocs/phase2_1_implementation.md) - Foundation
  - [../claudedocs/phase2_2_implementation.md](../claudedocs/phase2_2_implementation.md) - Installation
  - [../claudedocs/phase2_3_implementation.md](../claudedocs/phase2_3_implementation.md) - Bulk Operations
  - [../claudedocs/phase2_4_implementation.md](../claudedocs/phase2_4_implementation.md) - Upgrade
  - [../claudedocs/phase2_5_implementation.md](../claudedocs/phase2_5_implementation.md) - Reconciliation

---

## Quick Reference Card

| Want to... | Use this... |
|------------|-------------|
| Install one tool | `install_tool()` |
| Install many tools | `bulk_install()` |
| Check for upgrades | `get_upgrade_candidates()` |
| Upgrade a tool | `upgrade_tool()` |
| Remove duplicates | `reconcile_tool()` |
| Detect environment | `detect_environment()` |
| Load configuration | `load_config()` |
| Generate install plan | `generate_install_plan()` |
| Select package manager | `select_package_manager()` |

---

**Last Updated:** 2025-10-09
**API Stability:** Alpha (subject to changes before 2.0.0 release)
**Detailed Module Docs:** See [phase2_api/](phase2_api/) directory for per-module documentation
