# AI CLI Preparation - Complete Project Guide

**Version:** 2.0.0-alpha.6
**Status:** Phase 2 Complete - Ready for Beta
**Last Updated:** 2025-10-09

## 📚 Table of Contents

- [Project Overview](#project-overview)
- [Quick Start](#quick-start)
- [Documentation Hub](#documentation-hub)
- [Phase 1: Audit Tool](#phase-1-audit-tool)
- [Phase 2: Installation Package](#phase-2-installation-package)
- [Development Guide](#development-guide)
- [CI/CD Operations](#cicd-operations)
- [Testing Guide](#testing-guide)
- [Contributing](#contributing)
- [Navigation by Role](#navigation-by-role)

---

## Project Overview

AI CLI Preparation is a **dual-phase** tool for managing CLI tool versions in AI coding agent environments:

**Phase 1:** Fast, offline-first version auditing (cli_audit.py, 2,375 lines)
**Phase 2:** Complete installation management system (cli_audit/ package, 5,338 lines)

### Architecture

```
ai_cli_preparation/
├── cli_audit.py              # Phase 1: Fast audit CLI
├── cli_audit/                # Phase 2: Installation package
│   ├── environment.py        # Environment detection
│   ├── config.py             # Configuration management
│   ├── package_managers.py   # Package manager abstraction
│   ├── install_plan.py       # Installation planning
│   ├── installer.py          # Core installation logic
│   ├── bulk.py               # Parallel bulk operations
│   ├── upgrade.py            # Version management & rollback
│   ├── breaking_changes.py   # Breaking change detection
│   ├── reconcile.py          # Multi-installation conflict resolution
│   ├── logging_config.py     # Logging infrastructure
│   └── common.py             # Shared utilities
├── tests/                    # Comprehensive test suite
│   ├── test_*.py             # 9 unit test modules
│   └── integration/          # End-to-end integration tests
├── scripts/                  # Installation scripts (13+)
├── .github/workflows/        # CI/CD automation
├── docs/                     # Official documentation
└── claudedocs/               # AI agent context
```

### Key Statistics

| Metric | Value |
|--------|-------|
| Production LOC | 12,787 (Phase 1: 2,375 + Phase 2: 5,338 + tests: 4,907) |
| Public API Symbols | 78 exported functions/classes |
| Modules | 11 (Phase 2 package) |
| Test Coverage | 85%+ target, 292 passing tests |
| Documentation | 13 official docs + 6 ADRs + 12 AI context docs |
| Quality Rating | 9.3/10 (Excellent - Production Ready) |

---

## Quick Start

### For End Users (Audit Only)

```bash
# Quick audit
python3 cli_audit.py | column -s '|' -t

# JSON output
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'

# Role-specific preset
python3 cli_audit.py --only agent-core | python3 smart_column.py -s "|" -t --right 3,5 --header
```

→ See [README.md](README.md) for complete user guide

### For Developers (Installation API)

```python
from cli_audit import install_tool, Config, Environment

config = Config()
env = Environment.detect()

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

→ See [README.md - Code Examples](README.md#code-examples) for more examples

### For Contributors

```bash
# Clone and setup
git clone https://github.com/your-org/ai_cli_preparation.git
cd ai_cli_preparation
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest --cov=cli_audit --cov-report=term

# Quality checks
black cli_audit tests
flake8 cli_audit tests
mypy cli_audit
```

→ See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup

---

## Documentation Hub

### Core Documentation (docs/)

#### Technical Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| **[INDEX.md](docs/INDEX.md)** | Documentation index for Phase 1 | All |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System design, data flows, threading | Developers |
| **[API_REFERENCE.md](docs/API_REFERENCE.md)** | Phase 1 API documentation | Developers |
| **[FUNCTION_REFERENCE.md](docs/FUNCTION_REFERENCE.md)** | Quick function lookup | Developers |
| **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** | Common commands cheat sheet | Operators |

#### Implementation Guides

| Document | Purpose | Audience |
|----------|---------|----------|
| **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** | Contributing guide for Phase 1 | Contributors |
| **[TOOL_ECOSYSTEM.md](docs/TOOL_ECOSYSTEM.md)** | 50+ tool catalog | Users/Developers |
| **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Operations & Makefile guide | Operators |
| **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Problem solving guide | All |

#### Planning & Specifications

| Document | Purpose | Audience |
|----------|---------|----------|
| **[PRD.md](docs/PRD.md)** | Product requirements (Phase 1 & 2) | Product/Planning |
| **[PHASE2_IMPLEMENTATION.md](docs/PHASE2_IMPLEMENTATION.md)** | Phase 2 roadmap & milestones | Developers/Planning |
| **[CONFIGURATION_SPEC.md](docs/CONFIGURATION_SPEC.md)** | Config file format reference | Developers |
| **[adr/README.md](docs/adr/README.md)** | Architecture Decision Records (6 ADRs) | Architects |

### Phase 2 Package Documentation

#### API Documentation

**Module Reference:**
```python
# Phase 2.1: Foundation
from cli_audit import (
    Environment, detect_environment, get_environment_from_config,
    Config, ToolConfig, Preferences, BulkPreferences,
    PackageManager, select_package_manager,
    InstallPlan, InstallStep, generate_install_plan,
)

# Phase 2.2: Core Installation
from cli_audit import (
    InstallResult, StepResult, InstallError,
    install_tool, execute_step, execute_step_with_retry,
    verify_checksum, validate_installation,
)

# Phase 2.3: Bulk Operations
from cli_audit import (
    ToolSpec, ProgressTracker, BulkInstallResult,
    bulk_install, get_missing_tools, resolve_dependencies,
    generate_rollback_script, execute_rollback,
)

# Phase 2.4: Upgrade Management
from cli_audit import (
    UpgradeBackup, UpgradeResult, UpgradeCandidate,
    BulkUpgradeResult, compare_versions,
    get_available_version, check_upgrade_available,
    upgrade_tool, bulk_upgrade, get_upgrade_candidates,
    create_upgrade_backup, restore_from_backup,
)

# Phase 2.5: Reconciliation
from cli_audit import (
    Installation, ReconciliationResult,
    BulkReconciliationResult, detect_installations,
    reconcile_tool, bulk_reconcile, verify_path_ordering,
    SYSTEM_TOOL_SAFELIST,
)

# Breaking Changes
from cli_audit import (
    is_major_upgrade, check_breaking_change_policy,
    confirm_breaking_change, filter_by_breaking_changes,
)

# Logging
from cli_audit import setup_logging, get_logger
```

**78 public API symbols organized across 8 functional domains**

#### Phase-Specific Documentation

| Phase | Document | Purpose |
|-------|----------|---------|
| 2.1 | [claudedocs/phase2_1_implementation.md](claudedocs/phase2_1_implementation.md) | Foundation: Environment, Config, Package Managers |
| 2.2 | [claudedocs/phase2_2_implementation.md](claudedocs/phase2_2_implementation.md) | Core Installation: Single tool with retry |
| 2.3 | [claudedocs/phase2_3_implementation.md](claudedocs/phase2_3_implementation.md) | Bulk Operations: Parallel installation |
| 2.4 | [claudedocs/phase2_4_implementation.md](claudedocs/phase2_4_implementation.md) | Upgrade Management: Version control |
| 2.5 | [claudedocs/phase2_5_implementation.md](claudedocs/phase2_5_implementation.md) | Reconciliation: Conflict resolution |
| 2.6 | [claudedocs/phase2_6_logging_implementation.md](claudedocs/phase2_6_logging_implementation.md) | Logging Framework |
| - | [claudedocs/phase2_completion_report.md](claudedocs/phase2_completion_report.md) | **Phase 2 Completion Status** |

### AI Agent Context (claudedocs/)

| Document | Purpose |
|----------|---------|
| [comprehensive_code_review.md](claudedocs/comprehensive_code_review.md) | Complete quality assessment (9.3/10) |
| [project_context.md](claudedocs/project_context.md) | Project structure & context |
| [session_initialization.md](claudedocs/session_initialization.md) | Session setup patterns |

---

## Phase 1: Audit Tool

**File:** `cli_audit.py` (2,375 lines)

### Purpose

Fast, offline-first CLI tool version auditing with upstream version checking.

### Key Features

- Detects installed versions across PATH
- Fetches latest upstream versions (GitHub, PyPI, crates.io, npm)
- Snapshot-based workflow (collect/render separation)
- Offline mode with manual cache fallback
- JSON and table output formats
- 50+ tools across 9 categories

### Documentation

- **User Guide:** [README.md](README.md)
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Reference:** [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Tool Catalog:** [docs/TOOL_ECOSYSTEM.md](docs/TOOL_ECOSYSTEM.md)

### Quick Commands

```bash
# Update snapshot
make update

# Render from snapshot (offline)
make audit

# Auto-update if needed
make audit-auto

# JSON mode
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'

# Offline mode
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

---

## Phase 2: Installation Package

**Package:** `cli_audit/` (5,338 lines across 11 modules)

### Purpose

Complete tool installation, upgrade, and conflict resolution system.

### Module Architecture

#### Phase 2.1: Foundation

**environment.py** (177 lines)
- `Environment` dataclass: system environment detection
- `detect_environment()`: auto-detect workstation/CI/server
- `get_environment_from_config()`: environment from config

**config.py** (447 lines)
- `Config`, `ToolConfig`, `Preferences`, `BulkPreferences` dataclasses
- YAML configuration file parsing
- Multi-source config merging (project → user → system → defaults)
- Configuration validation

**package_managers.py** (428 lines)
- `PackageManager` enum: cargo, pipx, uv, npm, pip, etc.
- `select_package_manager()`: intelligent PM selection
- `get_available_package_managers()`: detect available PMs
- Language-specific hierarchies

**install_plan.py** (348 lines)
- `InstallPlan`, `InstallStep` dataclasses
- `generate_install_plan()`: create installation plan
- `dry_run_install()`: simulate installation

#### Phase 2.2: Core Installation

**installer.py** (559 lines)
- `install_tool()`: single tool installation with retry
- `execute_step()`: execute installation step
- `execute_step_with_retry()`: retry with exponential backoff
- `verify_checksum()`: SHA256 binary verification
- `validate_installation()`: post-install validation

#### Phase 2.3: Bulk Operations

**bulk.py** (613 lines)
- `bulk_install()`: parallel installation (ThreadPoolExecutor)
- `get_missing_tools()`: detect missing tools
- `resolve_dependencies()`: topological sort for dependencies
- `generate_rollback_script()`: create rollback script
- `ProgressTracker`: thread-safe progress tracking

#### Phase 2.4: Upgrade Management

**upgrade.py** (1,149 lines → ~970 after breaking_changes extraction)
- `upgrade_tool()`: single tool upgrade with backup
- `bulk_upgrade()`: parallel upgrades
- `get_upgrade_candidates()`: detect available upgrades
- `compare_versions()`: semantic version comparison
- `check_upgrade_available()`: cached version checking
- `create_upgrade_backup()`, `restore_from_backup()`: backup/restore

**breaking_changes.py** (183 lines) - **NEW**
- `is_major_upgrade()`: detect breaking changes
- `check_breaking_change_policy()`: enforce policy
- `confirm_breaking_change()`: user confirmation
- `filter_by_breaking_changes()`: policy-based filtering

#### Phase 2.5: Reconciliation

**reconcile.py** (1,090 lines)
- `reconcile_tool()`: resolve multiple installations
- `bulk_reconcile()`: parallel reconciliation
- `detect_installations()`: find all installations
- `classify_install_method()`: identify installation method
- `verify_path_ordering()`: check PATH ordering
- `SYSTEM_TOOL_SAFELIST`: 26 protected system tools

#### Shared Infrastructure

**logging_config.py** (177 lines)
- `setup_logging()`: configure logging
- `get_logger()`: retrieve module logger
- Log levels, handlers, formatters

**common.py** (127 lines)
- `vlog()`: verbose logging utility
- Shared helper functions

### Documentation

- **Phase 2.1:** [claudedocs/phase2_1_implementation.md](claudedocs/phase2_1_implementation.md)
- **Phase 2.2:** [claudedocs/phase2_2_implementation.md](claudedocs/phase2_2_implementation.md)
- **Phase 2.3:** [claudedocs/phase2_3_implementation.md](claudedocs/phase2_3_implementation.md)
- **Phase 2.4:** [claudedocs/phase2_4_implementation.md](claudedocs/phase2_4_implementation.md)
- **Phase 2.5:** [claudedocs/phase2_5_implementation.md](claudedocs/phase2_5_implementation.md)
- **Completion:** [claudedocs/phase2_completion_report.md](claudedocs/phase2_completion_report.md)
- **Code Review:** [claudedocs/comprehensive_code_review.md](claudedocs/comprehensive_code_review.md)

---

## Development Guide

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/ai_cli_preparation.git
cd ai_cli_preparation

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
# OR
pip install -r requirements-dev.txt
```

### Development Dependencies

**Testing:**
- pytest, pytest-cov, pytest-mock, pytest-xdist

**Linting & Type Checking:**
- flake8, mypy, bandit

**Code Quality:**
- black, isort

**Build & Distribution:**
- build, twine

**Security:**
- safety

**Documentation:**
- markdown, PyYAML

→ See [requirements-dev.txt](requirements-dev.txt) for versions

### Code Quality Workflow

```bash
# Format code
black cli_audit tests
isort cli_audit tests

# Lint
flake8 cli_audit tests

# Type check
mypy cli_audit

# Security scan
bandit -r cli_audit
safety check

# Run tests
pytest --cov=cli_audit --cov-report=term --cov-report=html

# Parallel tests
pytest -n auto
```

### Configuration Files

| File | Purpose |
|------|---------|
| [pyproject.toml](pyproject.toml) | Package metadata, black, isort, pytest, mypy config |
| [.flake8](.flake8) | Linting rules (max line 127, ignores) |
| [mypy.ini](mypy.ini) | Type checking configuration |
| [pytest.ini](pytest.ini) | Test discovery and coverage config |

---

## CI/CD Operations

### GitHub Actions Workflows

#### CI Pipeline (.github/workflows/ci.yml)

**Triggers:** Push/PR to main/develop

**Jobs:**

1. **Lint & Type Check**
   - flake8 (syntax, style)
   - mypy (type checking)

2. **Test Matrix**
   - OS: Ubuntu, macOS, Windows
   - Python: 3.9, 3.10, 3.11, 3.12
   - Coverage upload to Codecov

3. **Security Scan**
   - bandit (code security)
   - safety (dependency security)

4. **Build Distribution**
   - Build wheel and sdist
   - Validate with twine

5. **Documentation Check**
   - README validation
   - YAML config validation

6. **E2E Integration**
   - CLI execution test
   - API import test

#### Release Pipeline (.github/workflows/release.yml)

**Triggers:** Version tags (v*.*.*)

**Jobs:**

1. **Build**
   - Create distribution packages

2. **Create Release**
   - GitHub release with changelog
   - Attach distribution artifacts

3. **Publish to PyPI**
   - Automated PyPI publishing
   - Test PyPI support (manual trigger)

#### Dependabot (.github/dependabot.yml)

- Weekly Python dependency updates
- Weekly GitHub Actions updates
- Auto-PR with labels

### CI/CD Documentation

→ See [CONTRIBUTING.md - CI/CD](CONTRIBUTING.md#continuous-integration) for details

---

## Testing Guide

### Test Structure

```
tests/
├── __init__.py
├── fixtures/                 # Shared test fixtures
├── test_config.py            # Configuration tests
├── test_environment.py       # Environment detection
├── test_package_managers.py  # Package manager selection
├── test_install_plan.py      # Plan generation
├── test_installer.py         # Installation execution (669 lines)
├── test_bulk.py              # Parallel operations
├── test_upgrade.py           # Version management
├── test_reconcile.py         # Conflict resolution
├── test_logging.py           # Logging infrastructure
└── integration/
    ├── __init__.py
    └── test_e2e_install.py   # End-to-end workflows (360 lines)
```

### Test Statistics

- **Total Tests:** 292 passing, 1 skipped
- **Test LOC:** 4,907 lines
- **Coverage Target:** 85%+
- **Test Files:** 10 (9 unit + 1 integration)

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=cli_audit --cov-report=term --cov-report=html

# Specific file
pytest tests/unit/test_config.py

# Parallel execution
pytest -n auto

# Verbose
pytest -v

# Stop on first failure
pytest -x
```

### Integration Tests

**Location:** `tests/integration/test_e2e_install.py`

**Test Classes:**
- `TestSingleToolInstallation`: Python/Rust tool installation
- `TestBulkInstallation`: Parallel operations, fail-fast
- `TestDependencyResolution`: Dependency graph resolution
- `TestRollbackScenarios`: Atomic rollback
- `TestConfigurationIntegration`: Config merging

---

## Contributing

### Quick Contribution Workflow

1. **Fork & Clone**
   ```bash
   git clone https://github.com/your-username/ai_cli_preparation.git
   cd ai_cli_preparation
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

4. **Quality Checks**
   ```bash
   black cli_audit tests
   isort cli_audit tests
   flake8 cli_audit tests
   pytest --cov=cli_audit
   ```

5. **Commit & Push**
   ```bash
   git add -A
   git commit -m "feat: your feature description"
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Provide clear description
   - Reference related issues
   - Ensure CI passes

### Contribution Guidelines

→ See [CONTRIBUTING.md](CONTRIBUTING.md) for comprehensive guide covering:
- Development setup
- Code style guidelines
- Testing requirements
- Documentation standards
- PR process
- Release process

---

## Navigation by Role

### 🎯 For End Users

**Goal:** Use the audit tool to check CLI versions

1. Start: [README.md](README.md)
2. Quick reference: [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
3. Tool catalog: [docs/TOOL_ECOSYSTEM.md](docs/TOOL_ECOSYSTEM.md)
4. Operations: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
5. Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

### 💻 For Developers (Using Phase 2 API)

**Goal:** Integrate installation management in your code

1. Start: [README.md - Code Examples](README.md#code-examples)
2. API overview: This guide - [Phase 2: Installation Package](#phase-2-installation-package)
3. Phase docs: [claudedocs/phase2_*_implementation.md](claudedocs/)
4. Configuration: [docs/CONFIGURATION_SPEC.md](docs/CONFIGURATION_SPEC.md)

### 🔧 For Contributors

**Goal:** Contribute code to the project

1. Start: [CONTRIBUTING.md](CONTRIBUTING.md)
2. Setup: [Development Guide](#development-guide) (this doc)
3. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
4. Code review: [claudedocs/comprehensive_code_review.md](claudedocs/comprehensive_code_review.md)
5. Testing: [Testing Guide](#testing-guide) (this doc)

### 🏗️ For Maintainers/Architects

**Goal:** Understand system design and maintain quality

1. Start: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
2. ADRs: [docs/adr/README.md](docs/adr/README.md)
3. Phase 2 report: [claudedocs/phase2_completion_report.md](claudedocs/phase2_completion_report.md)
4. Code review: [claudedocs/comprehensive_code_review.md](claudedocs/comprehensive_code_review.md)
5. CI/CD: [CI/CD Operations](#cicd-operations) (this doc)

### 📦 For DevOps/Operators

**Goal:** Deploy and operate the tool

1. Start: [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
2. Deployment: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
3. Scripts: [scripts/README.md](scripts/README.md)
4. Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
5. CI/CD: [CI/CD Operations](#cicd-operations) (this doc)

### 🤖 For AI Coding Agents

**Goal:** Understand project context for assistance

1. Start: [claudedocs/project_context.md](claudedocs/project_context.md)
2. Session init: [claudedocs/session_initialization.md](claudedocs/session_initialization.md)
3. Phase completion: [claudedocs/phase2_completion_report.md](claudedocs/phase2_completion_report.md)
4. Code review: [claudedocs/comprehensive_code_review.md](claudedocs/comprehensive_code_review.md)
5. API surface: [Phase 2: Installation Package](#phase-2-installation-package) (this doc)

### 📊 For Product/Planning

**Goal:** Understand roadmap and requirements

1. Start: [docs/PRD.md](docs/PRD.md)
2. Phase 2 plan: [docs/PHASE2_IMPLEMENTATION.md](docs/PHASE2_IMPLEMENTATION.md)
3. ADRs: [docs/adr/README.md](docs/adr/README.md)
4. Completion: [claudedocs/phase2_completion_report.md](claudedocs/phase2_completion_report.md)

---

## Additional Resources

### External Links

- **Repository:** https://github.com/your-org/ai_cli_preparation
- **Claude Code:** https://www.npmjs.com/package/@anthropic-ai/claude-code
- **Issues:** https://github.com/your-org/ai_cli_preparation/issues

### Related Documentation

- [README.md](README.md) - User-focused guide
- [docs/INDEX.md](docs/INDEX.md) - Phase 1 documentation index
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contributor guide
- [scripts/README.md](scripts/README.md) - Installation scripts guide

---

## Document Status

**Created:** 2025-10-09
**Purpose:** Master navigation guide for complete project (Phase 1 + Phase 2)
**Audience:** All roles (developers, users, contributors, operators, AI agents)
**Maintenance:** Update when adding new modules, phases, or major features

**Feedback:** Documentation improvements welcome! Please update this guide when:
- Adding new Phase 2 modules
- Creating new documentation files
- Implementing Phase 3 features
- Updating CI/CD workflows

---

**🚀 Ready to get started?** Choose your role above and follow the navigation path!
