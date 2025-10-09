# Configuration Specification - AI CLI Preparation

**Version:** 1.0
**Last Updated:** 2025-10-09
**Status:** Specification (Phase 2)

## Overview

AI CLI Preparation uses YAML configuration files to control installation behavior, package manager preferences, version constraints, and environment-specific settings. Configuration files enable:

- Environment mode overrides (workstation, server, CI)
- Package manager hierarchy customization
- Per-tool version locking and method selection
- Reconciliation strategies and breaking change policies
- Custom role presets and global preferences

**Design Philosophy:**
- Human-readable and easy to edit
- Multi-location precedence (project → user → system)
- Schema validation for early error detection
- Sensible defaults requiring minimal configuration

---

## File Locations and Precedence

AI CLI Preparation loads configuration from multiple locations in precedence order:

```
1. ./.cli-audit.yml               # Project-local (highest priority)
2. ~/.config/cli-audit/config.yml  # User-global
3. /etc/cli-audit/config.yml       # System-global (lowest priority)
```

**Precedence Rules:**
- **Project overrides User overrides System**: Settings merge hierarchically
- **Per-setting granularity**: Each configuration field merges independently
- **Explicit wins over default**: Any explicitly set value overrides defaults
- **Missing files ignored**: Absent configuration files are skipped silently

**Merge Behavior Example:**

```yaml
# System: /etc/cli-audit/config.yml
environment:
  mode: server
preferences:
  breaking_changes: reject
  auto_upgrade: false

# User: ~/.config/cli-audit/config.yml
preferences:
  breaking_changes: warn  # Overrides system

# Project: ./.cli-audit.yml
environment:
  mode: workstation  # Overrides system
tools:
  python:
    version: "3.11.*"  # Project-specific

# Effective Configuration (merged result):
environment:
  mode: workstation       # From project
preferences:
  breaking_changes: warn  # From user
  auto_upgrade: false     # From system
tools:
  python:
    version: "3.11.*"     # From project
```

**Use Cases by Location:**

| Location | Use Case | Example |
|----------|----------|---------|
| **System** (`/etc/cli-audit/config.yml`) | Organization-wide policies, shared server defaults | Force server mode, reject breaking changes |
| **User** (`~/.config/cli-audit/config.yml`) | Personal preferences across all projects | Prefer `uv` for Python, 32 parallel workers |
| **Project** (`./.cli-audit.yml`) | Project-specific requirements | Lock Node.js to 20.x, exact Python version |

---

## Schema Reference

### Schema Version

```yaml
version: 1  # Required, integer
```

**Description:** Configuration schema version for backward compatibility

**Type:** `integer`
**Required:** Yes
**Default:** N/A (must be explicitly set)
**Valid Values:** `1` (current schema version)

**Purpose:** Allows tool to handle configuration format changes gracefully across versions

---

### Environment Mode

```yaml
environment:
  mode: auto  # auto | workstation | server | ci
```

**Description:** Override automatic environment detection

**Fields:**
- `mode`: Environment type controlling installation behavior

**Type:** `string` (enum)
**Required:** No
**Default:** `auto` (automatic detection)
**Valid Values:**
- `auto`: Detect environment based on system characteristics (recommended)
- `workstation`: Single-user development system (laptops, desktops)
- `server`: Multi-user shared development server
- `ci`: CI/CD environment (ephemeral, reproducible builds)

**Mode Behaviors:**

| Aspect | Workstation | Server | CI |
|--------|-------------|--------|-----|
| **Install Scope** | User (`~/.local/bin`) | System (`/usr/local/bin`) | Minimal (project) |
| **Preferred Methods** | Vendor tools (rustup, nvm, uv) | System packages (apt, brew) | Cache/snapshot |
| **Reconciliation** | Parallel (keep both) | Advisory locks (coordinate) | Replace (clean slate) |
| **Breaking Changes** | Accept (always latest) | Warn (manual approval) | Lock (exact versions) |
| **Auto-Upgrade** | Enabled | Disabled | Disabled |

**Examples:**

```yaml
# Auto-detect (recommended)
environment:
  mode: auto

# Force workstation behavior on shared server
environment:
  mode: workstation

# Explicit CI mode for containerized builds
environment:
  mode: ci
```

---

### Global Preferences

```yaml
preferences:
  reconciliation: parallel     # parallel | aggressive
  breaking_changes: warn       # accept | warn | reject
  auto_upgrade: true           # boolean
  timeout_seconds: 5           # integer (1-60)
  max_workers: 16              # integer (1-64)

  # Package manager hierarchy override
  package_managers:
    python: [uv, pipx, pip]
    rust: [rustup, cargo, system]
    node: [nvm, npm, system]
```

**Description:** Global settings affecting all tools

#### `reconciliation`

**Description:** Strategy for handling multiple installations of the same tool

**Type:** `string` (enum)
**Default:** `parallel`
**Valid Values:**
- `parallel`: Keep multiple installations, prefer user-level via PATH ordering (safe)
- `aggressive`: Remove non-preferred installations (requires confirmation)

**Behavior:**

**Parallel Mode (Recommended):**
```
Found ripgrep installations:
  ✓ 14.1.1 (cargo, ~/.cargo/bin) [ACTIVE]
  ℹ️  14.0.0 (apt, /usr/bin) [INACTIVE]

Action: Keep both
  - User version takes precedence (PATH: ~/.cargo/bin first)
  - System version preserved for other users/scripts
  - Manual removal available via: cli_audit reconcile --aggressive
```

**Aggressive Mode:**
```
Found ripgrep installations:
  ✓ 14.1.1 (cargo, ~/.cargo/bin) [PREFERRED]
  ✗ 14.0.0 (apt, /usr/bin) [WILL REMOVE]

Action: Remove non-preferred
  ⚠️  Requires confirmation (may break system dependencies)
  💡 Use parallel mode if unsure
```

#### `breaking_changes`

**Description:** Policy for major version upgrades with potential breaking changes

**Type:** `string` (enum)
**Default:** `warn` (recommended)
**Valid Values:**
- `accept`: Auto-upgrade major versions without prompts (risky)
- `warn`: Prompt user for major upgrades, auto-upgrade minor/patch (safe)
- `reject`: Never upgrade major versions automatically (conservative)

**Behavior:**

**Accept (Workstation Default):**
```
Upgrading python: 3.11.5 → 3.12.1
  ℹ️  Major version upgrade (breaking changes possible)
  ⚡ Auto-upgrading (accept policy)
```

**Warn (Recommended):**
```
⚠️  Major version upgrade detected:
    Tool: python
    Current: 3.11.5
    Latest: 3.12.1

Potential breaking changes:
  - Removed deprecated APIs (PEP 594)
  - F-string syntax changes
  - Type inference improvements

Proceed with upgrade? [y/N]
```

**Reject (Server Default):**
```
❌ Major version upgrade blocked:
   Tool: python 3.11.5 → 3.12.1
   Policy: reject (server mode)

   To upgrade: Update configuration or use --force
```

#### `auto_upgrade`

**Description:** Automatically upgrade minor/patch versions without prompts

**Type:** `boolean`
**Default:** `true` (workstation), `false` (server/CI)
**Valid Values:** `true`, `false`

**Behavior:**
- `true`: Auto-upgrade 3.11.4 → 3.11.5 (patch) or 3.11.x → 3.12.x (minor if breaking_changes allows)
- `false`: Require explicit upgrade command for all version changes

#### `timeout_seconds`

**Description:** Network timeout for upstream version queries

**Type:** `integer`
**Default:** `3`
**Range:** 1-60 seconds
**Valid Values:** Any integer in range

**Use Cases:**
- Increase for slow networks or CI environments
- Decrease for fast networks to fail faster

#### `max_workers`

**Description:** Maximum parallel workers for concurrent operations

**Type:** `integer`
**Default:** `16`
**Range:** 1-64 workers
**Valid Values:** Any integer in range

**Recommendations:**
- **Low-power systems**: 4-8 workers
- **Developer laptops**: 16 workers (default)
- **High-performance servers**: 32-64 workers

#### `package_managers`

**Description:** Override default package manager hierarchy per language/ecosystem

**Type:** `object` (nested)
**Default:** See "Package Manager Hierarchy" section
**Structure:**

```yaml
package_managers:
  python: [method1, method2, method3]
  rust: [method1, method2]
  node: [method1, method2]
```

**Default Hierarchies:**
- `python`: `[uv, pipx, pip, system]`
- `rust`: `[rustup, cargo, system]`
- `node`: `[nvm, npm, system]`
- `go`: `[go, system]`

**Example Overrides:**

```yaml
# Prefer pipx over uv for Python
preferences:
  package_managers:
    python: [pipx, uv, pip]

# Use system packages only (conservative server)
preferences:
  package_managers:
    python: [system]
    rust: [system]
    node: [system]

# GitHub releases preferred for Rust CLI tools
preferences:
  package_managers:
    rust: [github, cargo, system]
```

---

### Per-Tool Configuration

```yaml
tools:
  <tool_name>:
    version: "latest"      # string (SemVer range or "latest")
    method: <method>       # string (package manager name)
    fallback: <method>     # string (optional)
    auto_upgrade: true     # boolean (overrides global)
```

**Description:** Tool-specific settings overriding global preferences

**Structure:**

```yaml
tools:
  python:
    version: "3.12.*"      # Lock to Python 3.12.x
    method: uv             # Prefer uv
    fallback: pipx         # Use pipx if uv unavailable

  ripgrep:
    version: "latest"      # Always latest
    method: cargo          # Install via cargo

  node:
    version: "=20.10.0"    # Exact version lock
    method: nvm            # Use nvm for version management

  black:
    version: ">=23.0.0"    # Minimum version
    method: pipx           # Isolated installation
    auto_upgrade: false    # Don't auto-upgrade (override global)
```

**Field Descriptions:**

#### `version`

**Description:** Version constraint for tool (SemVer range)

**Type:** `string`
**Default:** `latest`
**Valid Formats:** See "Version Specification Syntax" section

#### `method`

**Description:** Preferred installation method (package manager)

**Type:** `string`
**Valid Values:** Depends on tool ecosystem (see "Installation Methods" section)

#### `fallback`

**Description:** Alternative method if preferred method unavailable

**Type:** `string` (optional)
**Default:** Next method in package manager hierarchy

#### `auto_upgrade`

**Description:** Override global auto_upgrade preference for this tool

**Type:** `boolean` (optional)
**Default:** Inherits from `preferences.auto_upgrade`

---

### Custom Presets

```yaml
presets:
  <preset_name>:
    - tool1
    - tool2
    - tool3
```

**Description:** Named groups of tools for bulk operations

**Type:** `object` (tool lists)
**Default:** Built-in presets (agent-core, python-core, etc.)

**Built-in Presets:**
- `agent-core`: Essential tools for AI coding agents (20+ tools)
- `python-core`: Python development stack
- `rust-core`: Rust development stack
- `security-core`: Security scanning tools
- `cloud-core`: Cloud infrastructure tools

**Custom Preset Examples:**

```yaml
presets:
  my-python-stack:
    - python
    - uv
    - black
    - ruff
    - pyright
    - pytest
    - mypy

  my-rust-stack:
    - rust
    - cargo
    - ripgrep
    - fd
    - bat
    - delta

  my-frontend-stack:
    - node
    - npm
    - prettier
    - eslint
    - typescript
```

**Usage:**

```bash
# Install all tools from preset
cli_audit install --preset my-python-stack

# Upgrade preset tools only
cli_audit upgrade --preset my-rust-stack
```

---

### Snapshot Configuration

```yaml
snapshot:
  path: tools_snapshot.json  # string (file path)
  strict: true               # boolean
```

**Description:** Snapshot-based installation for CI/CD reproducibility

**Fields:**

#### `path`

**Description:** Path to snapshot file (relative or absolute)

**Type:** `string`
**Default:** `tools_snapshot.json`

#### `strict`

**Description:** Fail if snapshot versions unavailable (vs fallback to latest)

**Type:** `boolean`
**Default:** `true` (CI mode), `false` (other modes)

**CI Usage Example:**

```yaml
# .cli-audit.yml (CI environment)
version: 1
environment:
  mode: ci

snapshot:
  path: tools_snapshot.json
  strict: true  # Fail if exact versions unavailable

preferences:
  breaking_changes: reject  # Enforce exact versions
  auto_upgrade: false       # No upgrades
```

**Snapshot Workflow:**

```bash
# Generate snapshot (developer workstation)
cli_audit snapshot create

# Commit snapshot to version control
git add tools_snapshot.json
git commit -m "Lock tool versions for CI"

# CI pipeline uses snapshot
cli_audit install --from-snapshot tools_snapshot.json
```

---

## Version Specification Syntax

AI CLI Preparation supports SemVer-style version constraints for flexible version management.

### Version Formats

| Format | Meaning | Example Matches | Example Non-Matches |
|--------|---------|-----------------|---------------------|
| `latest` | Always latest available | Current: 14.1.1 | N/A (always resolves) |
| `3.12.*` | Any 3.12.x | 3.12.0, 3.12.5 | 3.11.9, 3.13.0 |
| `>=3.11` | 3.11.0 or higher | 3.11.0, 3.12.1 | 3.10.9 |
| `^3.11` | 3.11.x (caret: minor) | 3.11.0, 3.11.9 | 3.10.x, 3.12.x |
| `~3.11.0` | 3.11.x (tilde: patch) | 3.11.0, 3.11.5 | 3.12.0 |
| `=3.11.5` | Exact version only | 3.11.5 | 3.11.4, 3.11.6 |
| `>3.11,<3.13` | Range (AND) | 3.12.0, 3.12.9 | 3.11.x, 3.13.x |

### Detailed Syntax

#### `latest` (Recommended Default)

**Description:** Always resolve to latest available version

**Use Cases:**
- Workstation development (maximize features/fixes)
- Tools with stable APIs (ripgrep, fd, bat)
- Non-critical tools (exploratory use)

**Example:**

```yaml
tools:
  ripgrep:
    version: "latest"  # Always 14.1.1 (or newer when released)
```

#### `*` (Wildcard)

**Description:** Match any version component

**Syntax:**
- `3.12.*`: Any 3.12.x (3.12.0, 3.12.1, 3.12.99)
- `3.*.*`: Any 3.x.x (3.0.0, 3.11.5, 3.99.99)

**Use Cases:**
- Lock major version (e.g., Python 3.x)
- Lock major.minor (e.g., Python 3.12.x)

**Example:**

```yaml
tools:
  python:
    version: "3.12.*"  # Lock to Python 3.12 series
  node:
    version: "20.*"    # Lock to Node.js 20.x
```

#### `>=`, `>`, `<=`, `<` (Comparison Operators)

**Description:** Version comparisons

**Syntax:**
- `>=3.11`: 3.11.0 or higher (inclusive)
- `>3.11`: Greater than 3.11.x (exclusive)
- `<=3.12`: 3.12.x or lower (inclusive)
- `<3.13`: Lower than 3.13.0 (exclusive)

**Use Cases:**
- Minimum version requirements (e.g., `>=23.0.0` for black)
- Exclude known-broken versions

**Example:**

```yaml
tools:
  black:
    version: ">=23.0.0"  # Require v23 or newer (f-string improvements)
```

#### `^` (Caret: Compatible Minor Versions)

**Description:** Allow minor and patch updates, lock major version

**Syntax:**
- `^3.11`: Allows 3.11.x, 3.12.x, ... 3.x.x (not 4.0.0)
- `^1.2.3`: Allows 1.2.3, 1.2.4, 1.3.0, 1.99.99 (not 2.0.0)

**Use Cases:**
- Semantic versioning compliance (no breaking changes in minor)
- Balance stability and updates

**Example:**

```yaml
tools:
  ruff:
    version: "^0.1"  # Allow 0.1.x, 0.2.x (not 1.0.0)
```

#### `~` (Tilde: Compatible Patch Versions)

**Description:** Allow patch updates only, lock major.minor

**Syntax:**
- `~3.11.0`: Allows 3.11.0, 3.11.1, ... 3.11.x (not 3.12.0)
- `~1.2.3`: Allows 1.2.3, 1.2.4, 1.2.99 (not 1.3.0)

**Use Cases:**
- Maximum stability (bug fixes only)
- Production environments

**Example:**

```yaml
tools:
  python:
    version: "~3.11.0"  # Allow 3.11.x patches (not 3.12)
```

#### `=` (Exact Version Lock)

**Description:** Exact version only, no flexibility

**Syntax:**
- `=3.11.5`: Only 3.11.5 (not 3.11.4 or 3.11.6)

**Use Cases:**
- CI/CD reproducibility
- Known-good versions
- Regression testing

**Example:**

```yaml
tools:
  node:
    version: "=20.10.0"  # Exact lock (CI reproducibility)
```

#### Range Expressions

**Description:** Combine constraints with commas (AND logic)

**Syntax:**
- `>3.11,<3.13`: Greater than 3.11, less than 3.13
- `>=3.11.0,<3.12.0`: 3.11.x only

**Use Cases:**
- Exclude specific major versions
- Narrow compatibility ranges

**Example:**

```yaml
tools:
  python:
    version: ">=3.11,<3.13"  # 3.11.x or 3.12.x (not 3.13+)
```

### Version Selection Logic

When multiple matching versions exist, AI CLI Preparation selects versions using this logic:

1. **Filter by constraint**: Apply version specification to available versions
2. **Select latest match**: Choose newest version satisfying constraint
3. **Warn on major upgrade**: If major version change, apply `breaking_changes` policy
4. **Install selected**: Execute installation with selected version

**Example:**

```yaml
tools:
  python:
    version: "3.12.*"

# Available upstream: 3.11.9, 3.12.0, 3.12.1, 3.12.2, 3.13.0
# Filter: 3.12.0, 3.12.1, 3.12.2 (matches 3.12.*)
# Select: 3.12.2 (latest match)
# Install: python 3.12.2
```

---

## Installation Methods

AI CLI Preparation supports multiple installation methods with automatic fallback.

### Method Hierarchy (Default)

**Preference Order:** Vendor → GitHub → System

1. **Vendor-Specific Tools** (Highest Priority)
   - Best version management, user isolation, no conflicts
   - Examples: uv, pipx, rustup, nvm, go install

2. **GitHub Releases** (Medium Priority)
   - Latest versions, standalone binaries, no dependencies
   - Examples: Standalone tools (fd, ripgrep, bat)

3. **System Package Managers** (Lowest Priority)
   - Slower updates, system-wide impact, potential conflicts
   - Examples: apt, brew, pacman, yum

### Per-Ecosystem Methods

#### Python Ecosystem

| Method | Priority | Description | Use Cases |
|--------|----------|-------------|-----------|
| `uv` | 1 | Fast Python package manager | Preferred (fastest) |
| `pipx` | 2 | Isolated tool installations | User isolation |
| `pip` | 3 | Standard package installer | Fallback |
| `apt/brew` | 4 | System package managers | System-wide |

**Example:**

```yaml
tools:
  black:
    method: uv       # Prefer uv
    fallback: pipx   # Use pipx if uv unavailable
```

#### Rust Ecosystem

| Method | Priority | Description | Use Cases |
|--------|----------|-------------|-----------|
| `rustup` | 1 | Official Rust toolchain installer | Rust compiler |
| `cargo` | 2 | Rust package manager | Rust CLI tools |
| `github` | 3 | GitHub releases (prebuilt) | Faster than cargo |
| `apt/brew` | 4 | System package managers | System-wide |

**Example:**

```yaml
tools:
  ripgrep:
    method: cargo    # Build from source
    fallback: github # Prebuilt binary if cargo slow
```

#### Node.js Ecosystem

| Method | Priority | Description | Use Cases |
|--------|----------|-------------|-----------|
| `nvm` | 1 | Node Version Manager | Version switching |
| `npm` | 2 | Node package manager | Global packages |
| `apt/brew` | 3 | System package managers | System-wide |

**Example:**

```yaml
tools:
  node:
    method: nvm      # Version management
  prettier:
    method: npm      # Global installation
```

#### Standalone Binaries (GitHub Releases)

| Method | Priority | Description | Use Cases |
|--------|----------|-------------|-----------|
| `github` | 1 | Prebuilt releases | Fast, self-contained |
| `cargo/go` | 2 | Build from source | Latest features |
| `apt/brew` | 3 | System packages | System-wide |

**Example:**

```yaml
tools:
  fd:
    method: github   # Prebuilt binary (fast)
    fallback: cargo  # Build if architecture unsupported
```

### Method Selection Logic

When installing a tool, AI CLI Preparation selects methods using this logic:

1. **Check explicit method**: If `tools.<name>.method` specified, use it
2. **Check method availability**: Verify method command exists on system
3. **Apply hierarchy**: Use first available method in hierarchy
4. **Fallback**: Try fallback method if primary fails
5. **Error**: Report failure if all methods unavailable

**Example:**

```yaml
tools:
  ripgrep:
    method: cargo
    fallback: github

# Selection Logic:
# 1. User specified: cargo (preferred)
# 2. Check: cargo command exists? Yes → use cargo
# 3. If cargo fails: fallback to github
# 4. If github fails: error (report installation failure)
```

---

## Configuration Examples

### Workstation (Developer Laptop)

**Use Case:** Single-user development system prioritizing latest features

```yaml
version: 1

environment:
  mode: workstation  # Or auto-detect

preferences:
  reconciliation: parallel      # Keep multiple installations
  breaking_changes: accept      # Auto-upgrade major versions
  auto_upgrade: true            # Auto-upgrade minor/patch
  max_workers: 16               # Parallel operations

tools:
  python:
    version: "latest"           # Always latest Python
    method: uv                  # Fast package manager

  node:
    version: "latest"           # Always latest Node.js
    method: nvm                 # Version manager

  ripgrep:
    version: "latest"           # Always latest ripgrep
    method: cargo               # Build from source

presets:
  my-stack:
    - python
    - uv
    - black
    - ruff
    - node
    - prettier
    - ripgrep
    - fd
```

### Shared Server (Multi-User)

**Use Case:** Shared development server prioritizing stability

```yaml
version: 1

environment:
  mode: server  # Or auto-detect

preferences:
  reconciliation: parallel      # Don't remove existing installs
  breaking_changes: warn        # Prompt for major upgrades
  auto_upgrade: false           # Manual upgrades only
  timeout_seconds: 10           # Longer timeout (slow network)

tools:
  python:
    version: "3.11.*"           # Lock to 3.11 series
    method: apt                 # System package manager

  node:
    version: "20.*"             # Lock to Node 20.x
    method: apt                 # System package manager

  ripgrep:
    version: ">=14.0.0"         # Minimum version (features)
    method: apt                 # System package manager
```

### CI/CD (Ephemeral Container)

**Use Case:** Reproducible builds with exact versions

```yaml
version: 1

environment:
  mode: ci

snapshot:
  path: tools_snapshot.json     # Locked versions
  strict: true                  # Fail if unavailable

preferences:
  reconciliation: replace       # Clean slate
  breaking_changes: reject      # Exact versions only
  auto_upgrade: false           # No upgrades
  max_workers: 32               # Fast parallel installs

tools:
  python:
    version: "=3.12.1"          # Exact version lock
    method: apt

  node:
    version: "=20.10.0"         # Exact version lock
    method: apt
```

### Per-Tool Version Locking

**Use Case:** Mix of latest and locked versions

```yaml
version: 1

preferences:
  breaking_changes: warn        # Warn on major upgrades

tools:
  # Latest versions (stable APIs)
  ripgrep:
    version: "latest"
  fd:
    version: "latest"
  bat:
    version: "latest"

  # Locked versions (project dependencies)
  python:
    version: "3.11.*"           # Project requires 3.11
  node:
    version: "20.*"             # Project requires Node 20

  # Minimum versions (feature requirements)
  black:
    version: ">=23.0.0"         # Requires f-string fixes
  ruff:
    version: ">=0.1.0"          # Stable API
```

### Custom Presets

**Use Case:** Organization-specific tool stacks

```yaml
version: 1

presets:
  backend-python:
    - python
    - uv
    - black
    - ruff
    - mypy
    - pytest
    - httpie

  frontend-react:
    - node
    - npm
    - prettier
    - eslint
    - typescript

  security-audit:
    - gitleaks
    - semgrep
    - bandit
    - trivy
    - osv-scanner

  cloud-aws:
    - aws-cli
    - terraform
    - kubectl
    - docker
```

**Usage:**

```bash
# Install backend stack
cli_audit install --preset backend-python

# Install security tools
cli_audit install --preset security-audit
```

### Package Manager Overrides

**Use Case:** Override default package manager preferences

```yaml
version: 1

preferences:
  # Prefer GitHub releases over building from source
  package_managers:
    rust: [github, cargo, system]

  # Prefer pipx over uv for isolation
  package_managers:
    python: [pipx, uv, pip, system]

  # System packages only (conservative)
  package_managers:
    python: [system]
    rust: [system]
    node: [system]
```

---

## Validation

AI CLI Preparation validates configuration files against a JSON Schema to catch errors early.

### Schema Validation

**Automatic Validation:** Configuration files are validated on load

**Manual Validation:**

```bash
# Validate configuration
cli_audit config validate

# Validate specific file
cli_audit config validate --file .cli-audit.yml
```

### Validation Rules

#### Required Fields

- `version`: Must be present and set to `1`

#### Type Validation

- `version`: Must be integer
- `environment.mode`: Must be one of `[auto, workstation, server, ci]`
- `preferences.reconciliation`: Must be one of `[parallel, aggressive]`
- `preferences.breaking_changes`: Must be one of `[accept, warn, reject]`
- `preferences.auto_upgrade`: Must be boolean
- `preferences.timeout_seconds`: Must be integer (1-60)
- `preferences.max_workers`: Must be integer (1-64)

#### Range Validation

- `timeout_seconds`: 1 ≤ value ≤ 60
- `max_workers`: 1 ≤ value ≤ 64

### Common Validation Errors

#### Missing Version

```
❌ Configuration error: Missing required field 'version'
   Location: .cli-audit.yml
   Fix: Add 'version: 1' to configuration file
```

#### Invalid Mode

```
❌ Configuration error: Invalid environment mode 'dev'
   Location: .cli-audit.yml:3
   Valid values: [auto, workstation, server, ci]
   Fix: Change 'mode: dev' to one of the valid values
```

#### Invalid Timeout

```
❌ Configuration error: timeout_seconds must be between 1 and 60
   Location: .cli-audit.yml:7
   Found: 120
   Fix: Reduce timeout_seconds to 60 or less
```

#### Invalid Version Syntax

```
❌ Configuration error: Invalid version syntax '3.12.x'
   Location: tools.python.version
   Valid formats: latest, 3.12.*, >=3.11, ^3.11, ~3.11.0, =3.11.5
   Fix: Use '3.12.*' instead of '3.12.x'
```

#### Typo in Field Name

```
❌ Configuration error: Unknown field 'reconcilliation'
   Location: preferences
   Did you mean: 'reconciliation'?
   Fix: Correct the spelling
```

---

## CLI Commands

AI CLI Preparation provides CLI commands for configuration management.

### `config init`

**Description:** Generate default configuration file

**Syntax:**

```bash
cli_audit config init [OPTIONS]
```

**Options:**
- `--user`: Generate user-global config (`~/.config/cli-audit/config.yml`)
- `--system`: Generate system-global config (`/etc/cli-audit/config.yml`)
- `--force`: Overwrite existing file

**Examples:**

```bash
# Create project configuration
cli_audit config init

# Create user-global configuration
cli_audit config init --user

# Overwrite existing configuration
cli_audit config init --force
```

**Generated Output:**

```yaml
version: 1

environment:
  mode: auto

preferences:
  reconciliation: parallel
  breaking_changes: warn
  auto_upgrade: true
  timeout_seconds: 3
  max_workers: 16
```

### `config validate`

**Description:** Validate configuration file syntax

**Syntax:**

```bash
cli_audit config validate [OPTIONS]
```

**Options:**
- `--file <path>`: Validate specific file (default: project config)

**Examples:**

```bash
# Validate project config
cli_audit config validate

# Validate user config
cli_audit config validate --file ~/.config/cli-audit/config.yml

# Validate custom file
cli_audit config validate --file custom.yml
```

**Success Output:**

```
✅ Configuration valid: .cli-audit.yml
```

**Error Output:**

```
❌ Configuration invalid: .cli-audit.yml

Errors:
  - Line 3: Invalid mode 'dev' (valid: auto, workstation, server, ci)
  - Line 8: timeout_seconds must be integer (found: "5")
```

### `config show`

**Description:** Display effective configuration (after merging)

**Syntax:**

```bash
cli_audit config show [OPTIONS]
```

**Options:**
- `--sources`: Show which file provides each setting
- `--format <format>`: Output format (`yaml`, `json`)

**Examples:**

```bash
# Show effective configuration
cli_audit config show

# Show with sources
cli_audit config show --sources

# JSON output
cli_audit config show --format json
```

**Example Output:**

```yaml
# Effective Configuration (merged from 3 sources)

version: 1

environment:
  mode: workstation  # From: ./.cli-audit.yml

preferences:
  reconciliation: parallel     # From: default
  breaking_changes: warn       # From: ~/.config/cli-audit/config.yml
  auto_upgrade: true           # From: default
  timeout_seconds: 5           # From: ./.cli-audit.yml
  max_workers: 16              # From: default

tools:
  python:
    version: "3.11.*"          # From: ./.cli-audit.yml
    method: uv                 # From: ~/.config/cli-audit/config.yml
```

### `config edit`

**Description:** Open configuration file in editor

**Syntax:**

```bash
cli_audit config edit [OPTIONS]
```

**Options:**
- `--user`: Edit user-global config
- `--system`: Edit system-global config
- `--editor <cmd>`: Use specific editor (default: $EDITOR)

**Examples:**

```bash
# Edit project config
cli_audit config edit

# Edit user config
cli_audit config edit --user

# Edit with specific editor
cli_audit config edit --editor vim
```

---

## Best Practices

### Configuration Organization

**Project-Local (`./.cli-audit.yml`):**
- Project-specific version requirements
- Tool locks for reproducibility
- Preset definitions for project workflows

**User-Global (`~/.config/cli-audit/config.yml`):**
- Personal package manager preferences
- Performance tuning (max_workers, timeout)
- Breaking change tolerance

**System-Global (`/etc/cli-audit/config.yml`):**
- Organization-wide policies
- Security requirements
- Shared server defaults

### Version Specification

**Recommended Practices:**
- Use `latest` for tools with stable APIs (ripgrep, fd)
- Use `x.y.*` locks for project dependencies (Python, Node)
- Use `>=x.y.z` for minimum feature requirements
- Use `=x.y.z` only for CI/CD reproducibility

**Avoid:**
- Over-constraining versions (blocks beneficial updates)
- Using `latest` for project dependencies (breaks reproducibility)
- Mixing version styles inconsistently

### Preset Management

**Effective Presets:**
- Group tools by use case (backend, frontend, security)
- Keep presets focused (5-10 tools per preset)
- Document preset purpose in comments
- Version control presets in project config

### Performance Tuning

**Max Workers:**
- Low-power laptops: 8 workers
- Standard laptops: 16 workers (default)
- High-performance desktops: 32 workers
- CI/CD containers: 32-64 workers

**Timeout:**
- Fast networks: 3 seconds (default)
- Slow networks: 5-10 seconds
- CI/CD (cached): 1 second
- CI/CD (uncached): 10 seconds

---

## Troubleshooting

### Configuration Not Loading

**Symptom:** Configuration changes not applied

**Diagnosis:**

```bash
# Check which files exist
ls -la .cli-audit.yml
ls -la ~/.config/cli-audit/config.yml
ls -la /etc/cli-audit/config.yml

# Show effective configuration
cli_audit config show --sources
```

**Common Causes:**
- File in wrong location
- Syntax errors preventing parse
- Precedence misunderstanding

### Validation Errors

**Symptom:** `config validate` reports errors

**Diagnosis:**

```bash
cli_audit config validate
```

**Common Fixes:**
- Fix YAML syntax (indentation, colons)
- Correct enum values (mode, reconciliation, breaking_changes)
- Ensure version is integer, not string

### Version Constraints Not Working

**Symptom:** Tool installed with wrong version

**Diagnosis:**

```bash
# Show effective config
cli_audit config show

# Check version specification
cli_audit audit --json | jq '.tools[] | select(.name=="python")'
```

**Common Causes:**
- Syntax error in version string (e.g., `3.12.x` instead of `3.12.*`)
- Constraint doesn't match any available versions
- Upstream API returning unexpected versions

### Package Manager Not Used

**Symptom:** Tool installed with wrong method

**Diagnosis:**

```bash
# Check package manager availability
which uv pipx pip

# Check configuration
cli_audit config show --sources | grep -A2 "python:"
```

**Common Causes:**
- Specified method not installed on system
- Fallback chain doesn't include working method
- PATH issues preventing method detection

---

## Reference

### Related Documentation

- **[PRD.md](PRD.md)** - Product requirements and Phase 2 specification
- **[ADR-006](adr/ADR-006-configuration-file-format.md)** - Configuration format decision
- **[ADR-001](adr/ADR-001-context-aware-installation.md)** - Environment mode behaviors
- **[ADR-002](adr/ADR-002-package-manager-hierarchy.md)** - Package manager preferences
- **[ADR-004](adr/ADR-004-always-latest-version-policy.md)** - Version policy rationale

### External Standards

- **YAML Specification:** https://yaml.org/spec/1.2/
- **JSON Schema:** https://json-schema.org/
- **Semantic Versioning:** https://semver.org/

### Configuration Schema (JSON Schema)

Complete JSON Schema for validation available at:
`/home/sme/p/ai_cli_preparation/schema/config-schema.json` (Phase 2 implementation)

---

**Document Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial specification (Phase 2) |
