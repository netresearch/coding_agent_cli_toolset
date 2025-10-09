# ADR-001: Context-Aware Installation Modes

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** AI CLI Preparation Team, User Requirements
**Tags:** installation, environment-detection, context-aware

## Context

Different environments have different requirements for tool installation:

- **Development Workstations** (laptops, personal desktops): Single-user systems where developers want latest tools, user-level installs, and flexibility
- **Shared Development Servers** (jump boxes, multi-user Linux servers): Multi-user systems requiring coordination, system-level installs, and stability
- **CI/CD Environments** (ephemeral containers, VMs): Temporary systems needing fast, reproducible, minimal installations

A one-size-fits-all installation strategy would either:
- Be too aggressive for servers (breaking other users' workflows)
- Be too conservative for workstations (preventing developers from using latest tools)
- Be too slow for CI/CD (installing unnecessary tools)

**Problem:** How do we adapt installation behavior to different environment types?

## Decision

Implement **context-aware installation modes** that automatically detect environment type and adjust installation behavior accordingly:

```python
def detect_environment() -> str:
    """Detect environment type: workstation | server | ci"""
    # CI indicators
    if any(env in os.environ for env in ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME']):
        return 'ci'

    # Multi-user indicators
    user_count = len([u for u in get_active_users() if u.login_time])
    if user_count > 3:
        return 'server'

    # Default to workstation
    return 'workstation'
```

**Mode Behaviors:**

| Aspect | Workstation | Server | CI |
|--------|-------------|--------|-----|
| **Scope** | User (~/.local/bin) | System (/usr/local/bin) | Minimal (project/cache) |
| **Prefer** | Vendor tools (rustup, nvm, uv) | System packages (apt, brew) | Snapshot/cache |
| **Reconciliation** | Parallel (keep both) | Advisory locks (coordinate) | Replace (clean slate) |
| **Breaking Changes** | Accept (always latest) | Warn (manual approval) | Lock (exact versions) |
| **Auto-Upgrade** | Enabled | Disabled (manual only) | Disabled (locked) |

**Configuration Override:**
```yaml
# .cli-audit.yml
environment:
  mode: auto  # auto | workstation | server | ci
```

## Rationale

### Why Context-Aware?

1. **Developer Productivity (Workstation)**:
   - Developers want latest tools for performance and features
   - User-level installs avoid permission issues and conflicts
   - Flexibility to experiment without affecting system

2. **System Stability (Server)**:
   - Multiple users depend on stable tool versions
   - System-level installs ensure consistency
   - Coordination prevents conflicting simultaneous installs

3. **Build Reproducibility (CI)**:
   - Exact versions ensure deterministic builds
   - Fast installs from cache reduce pipeline time
   - Minimal installs save disk space and time

### Why Automatic Detection?

- **Reduces Configuration Burden**: Users don't need to manually configure mode
- **Prevents Mistakes**: Developers won't accidentally break servers
- **Sensible Defaults**: Automatic detection works correctly 95%+ of the time
- **Override Available**: Users can force specific mode if needed

### Why These Thresholds?

- **User Count > 3**: Heuristic for shared server (1-2 users: pair programming, 4+: shared)
- **CI Environment Variables**: Standard indicators across major CI platforms
- **Workstation Default**: Conservative choice (least invasive)

## Consequences

### Positive

- **Better User Experience**: Installation behavior matches environment expectations
- **Reduced Conflicts**: Workstation and server users don't interfere with each other
- **Improved Reliability**: CI builds use locked versions for reproducibility
- **Safer Defaults**: Automatic detection prevents common mistakes

### Negative

- **Complexity**: More code paths and testing required
- **Detection Failures**: Edge cases where automatic detection is wrong (mitigated by override)
- **Documentation Burden**: Users must understand different mode behaviors

### Neutral

- **Configuration File**: Required to override automatic detection
- **Testing**: Must test all three modes independently

## Alternatives Considered

### Alternative 1: Single Fixed Strategy

**Description:** Use one installation strategy for all environments

**Example:** Always install user-level with vendor tools

**Pros:**
- Simpler implementation
- Less code complexity
- Easier to test

**Cons:**
- Doesn't work for servers (user-level installs not visible to other users)
- Doesn't work for CI (no caching, slow installs)
- Requires manual workarounds for different environments

**Why Rejected:** Fails to meet requirements for servers and CI environments

### Alternative 2: Manual Mode Selection Only

**Description:** Require users to explicitly set mode in configuration

**Example:**
```yaml
environment:
  mode: workstation  # REQUIRED field
```

**Pros:**
- Explicit control
- No detection logic needed
- Clear user intent

**Cons:**
- Poor user experience (manual setup required)
- Easy to forget or misconfigure
- Doesn't adapt when environment changes (e.g., developer connects to server)

**Why Rejected:** Creates friction for users, violates "sensible defaults" principle

### Alternative 3: Per-Tool Mode Configuration

**Description:** Configure installation strategy per-tool instead of per-environment

**Example:**
```yaml
tools:
  python:
    scope: user
    prefer: uv
  ripgrep:
    scope: system
    prefer: cargo
```

**Pros:**
- Maximum flexibility
- Fine-grained control

**Cons:**
- Extremely verbose configuration
- Complex mental model
- Most users want consistent behavior across tools

**Why Rejected:** Too complex, doesn't align with user requirements

### Alternative 4: Heuristic-Only (No Override)

**Description:** Rely entirely on automatic detection, no configuration override

**Pros:**
- Simplest user experience
- Zero configuration required

**Cons:**
- No escape hatch for detection failures
- Forces workarounds (e.g., manipulating environment variables)
- Reduces user control

**Why Rejected:** Too restrictive, users need override capability

## Implementation Notes

### Environment Detection Implementation

```python
def get_active_users():
    """Get list of currently active users (logged in recently)"""
    import subprocess
    try:
        output = subprocess.check_output(['who'], text=True)
        users = []
        for line in output.strip().split('\n'):
            if line:
                parts = line.split()
                users.append({'name': parts[0], 'login_time': parts[2:5]})
        return users
    except Exception:
        return []  # Fallback to workstation if detection fails

def detect_environment() -> str:
    """Detect environment type: workstation | server | ci"""
    # CI indicators (priority: most specific)
    ci_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME', 'CIRCLECI', 'TRAVIS']
    if any(var in os.environ for var in ci_vars):
        return 'ci'

    # Multi-user indicators
    try:
        user_count = len(get_active_users())
        if user_count > 3:
            return 'server'
    except Exception:
        pass  # Fall through to workstation

    # Default to workstation (conservative)
    return 'workstation'
```

### Configuration Loading

```python
def load_environment_mode(config_path: str = '.cli-audit.yml') -> str:
    """Load environment mode from config or detect automatically"""
    if os.path.exists(config_path):
        config = yaml.safe_load(open(config_path))
        mode = config.get('environment', {}).get('mode', 'auto')
        if mode != 'auto':
            return mode  # Explicit override

    # Auto-detect
    return detect_environment()
```

### Testing Strategy

1. **Unit Tests**: Mock environment variables and user count
2. **Integration Tests**: Test on actual workstation, server, CI environments
3. **Override Tests**: Verify configuration override works correctly
4. **Edge Cases**: Single-user server, developer with sudo on workstation

### Rollout Plan

1. **Phase 1**: Implement detection logic, workstation mode only
2. **Phase 2**: Add server mode with advisory locks
3. **Phase 3**: Add CI mode with snapshot-based installs
4. **Phase 4**: Comprehensive testing across environments

## References

- **[PRD.md](../PRD.md#context-aware-installation)** - Phase 2 specification
- **[ADR-005](ADR-005-environment-detection.md)** - Detailed environment detection logic
- **[ADR-006](ADR-006-configuration-file-format.md)** - Configuration file format
- User Requirements: "Primary target: dev workstations, second: shared dev servers"
- User Requirements: "Installation philosophy: context aware"

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial decision accepted |
