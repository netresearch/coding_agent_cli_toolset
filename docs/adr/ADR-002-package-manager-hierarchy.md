# ADR-002: Package Manager Preference Hierarchy

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** AI CLI Preparation Team, User Requirements
**Tags:** package-managers, installation, hierarchy

## Context

Most developer tools can be installed via multiple package managers:

- **Python tools**: pip, pipx, uv, apt, brew
- **Rust tools**: cargo, apt, brew
- **Node.js tools**: npm, yarn, pnpm, apt, brew
- **System tools**: apt, brew, dnf, pacman

Each installation method has different characteristics:

| Method | Scope | Version Control | User Isolation | Parallel Installs |
|--------|-------|-----------------|----------------|-------------------|
| **Vendor Tools** (rustup, nvm, uv) | User | Excellent | Yes | Yes |
| **GitHub Releases** | User or System | Manual | Depends | No |
| **System Packages** (apt, brew) | System | Poor (slow updates) | No | No |

**Problem:** Which package manager should we prefer for each tool? Should we enforce a strict hierarchy or allow per-tool configuration?

## Decision

Implement a **hierarchical package manager preference system** with the order:

**Vendor-Specific Tools → GitHub Releases → System Package Managers**

### Hierarchy Definition

**Tier 1: Vendor-Specific Tools** (Highest Priority)
- Python: `uv → pipx → pip`
- Rust: `rustup → cargo`
- Node.js: `nvm → npm`
- Go: Official installer

**Tier 2: GitHub Releases** (Medium Priority)
- Standalone binaries (fd, ripgrep, bat, delta, etc.)
- Direct download from GitHub releases
- User or system bin directory

**Tier 3: System Package Managers** (Lowest Priority)
- apt, brew, dnf, pacman
- System-wide installations
- Slowest updates

### Selection Logic

```python
def select_package_manager(tool: Tool, config: Config) -> str:
    """Choose best package manager for tool based on hierarchy"""

    # 1. Check for config override
    if tool.name in config.tools and 'method' in config.tools[tool.name]:
        return config.tools[tool.name]['method']

    # 2. Follow hierarchy
    if tool.category == 'python':
        # Tier 1: Vendor tools
        if is_available('uv'):
            return 'uv'
        if is_available('pipx'):
            return 'pipx'
        # Tier 3: System fallback
        return 'pip'

    if tool.category == 'rust':
        # Tier 1: Vendor tools
        if is_available('rustup'):
            return 'rustup'
        if is_available('cargo'):
            return 'cargo'
        # Tier 3: System fallback
        return 'apt'  # or brew on macOS

    if tool.has_github_release:
        # Tier 2: GitHub releases
        return 'github'

    # Tier 3: System package manager (detect platform)
    return detect_system_package_manager()  # apt, brew, dnf, etc.
```

### Configuration Override

```yaml
# .cli-audit.yml
tools:
  python:
    method: uv  # Force uv, skip hierarchy
    fallback: pipx

  ripgrep:
    method: cargo  # Prefer cargo over GitHub release

# Global hierarchy override
preferences:
  package_managers:
    python: [uv, pipx, pip]  # Custom order
    rust: [cargo, rustup]    # Reverse default order
```

## Rationale

### Why This Hierarchy?

**Tier 1: Vendor Tools (Highest Priority)**

Advantages:
- **Better Version Management**: rustup, nvm, uv manage multiple versions seamlessly
- **User Isolation**: Installs in user directories (~/.cargo, ~/.local), no sudo required
- **Parallel Installs**: Multiple versions can coexist (nvm for Node.js, rustup for Rust)
- **Faster Updates**: Direct from upstream, no distro lag
- **Tool-Specific Features**: nvm supports .nvmrc, rustup supports toolchains

Example:
```bash
# uv for Python: isolated, fast, no conflicts
uv tool install black

# vs pip: global namespace pollution, permission issues
pip install black  # May require sudo, conflicts with system packages
```

**Tier 2: GitHub Releases (Medium Priority)**

Advantages:
- **Latest Versions**: Direct from maintainers, no distro lag
- **No System Dependencies**: Standalone binaries
- **Cross-Platform**: Same binary on Ubuntu, Fedora, macOS
- **Predictable Installs**: Download + chmod + move, no package manager quirks

Example:
```bash
# fd from GitHub: latest version, no dependencies
wget https://github.com/sharkdp/fd/releases/download/v8.7.0/fd-v8.7.0-x86_64-unknown-linux-gnu.tar.gz
tar xf fd-*.tar.gz
mv fd ~/.local/bin/

# vs apt: older version (8.3.0 vs 8.7.0), system dependency
apt install fd-find  # Slower updates, different binary name (fdfind vs fd)
```

**Tier 3: System Package Managers (Lowest Priority)**

Disadvantages:
- **Slow Updates**: Distros lag upstream releases (often 6-12 months)
- **System-Wide Impact**: Requires sudo, affects all users
- **Conflicts**: May conflict with user-installed versions
- **Version Locks**: Hard to use specific versions

When to Use:
- System dependencies (e.g., Docker, systemd)
- Multi-user servers (consistency across users)
- Security-critical tools (distro security patches)

### Why Allow Configuration Override?

1. **Flexibility**: Users may have valid reasons to prefer different methods
2. **Edge Cases**: Some environments may not have vendor tools available
3. **Organizational Policy**: Companies may enforce specific package managers
4. **Migration**: Gradual migration from system packages to vendor tools

### Why Not Per-Tool Defaults?

- **Consistency**: Users expect similar tools to install the same way
- **Simplicity**: Hierarchy is easy to understand and remember
- **Maintainability**: One hierarchy vs 50+ per-tool configurations

## Consequences

### Positive

- **Better Isolation**: User-level installs avoid permission issues and conflicts
- **Faster Updates**: Vendor tools and GitHub releases provide latest versions
- **Fewer Conflicts**: User installations don't interfere with system packages
- **Consistency**: Predictable installation method for each category

### Negative

- **Learning Curve**: Users must understand hierarchy and when to override
- **Vendor Tool Dependency**: Requires rustup, nvm, uv to be installed first
- **Complexity**: More code paths to test and maintain

### Neutral

- **Configuration Required**: Override requires .cli-audit.yml file
- **Platform Differences**: macOS (brew) vs Linux (apt) requires detection

## Alternatives Considered

### Alternative 1: System Package Managers First

**Description:** Prefer apt/brew over vendor tools

**Hierarchy:** System packages → GitHub → Vendor tools

**Pros:**
- Simpler (no vendor tool bootstrapping)
- System integration (man pages, completions)
- Trusted sources (distro maintainers)

**Cons:**
- Slow updates (6-12 months lag)
- Requires sudo (permission issues)
- Version conflicts (can't install multiple versions)
- Defeats user requirement: "prefer vendor tools"

**Why Rejected:** Doesn't align with user requirements (vendor tools preferred)

### Alternative 2: GitHub Releases First

**Description:** Prefer standalone binaries over everything

**Hierarchy:** GitHub → Vendor tools → System packages

**Pros:**
- Latest versions
- No package manager required
- Cross-platform consistency

**Cons:**
- No version management (can't easily switch versions)
- Manual updates (no auto-upgrade)
- No dependency handling
- Doesn't leverage vendor tool ecosystems (rustup, nvm, uv)

**Why Rejected:** Loses vendor tool benefits (version management, isolation)

### Alternative 3: Flat Preference (No Hierarchy)

**Description:** Require explicit configuration for each tool

```yaml
tools:
  python: { method: uv }
  black: { method: pipx }
  ripgrep: { method: cargo }
  # ... 50+ tools
```

**Pros:**
- Maximum control
- Explicit intent

**Cons:**
- Verbose configuration (50+ tools)
- Poor user experience (manual setup required)
- No sensible defaults

**Why Rejected:** Too much configuration burden, violates "sensible defaults"

### Alternative 4: Single Method per Category

**Description:** Force one method per category (e.g., all Python tools via uv)

**Pros:**
- Simplest implementation
- Consistent within category

**Cons:**
- No fallback if vendor tool unavailable
- Fails on systems without vendor tools installed
- No gradual migration path

**Why Rejected:** Too rigid, no fallback mechanism

## Implementation Notes

### Package Manager Availability Check

```python
def is_available(tool: str) -> bool:
    """Check if package manager is available on PATH"""
    return shutil.which(tool) is not None
```

### Hierarchy Implementation

```python
# Package manager hierarchy per category
PACKAGE_MANAGER_HIERARCHY = {
    'python': ['uv', 'pipx', 'pip'],
    'rust': ['rustup', 'cargo', 'system'],
    'node': ['nvm', 'npm', 'system'],
    'go': ['official', 'system'],
    'standalone': ['github', 'system'],
}

def select_package_manager(tool: Tool, config: Config) -> str:
    """Select best available package manager"""
    # Config override
    if tool.name in config.tools:
        if 'method' in config.tools[tool.name]:
            return config.tools[tool.name]['method']

    # Hierarchy
    category = tool.category
    hierarchy = PACKAGE_MANAGER_HIERARCHY.get(category, ['system'])

    for method in hierarchy:
        if method == 'system':
            return detect_system_package_manager()
        if is_available(method):
            return method

    # Fallback
    return 'system'
```

### Vendor Tool Bootstrapping

```python
def ensure_vendor_tool(tool: str) -> bool:
    """Ensure vendor tool is installed, install if missing"""
    if is_available(tool):
        return True

    # Bootstrap vendor tools
    if tool == 'uv':
        subprocess.run(['curl', '-LsSf', 'https://astral.sh/uv/install.sh', '|', 'sh'])
        return is_available('uv')

    if tool == 'rustup':
        subprocess.run(['curl', '--proto', '=https', '--tlsv1.2', '-sSf', 'https://sh.rustup.rs', '|', 'sh', '-s', '--', '-y'])
        return is_available('rustup')

    if tool == 'nvm':
        # nvm is shell-specific, requires sourcing
        # Provide manual instructions
        return False

    return False
```

### Testing Strategy

1. **Unit Tests**: Test hierarchy selection logic with mocked availability
2. **Integration Tests**: Test installations with all package managers
3. **Fallback Tests**: Verify fallback when preferred method unavailable
4. **Override Tests**: Verify configuration overrides work

## References

- **[PRD.md](../PRD.md#package-manager-hierarchy)** - Phase 2 specification
- **[ADR-001](ADR-001-context-aware-installation.md)** - Context-aware installation modes
- **[ADR-003](ADR-003-parallel-installation-approach.md)** - Parallel installation approach
- User Requirements: "Package manager hierarchy: vendor tools → GitHub → system packages (confirmed)"

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial decision accepted |
