# Environment Detection API

**Module:** `cli_audit.environment`
**Phase:** 2.1 (Foundation)
**Purpose:** Context-aware environment detection for intelligent installation strategy selection

---

## Overview

The environment module detects the execution context (CI/CD, server, or workstation) to inform installation decisions. Different environments require different installation strategies:

- **CI/CD:** Reproducible, ephemeral, prefer system packages
- **Server:** Multi-user, system-level, prefer stable versions
- **Workstation:** Single-user, user-level, prefer latest tools

---

## Classes

### Environment

```python
@dataclass(frozen=True)
class Environment:
    """Detected environment information."""
    mode: str
    confidence: float
    indicators: tuple[str, ...] = ()
    override: bool = False
```

**Immutable dataclass** representing detected or configured environment.

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `mode` | `str` | Environment type: `"ci"`, `"server"`, or `"workstation"` |
| `confidence` | `float` | Detection confidence level (0.0-1.0) |
| `indicators` | `tuple[str, ...]` | Evidence used for detection decision |
| `override` | `bool` | Whether mode was explicitly overridden by user |

#### Methods

**`__str__() -> str`**

Returns human-readable representation:
```python
env = Environment(mode="workstation", confidence=0.75, indicators=("display_environment",))
print(env)  # "workstation (confidence: 75%)"
```

---

## Functions

### detect_environment()

```python
def detect_environment(
    override: str | None = None,
    verbose: bool = False
) -> Environment
```

**Detect environment type for context-aware installation.**

Uses heuristic detection with priority cascade:
1. Explicit override (if provided)
2. CI/CD indicators (highest confidence: 95%)
3. Server indicators (medium confidence: 50-85%)
4. Workstation (default fallback: 75%)

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `override` | `str \| None` | `None` | Explicit mode: `"ci"`, `"server"`, `"workstation"`, or `None` for auto-detect |
| `verbose` | `bool` | `False` | Enable verbose logging to stdout |

#### Returns

`Environment` object with detected or overridden mode

#### Raises

- `ValueError`: If `override` value is not valid (`"ci"`, `"server"`, `"workstation"`)

#### Detection Algorithm

**1. CI/CD Detection (Confidence: 95%)**

Checks environment variables:
- `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, `CIRCLECI`, `TRAVIS`
- `JENKINS_HOME`, `BUILDKITE`, `DRONE`, `SEMAPHORE`

If any CI variable is set → `mode="ci"`, `confidence=0.95`

**2. Server Detection (Confidence: 50-85%)**

Scoring system (threshold: 0.5):
- **Multiple active users:**
  - `>3 users`: +0.3 score
  - `>1 users`: +0.15 score
- **System uptime:**
  - `>30 days`: +0.25 score
  - `>7 days`: +0.1 score
- **Shared filesystem:**
  - `/shared` or `/export` exists: +0.2 score
- **No display environment:**
  - No `DISPLAY`, `WAYLAND_DISPLAY`, or `SSH_CONNECTION`: +0.1 score

If `score >= 0.5` → `mode="server"`, `confidence=min(score, 0.85)`

**3. Workstation Detection (Confidence: 75%)**

Default fallback when CI/server detection fails.

Indicators checked (informational only):
- Display environment (`DISPLAY` or `WAYLAND_DISPLAY`)
- Single user
- Typical workstation paths (`~/Desktop`, `~/.config`)

Always returns: `mode="workstation"`, `confidence=0.75`

#### Examples

**Auto-detection:**
```python
from cli_audit import detect_environment

# Detect current environment
env = detect_environment()
print(env.mode)        # "workstation"
print(env.confidence)  # 0.75
print(env.indicators)  # ("display_environment", "single_user", "workstation_paths")
```

**Explicit override:**
```python
# Force CI mode
env = detect_environment(override="ci")
print(env.mode)      # "ci"
print(env.confidence) # 1.0
print(env.override)  # True
```

**Verbose logging:**
```python
env = detect_environment(verbose=True)
# Output: "Workstation environment detected (default): ['display_environment', 'single_user']"
```

**CI environment detection:**
```python
import os
os.environ["GITHUB_ACTIONS"] = "true"

env = detect_environment()
print(env.mode)       # "ci"
print(env.confidence) # 0.95
print(env.indicators) # ("env:GITHUB_ACTIONS=true",)
```

**Server environment detection:**
```python
# On a server with 5 active users and 45 days uptime
env = detect_environment()
print(env.mode)       # "server"
print(env.confidence) # 0.55 (0.3 + 0.25)
print(env.indicators) # ("active_users=5", "uptime_days=45")
```

---

### get_environment_from_config()

```python
def get_environment_from_config(
    config_mode: str | None,
    verbose: bool = False
) -> Environment
```

**Get environment from configuration file setting.**

Wrapper around `detect_environment()` for config file integration.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_mode` | `str \| None` | - | Mode from config: `"auto"`, `"ci"`, `"server"`, `"workstation"`, or `None` |
| `verbose` | `bool` | `False` | Enable verbose logging |

#### Returns

`Environment` object:
- `"auto"` or `None` → triggers `detect_environment(override=None)`
- Other values → explicit override via `detect_environment(override=config_mode)`

#### Examples

**Auto-detection from config:**
```python
from cli_audit import get_environment_from_config

# Config specifies "auto" or is None
env = get_environment_from_config(config_mode="auto")
# Triggers full auto-detection
```

**Explicit mode from config:**
```python
# Config specifies "server"
env = get_environment_from_config(config_mode="server")
print(env.mode)     # "server"
print(env.override) # True
```

---

## Usage Patterns

### Basic Detection

```python
from cli_audit import detect_environment

env = detect_environment()

if env.mode == "ci":
    print("Running in CI/CD - use reproducible installs")
elif env.mode == "server":
    print("Running on server - use system packages")
else:  # workstation
    print("Running on workstation - use user-level tools")
```

### With Configuration

```python
from cli_audit import load_config, get_environment_from_config

config = load_config()  # Loads .cli-audit.yml
env = get_environment_from_config(config.environment_mode)

print(f"Environment: {env}")
print(f"Confidence: {env.confidence * 100:.0f}%")
```

### Installation Strategy Selection

```python
from cli_audit import detect_environment, select_package_manager

env = detect_environment()

if env.mode == "ci":
    # CI: Prefer system packages for reproducibility
    pm = select_package_manager("python", env=env)
    # Likely returns: pip (system)

elif env.mode == "server":
    # Server: Prefer system packages for stability
    pm = select_package_manager("python", env=env)
    # Likely returns: pip (system) or apt/dnf

else:  # workstation
    # Workstation: Prefer user-level isolation
    pm = select_package_manager("python", env=env)
    # Likely returns: uv or pipx (user-level)
```

### Confidence-Based Fallbacks

```python
env = detect_environment()

if env.confidence < 0.6:
    print(f"Warning: Low confidence ({env.confidence:.0%}) in detection")
    print(f"Indicators: {env.indicators}")

    # Prompt user for confirmation or use safe defaults
    confirmed = input(f"Detected {env.mode}. Correct? [y/N]: ")
    if confirmed.lower() != 'y':
        # Use explicit override
        mode = input("Enter mode (ci/server/workstation): ")
        env = detect_environment(override=mode)
```

---

## Integration Points

### With Configuration (config.py)

```python
from cli_audit import Config, get_environment_from_config

config = Config()  # Default or loaded from file
env = get_environment_from_config(config.environment_mode)
```

### With Package Manager Selection (package_managers.py)

```python
from cli_audit import detect_environment, select_package_manager

env = detect_environment()
pm = select_package_manager("python", env=env)
# Environment influences PM selection priority
```

### With Installation (installer.py)

```python
from cli_audit import install_tool, detect_environment, Config

config = Config()
env = detect_environment()

result = install_tool(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,  # Environment influences installation strategy
    language="rust",
)
```

---

## Design Decisions

### Why Frozen Dataclass?

Immutability ensures environment detection results can't be accidentally modified after detection, preventing subtle bugs in multi-threaded contexts.

### Why Confidence Scores?

Different detection methods have different reliability:
- **CI indicators (95%):** Environment variables are explicit
- **Server heuristics (50-85%):** Scoring multiple indicators
- **Workstation fallback (75%):** Safe default, medium confidence

### Why Three Modes Only?

Simplifies decision logic while covering main use cases:
- **CI:** Ephemeral, reproducible builds
- **Server:** Multi-user, system-level stability
- **Workstation:** Single-user, latest tools

More granular modes (developer, production, staging) can be handled via configuration overrides.

### Why Override Support?

Allows users to explicitly set mode when:
- Heuristics fail or produce low confidence
- Running in unusual environments (containers, VMs)
- Testing installation strategies
- Configuration-driven workflows

---

## Related Documentation

- **Configuration:** [config.md](config.md) - Config integration
- **Package Managers:** [package_managers.md](package_managers.md) - PM selection influenced by environment
- **Architecture:** [../ARCHITECTURE_DIAGRAM.md](../ARCHITECTURE_DIAGRAM.md) - Environment in dependency graph
- **ADR-005:** [../adr/ADR-005-environment-detection.md](../adr/ADR-005-environment-detection.md) - Design rationale

---

## Change History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0-alpha.6 | 2025-10-09 | Initial Phase 2.1 implementation |

**Module Location:** `cli_audit/environment.py` (177 lines)
**Exports:** `Environment`, `detect_environment`, `get_environment_from_config`
**Dependencies:** `common.py` (utility functions)
