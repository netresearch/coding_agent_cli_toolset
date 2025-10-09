# ADR-006: Configuration File Format

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** AI CLI Preparation Team
**Tags:** configuration, yaml, file-format

## Context

AI CLI Preparation requires configuration for:
- Environment mode overrides (workstation, server, ci)
- Package manager preferences
- Version locking per tool
- Reconciliation strategies
- Breaking change tolerance
- Global preferences (timeout, workers, etc.)

**Requirements:**

1. **Human-Readable**: Easy for developers to read and edit
2. **Machine-Parsable**: Structured format for programmatic access
3. **Standard Format**: Use widely adopted format (not custom DSL)
4. **Hierarchical**: Support nested configuration (tools, preferences, environment)
5. **Validation**: Schema validation to catch errors early
6. **Multiple Locations**: Project-local, user-global, system-global
7. **Precedence**: Project overrides user overrides system

**Format Options:**

| Format | Pros | Cons |
|--------|------|------|
| **YAML** | Human-readable, hierarchical, widely used | Whitespace-sensitive, complex spec |
| **TOML** | Simple, explicit, Rust ecosystem | Less familiar to developers |
| **JSON** | Ubiquitous, strict parsing | Not human-friendly (no comments) |
| **INI** | Simple, widely supported | Limited nesting, no lists |
| **Python** | Full language power | Security risk (arbitrary code) |

**Problem:** What configuration file format best balances readability, structure, and developer familiarity?

## Decision

Use **YAML** format with **.cli-audit.yml** filename and multi-location precedence

### File Locations

**Precedence: Project → User → System** (first match wins per setting)

```
1. ./.cli-audit.yml               # Project-local (highest priority)
2. ~/.config/cli-audit/config.yml  # User-global
3. /etc/cli-audit/config.yml       # System-global (lowest priority)
```

### Schema Definition

```yaml
# .cli-audit.yml - AI CLI Preparation Configuration
# Schema Version: 1

version: 1  # Schema version (required)

# Environment mode override
environment:
  mode: auto  # auto | workstation | server | ci

# Global preferences
preferences:
  reconciliation: parallel  # parallel | aggressive
  breaking_changes: warn    # accept | warn | reject
  auto_upgrade: true        # Auto-upgrade minor/patch versions
  timeout_seconds: 5        # Network timeout (default: 3)
  max_workers: 16           # Parallel workers (default: 16)

  # Package manager hierarchy override
  package_managers:
    python: [uv, pipx, pip]
    rust: [rustup, cargo, system]
    node: [nvm, npm, system]

# Per-tool configuration
tools:
  python:
    version: "3.12.*"      # SemVer range: 3.12.x only
    method: uv             # Preferred package manager
    fallback: pipx         # Fallback if uv unavailable

  ripgrep:
    version: "latest"      # Always latest (default)
    method: cargo

  node:
    version: "=20.10.0"    # Exact version lock
    method: nvm

  # Tool-specific preferences
  black:
    version: ">=23.0.0"    # Minimum version
    method: pipx
    auto_upgrade: false    # Override global auto_upgrade

# Custom role presets
presets:
  my-python-stack:
    - python
    - uv
    - black
    - ruff
    - pyright
    - pytest

  my-rust-stack:
    - rust
    - cargo
    - ripgrep
    - fd
    - bat

# Snapshot configuration (for CI)
snapshot:
  path: tools_snapshot.json  # Path to snapshot file
  strict: true               # Fail if snapshot versions unavailable
```

### Version Specification Syntax

**SemVer Ranges** (npm/Cargo style):

```yaml
version: "latest"        # Always latest available
version: "3.12.*"        # Any 3.12.x (e.g., 3.12.0, 3.12.1)
version: ">=3.11"        # 3.11.0 or higher
version: "^3.11"         # 3.11.x (caret: minor updates)
version: "~3.11.0"       # 3.11.x (tilde: patch updates)
version: "=3.11.5"       # Exact version only
```

### Configuration Loading

```python
def load_config() -> Config:
    """Load and merge configuration from multiple locations"""
    # Default configuration
    config = Config.default()

    # Load in precedence order (system → user → project)
    system_config = load_config_file('/etc/cli-audit/config.yml')
    user_config = load_config_file(os.path.expanduser('~/.config/cli-audit/config.yml'))
    project_config = load_config_file('.cli-audit.yml')

    # Merge: project overrides user overrides system
    config = merge_configs([system_config, user_config, project_config])

    # Validate schema
    validate_config(config)

    return config


def merge_configs(configs: list[Config]) -> Config:
    """Merge configurations with later configs overriding earlier ones"""
    merged = Config.default()

    for config in configs:
        if config is None:
            continue

        # Merge environment
        if 'environment' in config:
            merged['environment'].update(config['environment'])

        # Merge preferences
        if 'preferences' in config:
            merged['preferences'].update(config['preferences'])

        # Merge tools (per-tool override)
        if 'tools' in config:
            merged['tools'].update(config['tools'])

        # Merge presets
        if 'presets' in config:
            merged['presets'].update(config['presets'])

    return merged
```

### Schema Validation

```python
import yaml
from jsonschema import validate, ValidationError

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "integer", "const": 1},
        "environment": {
            "type": "object",
            "properties": {
                "mode": {"enum": ["auto", "workstation", "server", "ci"]}
            }
        },
        "preferences": {
            "type": "object",
            "properties": {
                "reconciliation": {"enum": ["parallel", "aggressive"]},
                "breaking_changes": {"enum": ["accept", "warn", "reject"]},
                "auto_upgrade": {"type": "boolean"},
                "timeout_seconds": {"type": "integer", "minimum": 1},
                "max_workers": {"type": "integer", "minimum": 1, "maximum": 64}
            }
        },
        "tools": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string"},
                        "method": {"type": "string"},
                        "fallback": {"type": "string"},
                        "auto_upgrade": {"type": "boolean"}
                    }
                }
            }
        },
        "presets": {
            "type": "object",
            "patternProperties": {
                ".*": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "required": ["version"]
}

def validate_config(config: dict) -> None:
    """Validate configuration against schema"""
    try:
        validate(instance=config, schema=CONFIG_SCHEMA)
    except ValidationError as e:
        print(f"❌ Invalid configuration: {e.message}")
        sys.exit(1)
```

## Rationale

### Why YAML?

**Human-Readable:**
```yaml
# YAML: Natural to read and write
tools:
  python:
    version: "3.12.*"
    method: uv
```

vs

```json
// JSON: More verbose, no comments
{
  "tools": {
    "python": {
      "version": "3.12.*",
      "method": "uv"
    }
  }
}
```

**Hierarchical Structure:**
- Native support for nested objects
- Lists and dictionaries
- Multiline strings

**Developer Familiarity:**
- Used in Docker Compose, Kubernetes, GitHub Actions, Ansible
- Most developers have YAML experience
- Extensive tooling support (linters, validators, IDE plugins)

**Comments Support:**
```yaml
# This is a comment
tools:
  python:
    version: "3.12.*"  # Lock to Python 3.12.x
```

### Why .cli-audit.yml Filename?

**Conventions:**
- Standard YAML extension (.yml or .yaml)
- Tool-specific prefix (.cli-audit)
- Dot-prefixed (hidden file, won't clutter listings)

**Alternatives:**
- `cli-audit.yml` (not hidden)
- `.cli-audit.yaml` (longer extension)
- `.cli-audit.config.yml` (too verbose)

### Why Multi-Location Precedence?

**Use Cases:**

1. **System-Level Defaults** (`/etc/cli-audit/config.yml`):
   - Admin sets organization-wide policies
   - All users inherit settings
   - Example: Force server mode on shared systems

2. **User-Level Overrides** (`~/.config/cli-audit/config.yml`):
   - Developer sets personal preferences
   - Applies to all projects
   - Example: Prefer uv for Python across all projects

3. **Project-Level Overrides** (`./.cli-audit.yml`):
   - Project-specific requirements
   - Highest priority
   - Example: Lock Node.js to 20.x for compatibility

**Precedence Example:**
```
System: /etc/cli-audit/config.yml
  environment: { mode: server }
  preferences: { breaking_changes: reject }

User: ~/.config/cli-audit/config.yml
  preferences: { breaking_changes: warn }  # Overrides system

Project: ./.cli-audit.yml
  environment: { mode: workstation }       # Overrides system
  tools:
    python: { version: "3.11.*" }          # Project-specific

Result:
  environment: { mode: workstation }       # Project
  preferences: { breaking_changes: warn }  # User
  tools: { python: { version: "3.11.*" } } # Project
```

### Why Schema Validation?

**Benefits:**

1. **Early Error Detection**: Catch typos and invalid values before execution
2. **Clear Error Messages**: Explain what's wrong and where
3. **Documentation**: Schema serves as formal specification
4. **IDE Support**: JSON Schema enables autocomplete in editors

**Example Error:**
```
❌ Invalid configuration: 'reconciliation' must be one of ['parallel', 'aggressive']
   Found: 'paralel' (typo)
   Location: .cli-audit.yml:7
```

## Consequences

### Positive

- **Human-Readable**: Easy for developers to read and edit
- **Hierarchical**: Supports nested configuration naturally
- **Standard Format**: YAML is widely adopted and familiar
- **Validation**: Schema catches errors early
- **Flexible**: Multi-location precedence supports all use cases
- **Comments**: Developers can document configuration choices

### Negative

- **Whitespace-Sensitive**: Indentation errors can be frustrating
- **Complex Spec**: YAML has edge cases (anchors, multiline, etc.)
- **Dependency**: Requires YAML parser (PyYAML or ruamel.yaml)

### Neutral

- **Learning Curve**: Developers familiar with YAML from other tools
- **Validation Required**: Schema validation adds complexity but improves UX

## Alternatives Considered

### Alternative 1: TOML Format

**Description:** Use TOML instead of YAML

```toml
# .cli-audit.toml
version = 1

[environment]
mode = "auto"

[preferences]
reconciliation = "parallel"
breaking_changes = "warn"

[tools.python]
version = "3.12.*"
method = "uv"
```

**Pros:**
- Simpler spec than YAML (less edge cases)
- Explicit syntax (no whitespace sensitivity)
- Used in Rust ecosystem (Cargo.toml)

**Cons:**
- Less familiar to most developers
- More verbose than YAML
- Nested structures less natural

**Why Rejected:** YAML is more widely adopted, more familiar to developers

### Alternative 2: JSON Format

**Description:** Use JSON instead of YAML

```json
{
  "version": 1,
  "environment": {
    "mode": "auto"
  },
  "tools": {
    "python": {
      "version": "3.12.*",
      "method": "uv"
    }
  }
}
```

**Pros:**
- Ubiquitous (every language has parser)
- Strict parsing (no ambiguity)
- Simple spec

**Cons:**
- Not human-friendly (no comments, trailing commas, verbose)
- Poor developer experience for manual editing
- No comments (can't document choices)

**Why Rejected:** Too verbose, poor UX for manual editing

### Alternative 3: Python Configuration Files

**Description:** Use Python files for configuration (.cli-audit.py)

```python
# .cli-audit.py
CONFIG = {
    'environment': {'mode': 'auto'},
    'tools': {
        'python': {'version': '3.12.*', 'method': 'uv'}
    }
}
```

**Pros:**
- Full language power
- Dynamic configuration (conditions, functions)
- Native Python integration

**Cons:**
- Security risk (arbitrary code execution)
- Requires Python runtime to read config
- Complex for simple configuration

**Why Rejected:** Security risk, overkill for configuration needs

### Alternative 4: Single-Location Configuration

**Description:** Only support project-local .cli-audit.yml

**Pros:**
- Simpler implementation
- No precedence complexity

**Cons:**
- Can't set user-global preferences
- Can't enforce system-wide policies
- Duplicated configuration across projects

**Why Rejected:** Doesn't support system/user-level configuration needs

## Implementation Notes

### Configuration File Generation

```bash
# Generate default config
cli_audit config init

# Output: .cli-audit.yml
version: 1
environment:
  mode: auto
preferences:
  reconciliation: parallel
  breaking_changes: warn
  auto_upgrade: true
```

### Configuration Commands

```bash
# Validate configuration
cli_audit config validate

# Show effective configuration (after merging)
cli_audit config show

# Show configuration source (which file provides each setting)
cli_audit config show --sources

# Edit user-global config
cli_audit config edit --user

# Edit project config
cli_audit config edit
```

### Testing Strategy

1. **Unit Tests**: Test configuration parsing, merging, validation
2. **Integration Tests**: Test multi-location precedence
3. **Schema Tests**: Test validation catches errors
4. **Edge Case Tests**: Test YAML edge cases (anchors, multiline, etc.)

## References

- **[PRD.md](../PRD.md#configuration-file-format)** - Phase 2 specification
- **[ADR-001](ADR-001-context-aware-installation.md)** - Context-aware installation modes
- **[ADR-002](ADR-002-package-manager-hierarchy.md)** - Package manager hierarchy
- **[ADR-004](ADR-004-always-latest-version-policy.md)** - Always-latest version policy
- **[CONFIGURATION_SPEC.md](../CONFIGURATION_SPEC.md)** - Full configuration specification
- YAML Specification: https://yaml.org/spec/1.2/
- JSON Schema: https://json-schema.org/

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial decision accepted |
