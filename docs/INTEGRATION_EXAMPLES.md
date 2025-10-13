# Integration Examples

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-13

Real-world integration patterns for CLI Audit tool in CI/CD pipelines, development workflows, and custom automation scenarios.

---

## Table of Contents

- [CI/CD Integration](#cicd-integration)
- [Development Workflows](#development-workflows)
- [Custom Toolchain Management](#custom-toolchain-management)
- [Python API Integration](#python-api-integration)
- [Configuration Patterns](#configuration-patterns)
- [Advanced Use Cases](#advanced-use-cases)

---

## CI/CD Integration

### GitHub Actions

**Basic Tool Audit in CI:**

```yaml
# .github/workflows/tool-audit.yml
name: Tool Audit
on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run CLI Audit
        run: |
          python cli_audit.py --format json --output tools.json

      - name: Upload Audit Results
        uses: actions/upload-artifact@v4
        with:
          name: tool-audit
          path: tools.json
```

**Auto-Install Missing Tools:**

```yaml
# .github/workflows/dev-setup.yml
name: Development Setup
on: [push]

jobs:
  setup-tools:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Cache Tool Installations
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/bin
            ~/.local/bin
          key: dev-tools-${{ hashFiles('.cli-audit.yml') }}

      - name: Install Missing Tools
        run: |
          python3 -c "
          from cli_audit import bulk_install, load_config

          config = load_config('.cli-audit.yml')
          result = bulk_install(
              mode='missing',
              config=config,
              max_workers=8,
              verbose=True
          )

          print(f'✅ Installed: {len(result.successes)}')
          print(f'❌ Failed: {len(result.failures)}')

          if result.failures:
              exit(1)
          "

      - name: Verify Installation
        run: |
          rg --version
          fd --version
          hyperfine --version
```

**Tool Version Enforcement:**

```yaml
# .github/workflows/version-check.yml
name: Tool Version Check
on: [pull_request]

jobs:
  version-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check Tool Versions
        run: |
          python3 -c "
          from cli_audit import audit_tools, load_config, generate_snapshot

          config = load_config()
          result = audit_tools(config=config, verbose=True)

          # Check for outdated tools
          outdated = [
              entry for entry in result.entries
              if entry.status == 'version_mismatch'
          ]

          if outdated:
              print('⚠️  Outdated tools detected:')
              for entry in outdated:
                  print(f'  {entry.tool_name}: {entry.found_version} '
                        f'(expected: {entry.expected_version})')
              exit(1)
          "
```

### GitLab CI

**Tool Audit Pipeline:**

```yaml
# .gitlab-ci.yml
stages:
  - audit
  - install
  - test

audit-tools:
  stage: audit
  image: python:3.11-slim
  script:
    - python cli_audit.py --format json --output audit.json
    - python cli_audit.py --format markdown > audit.md
  artifacts:
    paths:
      - audit.json
      - audit.md
    reports:
      dotenv: audit.env

install-missing:
  stage: install
  image: python:3.11-slim
  script:
    - |
      python3 -c "
      from cli_audit import bulk_install, load_config

      config = load_config()
      result = bulk_install(
          mode='missing',
          config=config,
          max_workers=4,
          verbose=True
      )

      if result.failures:
          exit(1)
      "
  cache:
    key: dev-tools-${CI_COMMIT_REF_SLUG}
    paths:
      - .cargo/
      - .local/

verify-tools:
  stage: test
  image: python:3.11-slim
  script:
    - python cli_audit.py --verify-only
```

**Parallel Tool Installation:**

```yaml
# .gitlab-ci.yml
install-rust-tools:
  stage: install
  script:
    - |
      python3 -c "
      from cli_audit import bulk_install, Config, Environment
      from cli_audit.bulk import ToolSpec

      specs = [
          ToolSpec('ripgrep', 'ripgrep', 'latest', 'rust'),
          ToolSpec('fd-find', 'fd-find', 'latest', 'rust'),
          ToolSpec('bat', 'bat', 'latest', 'rust'),
      ]

      result = bulk_install(
          mode='explicit',
          tool_names=[s.tool_name for s in specs],
          max_workers=3,
          verbose=True
      )

      print(result.summary() if hasattr(result, 'summary') else 'Done')
      "
  parallel:
    matrix:
      - TOOL_SET: [rust, python, node]
```

---

## Development Workflows

### Local Development Setup

**One-Command Setup:**

```bash
#!/bin/bash
# scripts/setup-dev-env.sh
# Sets up complete development environment

set -euo pipefail

echo "🚀 Setting up development environment..."

# 1. Audit current tools
python3 cli_audit.py --format compact

# 2. Install missing tools
python3 -c "
from cli_audit import bulk_install, load_config, Environment, detect_environment

env = detect_environment()
config = load_config('.cli-audit.yml')

print(f'Environment: {env.mode} (confidence: {env.confidence:.0%})')

result = bulk_install(
    mode='missing',
    config=config,
    max_workers=8,
    verbose=True
)

print(f'\n✅ Installed: {len(result.successes)}')
for r in result.successes:
    print(f'  • {r.tool_name} v{r.installed_version}')

if result.failures:
    print(f'\n❌ Failed: {len(result.failures)}')
    for r in result.failures:
        print(f'  • {r.tool_name}: {r.error_message}')
    exit(1)
"

echo "✨ Development environment ready!"
```

**Tool Upgrade Script:**

```bash
#!/bin/bash
# scripts/upgrade-tools.sh
# Upgrades all development tools with backup

python3 -c "
from cli_audit import bulk_upgrade, load_config, Environment

config = load_config()

print('🔍 Checking for available upgrades...')

result = bulk_upgrade(
    mode='outdated',
    config=config,
    max_workers=4,
    force=False,  # Prompt for breaking changes
    skip_backup=False,  # Create backups
    verbose=True
)

print(result.summary())

# Show what was upgraded
if result.upgrades:
    print('\n✅ Upgraded:')
    for upgrade in result.upgrades:
        print(f'  • {upgrade.tool_name}: '
              f'{upgrade.previous_version} → {upgrade.new_version}')

# Show rollbacks
if result.rollbacks_executed > 0:
    print(f'\n🔄 Automatic rollbacks: {result.rollbacks_executed}')
"
```

### Pre-Commit Hook

**Tool Version Verification:**

```bash
#!/bin/bash
# .git/hooks/pre-commit
# Verifies required tools are installed and at correct versions

python3 -c "
from cli_audit import audit_tools, load_config

config = load_config()
result = audit_tools(config=config, verbose=False)

# Check for critical tools
critical_tools = {'ruff', 'mypy', 'black', 'pytest'}
missing_critical = [
    entry.tool_name
    for entry in result.entries
    if entry.tool_name in critical_tools and entry.status == 'not_found'
]

if missing_critical:
    print(f'❌ Critical tools missing: {missing_critical}')
    print('Run: python cli_audit.py --install')
    exit(1)

# Check for outdated tools
outdated = [
    entry for entry in result.entries
    if entry.status == 'version_mismatch'
]

if outdated:
    print('⚠️  Warning: Some tools are outdated')
    for entry in outdated:
        print(f'  {entry.tool_name}: {entry.found_version} '
              f'(expected: {entry.expected_version})')
    # Don't block commit, just warn
"
```

### Makefile Integration

```makefile
# Makefile
.PHONY: audit install upgrade verify

# Audit current tool state
audit:
	@python3 cli_audit.py --format compact

# Install missing tools
install:
	@python3 -c "from cli_audit import bulk_install, load_config; \
	config = load_config(); \
	result = bulk_install(mode='missing', config=config); \
	exit(0 if not result.failures else 1)"

# Upgrade all tools
upgrade:
	@python3 -c "from cli_audit import bulk_upgrade, load_config; \
	config = load_config(); \
	result = bulk_upgrade(mode='outdated', config=config, force=False); \
	print(result.summary())"

# Verify tool installation
verify:
	@python3 cli_audit.py --verify-only || \
	(echo "❌ Verification failed. Run 'make install'"; exit 1)

# Full development setup
dev-setup: audit install verify
	@echo "✨ Development environment ready!"
```

---

## Custom Toolchain Management

### Language-Specific Toolchains

**Python Development Tools:**

```python
# scripts/setup-python-tools.py
"""Install Python development toolchain."""

from cli_audit import bulk_install, load_config, Environment
from cli_audit.bulk import ToolSpec

def setup_python_toolchain(verbose: bool = True):
    """Install complete Python development toolchain."""

    # Define Python tool specs
    specs = [
        ToolSpec("ruff", "ruff", "latest", "python"),
        ToolSpec("black", "black", "latest", "python"),
        ToolSpec("mypy", "mypy", "latest", "python"),
        ToolSpec("pytest", "pytest", "latest", "python"),
        ToolSpec("pytest-cov", "pytest-cov", "latest", "python"),
        ToolSpec("ipython", "ipython", "latest", "python"),
    ]

    tool_names = [spec.tool_name for spec in specs]

    result = bulk_install(
        mode="explicit",
        tool_names=tool_names,
        max_workers=6,
        atomic=True,  # Rollback on any failure
        verbose=verbose
    )

    print(f"\n✅ Installed: {len(result.successes)}")
    print(f"❌ Failed: {len(result.failures)}")

    if result.rollback_script:
        print(f"📜 Rollback script: {result.rollback_script}")

    return len(result.failures) == 0

if __name__ == "__main__":
    import sys
    sys.exit(0 if setup_python_toolchain() else 1)
```

**Rust Development Tools:**

```python
# scripts/setup-rust-tools.py
"""Install Rust development toolchain."""

from cli_audit import bulk_install
from cli_audit.bulk import ToolSpec

def setup_rust_toolchain():
    """Install complete Rust development toolchain."""

    specs = [
        ToolSpec("ripgrep", "ripgrep", "latest", "rust"),
        ToolSpec("fd-find", "fd-find", "latest", "rust"),
        ToolSpec("bat", "bat", "latest", "rust"),
        ToolSpec("exa", "exa", "latest", "rust"),
        ToolSpec("hyperfine", "hyperfine", "latest", "rust"),
        ToolSpec("tokei", "tokei", "latest", "rust"),
    ]

    result = bulk_install(
        mode="explicit",
        tool_names=[s.tool_name for s in specs],
        max_workers=6,
        fail_fast=False,  # Continue on failures
        verbose=True
    )

    return result

if __name__ == "__main__":
    result = setup_rust_toolchain()
    print(f"\n{'✅' if not result.failures else '⚠️'} Setup complete")
```

### Multi-Environment Configuration

**Environment-Aware Configuration:**

```yaml
# .cli-audit.yml
version: 1

# Environment detection
environment:
  mode: auto  # auto, ci, server, workstation

# Tool configurations
tools:
  # Core tools (all environments)
  ruff:
    version: ">=0.1.0"
    install_on: [ci, server, workstation]

  mypy:
    version: ">=1.7.0"
    install_on: [ci, server, workstation]

  # Development-only tools
  ipython:
    version: "latest"
    install_on: [workstation]

  hyperfine:
    version: "latest"
    install_on: [workstation]

  # CI-only tools
  pytest-cov:
    version: "latest"
    install_on: [ci]

# Environment-specific preferences
preferences:
  reconciliation: parallel
  breaking_changes: warn  # warn in dev, reject in CI
  auto_upgrade: true
  timeout_seconds: 10
  max_workers: 16

  # Package manager preferences
  package_managers:
    python: [uv, pipx, pip]
    rust: [cargo]
    node: [npm]

# Tool presets
presets:
  python-dev: [ruff, black, mypy, pytest, ipython]
  rust-dev: [ripgrep, fd-find, bat, exa, hyperfine]
  minimal: [ruff, mypy, pytest]
```

**Environment-Specific Installation:**

```python
# scripts/install-by-env.py
"""Install tools based on current environment."""

from cli_audit import (
    bulk_install,
    load_config,
    detect_environment,
)

def install_environment_tools():
    """Install tools appropriate for current environment."""

    # Detect environment
    env = detect_environment()
    config = load_config()

    print(f"Environment: {env.mode} (confidence: {env.confidence:.0%})")
    print(f"Indicators: {', '.join(env.indicators)}")

    # Filter tools by environment
    tools_for_env = []
    for tool_name, tool_config in config.tools.items():
        install_on = getattr(tool_config, 'install_on', ['all'])
        if env.mode in install_on or 'all' in install_on:
            tools_for_env.append(tool_name)

    if not tools_for_env:
        print("No tools to install for this environment")
        return

    print(f"\nInstalling {len(tools_for_env)} tools: {tools_for_env}")

    result = bulk_install(
        mode="explicit",
        tool_names=tools_for_env,
        config=config,
        env=env,
        max_workers=8,
        verbose=True
    )

    print(f"\n✅ Installed: {len(result.successes)}")
    print(f"❌ Failed: {len(result.failures)}")

if __name__ == "__main__":
    install_environment_tools()
```

---

## Python API Integration

### Custom Tool Manager

**Tool Manager Class:**

```python
# tool_manager.py
"""Custom tool manager using CLI Audit API."""

from dataclasses import dataclass
from typing import Sequence
from cli_audit import (
    audit_tools,
    bulk_install,
    bulk_upgrade,
    load_config,
    detect_environment,
    Config,
    Environment,
)
from cli_audit.bulk import ProgressTracker

@dataclass
class ToolManager:
    """High-level tool management interface."""

    config: Config
    env: Environment
    verbose: bool = False

    @classmethod
    def create(cls, config_path: str | None = None, verbose: bool = False):
        """Create tool manager with auto-detection."""
        config = load_config(config_path, verbose=verbose)
        env = detect_environment(verbose=verbose)
        return cls(config=config, env=env, verbose=verbose)

    def audit(self):
        """Audit current tool state."""
        result = audit_tools(config=self.config, verbose=self.verbose)

        print(f"Tool Audit Results:")
        print(f"  ✅ Available: {result.summary['available']}")
        print(f"  ❌ Missing: {result.summary['not_found']}")
        print(f"  ⚠️  Version mismatch: {result.summary['version_mismatch']}")

        return result

    def install_missing(self):
        """Install all missing tools."""
        result = bulk_install(
            mode="missing",
            config=self.config,
            env=self.env,
            max_workers=8,
            verbose=self.verbose
        )

        print(f"\nInstallation Results:")
        print(f"  ✅ Installed: {len(result.successes)}")
        print(f"  ❌ Failed: {len(result.failures)}")

        return result

    def upgrade_all(self, force: bool = False):
        """Upgrade all tools with available updates."""
        result = bulk_upgrade(
            mode="outdated",
            config=self.config,
            env=self.env,
            max_workers=4,
            force=force,
            verbose=self.verbose
        )

        print(result.summary())
        return result

    def install_preset(self, preset_name: str):
        """Install tools from preset."""
        result = bulk_install(
            mode="preset",
            preset_name=preset_name,
            config=self.config,
            env=self.env,
            verbose=self.verbose
        )

        return result

# Example usage
if __name__ == "__main__":
    manager = ToolManager.create(verbose=True)

    # Audit current state
    audit_result = manager.audit()

    # Install missing tools
    if audit_result.summary['not_found'] > 0:
        manager.install_missing()

    # Upgrade outdated tools
    manager.upgrade_all(force=False)
```

### Progress Tracking Integration

**Real-Time Progress Display:**

```python
# progress_example.py
"""Example of real-time progress tracking."""

import time
from cli_audit import bulk_install, load_config
from cli_audit.bulk import ProgressTracker

def print_progress(tool_name: str, status: str, message: str):
    """Progress callback for real-time updates."""
    icons = {
        "pending": "⏳",
        "in_progress": "🔄",
        "success": "✅",
        "failed": "❌",
        "skipped": "⏭️",
    }
    icon = icons.get(status, "❓")
    print(f"{icon} {tool_name}: {status} - {message}")

def install_with_progress():
    """Install tools with real-time progress tracking."""

    # Create progress tracker with callback
    tracker = ProgressTracker()
    tracker.register_callback(print_progress)

    config = load_config()

    print("Starting installation...\n")

    result = bulk_install(
        mode="missing",
        config=config,
        max_workers=4,
        progress_tracker=tracker,
        verbose=False  # Disable verbose to see clean progress
    )

    # Get final summary
    summary = tracker.get_summary()
    print(f"\nFinal Summary:")
    print(f"  Success: {summary['success']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Skipped: {summary['skipped']}")

    return result

if __name__ == "__main__":
    install_with_progress()
```

### Configuration Management

**Dynamic Configuration:**

```python
# config_builder.py
"""Build configuration programmatically."""

from cli_audit.config import Config, Preferences, ToolConfig

def build_config():
    """Build configuration programmatically."""

    # Define preferences
    prefs = Preferences(
        reconciliation="parallel",
        breaking_changes="warn",
        auto_upgrade=True,
        timeout_seconds=10,
        max_workers=16,
        package_managers={
            "python": ["uv", "pipx", "pip"],
            "rust": ["cargo"],
        }
    )

    # Define tools
    tools = {
        "ruff": ToolConfig(version=">=0.1.0", priority=1),
        "mypy": ToolConfig(version=">=1.7.0", priority=1),
        "black": ToolConfig(version="latest", priority=2),
        "pytest": ToolConfig(version="latest", priority=1),
    }

    # Build config
    config = Config(
        version=1,
        environment_mode="auto",
        tools=tools,
        preferences=prefs,
    )

    return config

# Usage
if __name__ == "__main__":
    from cli_audit import bulk_install

    config = build_config()

    result = bulk_install(
        mode="all",
        config=config,
        verbose=True
    )
```

---

## Configuration Patterns

### Minimal Configuration

```yaml
# .cli-audit-minimal.yml
version: 1

tools:
  ruff: {}
  mypy: {}
  pytest: {}

preferences:
  breaking_changes: warn
```

### Comprehensive Configuration

```yaml
# .cli-audit-comprehensive.yml
version: 1

# Environment detection
environment:
  mode: auto

# Tool definitions
tools:
  # Python tools
  ruff:
    version: ">=0.1.0"
    priority: 1
    package_manager: uv

  mypy:
    version: ">=1.7.0"
    priority: 1
    package_manager: pipx

  black:
    version: "latest"
    priority: 2

  pytest:
    version: ">=7.4.0"
    priority: 1

  # Rust tools
  ripgrep:
    version: "latest"
    priority: 2
    package_manager: cargo

  fd-find:
    version: "latest"
    priority: 2

  bat:
    version: "latest"
    priority: 3

# Preferences
preferences:
  reconciliation: parallel
  breaking_changes: warn
  auto_upgrade: true
  timeout_seconds: 10
  max_workers: 16
  cache_ttl_seconds: 3600

  package_managers:
    python: [uv, pipx, pip]
    rust: [cargo]
    node: [npm, pnpm, yarn]

  bulk:
    fail_fast: false
    atomic: false
    retry_failed: true
    max_retries: 3

# Tool presets
presets:
  essential: [ruff, mypy, pytest]
  python-dev: [ruff, mypy, black, pytest, ipython]
  rust-dev: [ripgrep, fd-find, bat, exa]
  full: [ruff, mypy, black, pytest, ripgrep, fd-find, bat]
```

### Multi-Project Configuration

**Project-Specific Configuration:**

```yaml
# project-a/.cli-audit.yml
version: 1

tools:
  ruff:
    version: "0.1.6"  # Pinned version for consistency
  mypy:
    version: "1.7.1"
  pytest:
    version: "7.4.3"

preferences:
  breaking_changes: reject  # Strict for production
```

**User-Level Configuration:**

```yaml
# ~/.config/cli-audit/config.yml
version: 1

# Global preferences
preferences:
  reconciliation: parallel
  breaking_changes: warn
  max_workers: 16

  package_managers:
    python: [uv, pipx, pip]
    rust: [cargo]

# Global tool defaults
tools:
  ruff:
    priority: 1
  mypy:
    priority: 1
```

---

## Advanced Use Cases

### Dependency Resolution

**Tools with Dependencies:**

```python
# install_with_deps.py
"""Install tools with dependency resolution."""

from cli_audit import bulk_install, Config
from cli_audit.bulk import ToolSpec

# Define tools with dependencies
specs = [
    ToolSpec("gcc", "gcc", "latest", dependencies=()),
    ToolSpec("make", "make", "latest", dependencies=("gcc",)),
    ToolSpec("cmake", "cmake", "latest", dependencies=("make", "gcc")),
    ToolSpec("ninja", "ninja", "latest", dependencies=()),
]

# Bulk install will resolve dependencies automatically
result = bulk_install(
    mode="explicit",
    tool_names=[s.tool_name for s in specs],
    verbose=True
)

print(f"Installed in dependency order:")
for success in result.successes:
    print(f"  {success.tool_name} v{success.installed_version}")
```

### Atomic Operations

**All-or-Nothing Installation:**

```python
# atomic_install.py
"""Atomic installation with automatic rollback."""

from cli_audit import bulk_install, load_config

config = load_config()

print("Starting atomic installation...")

result = bulk_install(
    mode="preset",
    preset_name="python-dev",
    config=config,
    atomic=True,  # Rollback everything on any failure
    verbose=True
)

if result.failures:
    print(f"\n❌ Installation failed. All changes rolled back.")
    print(f"Rollback script: {result.rollback_script}")
else:
    print(f"\n✅ All tools installed successfully!")
```

### Reconciliation Strategies

**Parallel Installation Reconciliation:**

```python
# reconcile_example.py
"""Reconcile multiple tool installations."""

from cli_audit import reconcile_tool, Config, load_config

config = load_config()

# Parallel mode: keep all installations
result = reconcile_tool(
    tool_name="python",
    mode="parallel",
    config=config,
    verbose=True
)

print(f"Found {len(result.installations_found)} Python installations:")
for install in result.installations_found:
    print(f"  • {install.version} at {install.path} (via {install.package_manager})")

print(f"\nKept all installations (parallel mode)")
```

**Aggressive Reconciliation:**

```python
# aggressive_reconcile.py
"""Remove duplicate installations."""

from cli_audit import reconcile_tool, Config

result = reconcile_tool(
    tool_name="ripgrep",
    mode="aggressive",  # Remove non-preferred installations
    config=Config(),
    dry_run=False,
    verbose=True
)

print(f"Installations found: {len(result.installations_found)}")
print(f"Preferred: {result.preferred_installation}")
print(f"Removed: {len(result.installations_removed)}")
```

### Breaking Change Management

**Breaking Change Policy:**

```python
# breaking_changes_example.py
"""Handle breaking changes during upgrades."""

from cli_audit import upgrade_tool, Config, load_config

config = load_config()

# Upgrade with breaking change protection
result = upgrade_tool(
    tool_name="ruff",
    target_version="latest",
    config=config,
    force=False,  # Don't force breaking changes
    skip_backup=False,  # Create backup for rollback
    verbose=True
)

if result.breaking_change:
    if result.breaking_change_accepted:
        print(f"✅ Breaking change upgrade: "
              f"{result.previous_version} → {result.new_version}")
    else:
        print(f"❌ Breaking change rejected by policy")

if result.rollback_executed:
    print(f"🔄 Automatic rollback: {'success' if result.rollback_success else 'failed'}")
```

### Custom Package Manager Selection

**Package Manager Hierarchy:**

```python
# pm_selection.py
"""Custom package manager selection logic."""

from cli_audit.package_managers import select_package_manager
from cli_audit.config import Config, Preferences

# Build config with custom PM hierarchy
config = Config(
    version=1,
    preferences=Preferences(
        package_managers={
            "python": ["uv", "pipx", "pip"],  # Try uv first
            "rust": ["cargo"],
            "node": ["pnpm", "npm", "yarn"],
        }
    )
)

# Select PM for Python tool
pm_name, reason = select_package_manager(
    tool_name="ruff",
    language="python",
    config=config,
    verbose=True
)

print(f"Selected: {pm_name}")
print(f"Reason: {reason}")
```

---

## Related Documentation

- **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - Complete API documentation
- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-line reference
- **[ERROR_CATALOG.md](ERROR_CATALOG.md)** - Error reference and troubleshooting
- **[TESTING.md](TESTING.md)** - Testing guide
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture

---

**Last Updated:** 2025-10-13
**Maintainers:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
