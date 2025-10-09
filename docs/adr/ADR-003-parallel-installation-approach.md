# ADR-003: Parallel Installation Approach (Reconciliation)

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** AI CLI Preparation Team, User Requirements
**Tags:** reconciliation, installation, path-management

## Context

Developers often have tools installed via multiple methods:

- **System Package Manager** (apt, brew): Installed during OS setup or by admin
- **User Package Manager** (cargo, pipx): Installed by developer for latest version
- **Project-Local** (node_modules/.bin): Installed for specific project

**Example Scenario:**
```bash
$ which ripgrep
~/.cargo/bin/rg  # User-installed via cargo (14.1.1)

$ dpkg -l | grep ripgrep
ripgrep  14.0.0  # System-installed via apt
```

**Problem:** When multiple installations exist, should we:
1. **Remove** non-preferred installations (aggressive reconciliation)
2. **Keep** all installations, prefer one via PATH (parallel reconciliation)
3. **Warn** user and require manual resolution

This decision impacts:
- System integrity (removing system packages may break dependencies)
- User autonomy (forced removal vs user choice)
- Rollback capability (can user revert if preferred version has issues?)

## Decision

Implement **parallel installation approach** (reconciliation): Keep all installations, prefer user-level via PATH ordering

### Reconciliation Behavior

**Default: Parallel (Keep Both)**
```
Current State:
  ✓ ripgrep: 14.1.1 (cargo, ~/.cargo/bin) [ACTIVE]
  ℹ️  Also found: 14.0.0 (apt, /usr/bin)

Action: No removal
  - User version takes precedence (PATH ordering)
  - System version remains (may be needed by other users/scripts)
  - User can manually remove system version if desired

PATH Management:
  ~/.cargo/bin:/usr/local/bin:/usr/bin
  ↑ User bins first → takes precedence
```

**Optional: Aggressive (Remove Non-Preferred)**
```yaml
# .cli-audit.yml
preferences:
  reconciliation: aggressive
```

```
Current State:
  ✓ ripgrep: 14.1.1 (cargo, ~/.cargo/bin) [ACTIVE]
  ⚠️  Also found: 14.0.0 (apt, /usr/bin) [WILL REMOVE]

Action: Remove system version
  ⚠️  Warning: This requires sudo and may break system dependencies
  Proceed? [y/N]
```

### PATH Management

**Ensure User Bins First:**
```python
def ensure_path_ordering(config: Config) -> None:
    """Ensure user bin directories appear before system bins in PATH"""
    user_bins = [
        os.path.expanduser('~/.local/bin'),
        os.path.expanduser('~/.cargo/bin'),
        os.path.expanduser('~/.nvm/versions/node/*/bin'),
    ]

    current_path = os.environ['PATH'].split(':')
    system_bins = ['/usr/local/bin', '/usr/bin', '/bin']

    # Verify user bins come before system bins
    for user_bin in user_bins:
        if user_bin in current_path:
            user_idx = current_path.index(user_bin)
            for sys_bin in system_bins:
                if sys_bin in current_path:
                    sys_idx = current_path.index(sys_bin)
                    if user_idx > sys_idx:
                        # BAD: system bin before user bin
                        print(f"⚠️  PATH ordering issue: {sys_bin} before {user_bin}")
                        print(f"💡 Add to ~/.bashrc: export PATH=\"{user_bin}:$PATH\"")
```

**Shell Configuration:**
```bash
# ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# For nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

## Rationale

### Why Parallel (Keep Both)?

**Advantages:**

1. **Safety First**:
   - No accidental removals
   - Preserves system integrity
   - System packages may be dependencies for other packages

2. **User Autonomy**:
   - User retains full control
   - Can manually remove if desired
   - Can switch between versions by adjusting PATH

3. **Rollback Capability**:
   - If user version has issues, fallback to system version
   - Simply adjust PATH ordering, no reinstallation needed

4. **Multi-User Compatibility**:
   - System version remains available for other users
   - Admin can keep system tools while developers use user tools

5. **Explicit User Intent**:
   - User requirement: "Reconciliation: parallel"
   - Matches user's preferred approach

**Example Rollback:**
```bash
# Issue with ripgrep 14.1.1 (cargo version)
# Temporarily use system version 14.0.0
export PATH="/usr/bin:$HOME/.cargo/bin:$PATH"

# Verify
which rg
/usr/bin/rg  # Now using system version

# Permanent rollback: remove cargo version
cargo uninstall ripgrep
```

### Why Not Aggressive by Default?

**Risks:**

1. **System Breakage**:
   - System packages may be dependencies
   - Example: `apt remove ripgrep` → breaks packages depending on ripgrep

2. **Requires sudo**:
   - User must have admin privileges
   - Not always available on shared servers

3. **Irreversible**:
   - Once removed, must reinstall via apt (slower)
   - May require network access

4. **User Surprise**:
   - Unexpected removals violate "principle of least surprise"
   - Users prefer explicit actions

**When Aggressive Makes Sense:**
- Clean development workstation (single user)
- User explicitly requests cleanup
- Disk space constraints
- Version confusion needs resolution

### Why PATH Ordering?

**Standard Unix Behavior:**
- First match in PATH wins
- Predictable, well-understood by developers
- No special logic required

**Visibility:**
```bash
# User can easily verify which version is active
which ripgrep
~/.cargo/bin/rg

# User can see all versions
whereis ripgrep
ripgrep: ~/.cargo/bin/rg /usr/bin/rg

# User can explicitly call non-preferred version
/usr/bin/rg --version  # Force system version
```

## Consequences

### Positive

- **Safety**: No accidental removals, system integrity preserved
- **Flexibility**: User can switch versions by adjusting PATH
- **Rollback**: Easy fallback if preferred version has issues
- **Multi-User**: System installations remain for other users
- **User Control**: Explicit user choice for aggressive reconciliation

### Negative

- **Disk Space**: Multiple installations consume more space (mitigated: tools are small)
- **PATH Complexity**: Users must understand PATH ordering
- **Confusion**: Multiple versions may confuse inexperienced users

### Neutral

- **Manual Cleanup**: User must manually remove unwanted versions (if desired)
- **Configuration Required**: Aggressive mode requires .cli-audit.yml override

## Alternatives Considered

### Alternative 1: Aggressive by Default

**Description:** Automatically remove non-preferred installations

**Pros:**
- Clean system (one version per tool)
- No PATH confusion
- Reduces disk space

**Cons:**
- Dangerous (may break system)
- Requires sudo
- Irreversible
- Violates user requirement: "parallel"

**Why Rejected:** Too risky, doesn't align with user requirements

### Alternative 2: Warn and Require Manual Resolution

**Description:** Detect conflicts, warn user, refuse to proceed

```
⚠️  Conflict detected: ripgrep installed via apt and cargo
Action required: Manually remove one installation
```

**Pros:**
- Forces user awareness
- User makes explicit choice

**Cons:**
- Poor user experience (blocks installation)
- Requires manual intervention
- Slows down workflow

**Why Rejected:** Creates friction, doesn't solve user problem

### Alternative 3: Symlink Preferred Version

**Description:** Create symlinks to preferred version in user bin

```bash
ln -sf ~/.cargo/bin/rg ~/.local/bin/rg
```

**Pros:**
- Explicit preferred version
- No PATH complexity

**Cons:**
- Breaks if source moves
- Requires manual symlink management
- Not cross-platform (Windows)

**Why Rejected:** Adds complexity without clear benefit over PATH ordering

### Alternative 4: Version Switching Tool (like nvm)

**Description:** Implement tool version manager (e.g., `cli_audit use ripgrep 14.1.1`)

**Pros:**
- Fine-grained control
- Easy switching

**Cons:**
- Massive scope increase
- Duplicates existing tools (rustup, nvm, uv)
- Out of scope for Phase 2

**Why Rejected:** Too complex, already solved by vendor tools

## Implementation Notes

### Detection Logic

```python
def detect_installations(tool: Tool) -> list[Installation]:
    """Find all installations of a tool"""
    installations = []

    # Search PATH
    for path_dir in os.environ['PATH'].split(':'):
        for candidate in tool.candidates:
            full_path = os.path.join(path_dir, candidate)
            if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                version = get_version(full_path)
                method = classify_install_method(full_path)
                installations.append(Installation(
                    path=full_path,
                    version=version,
                    method=method,
                    active=(full_path == shutil.which(candidate))
                ))

    return installations
```

### Reconciliation Report

```python
def report_reconciliation(tool: Tool, installations: list[Installation]) -> None:
    """Report reconciliation status"""
    print(f"Reconciling {tool.name} installations:\n")

    print("Found {} installations:".format(len(installations)))
    for i, inst in enumerate(installations, 1):
        active_marker = "[ACTIVE]" if inst.active else ""
        preferred_marker = "[PREFERRED]" if i == 1 else ""
        print(f"  [{i}] {inst.version} ({inst.method}, {inst.path}) {active_marker} {preferred_marker}")

    print(f"\nStrategy: parallel (keep both)")
    print(f"\nActions:")
    print(f"  ✓ PATH ordering ensures [1] is active")
    if len(installations) > 1:
        print(f"  ℹ️  Other installations remain available")
        print(f"  💡 Run 'cli_audit reconcile --aggressive {tool.name}' to remove non-preferred")

    # PATH verification
    current_path = os.environ['PATH']
    print(f"\nCurrent PATH:")
    print(f"  {current_path}")
    print(f"  ↑ {installations[0].path} will be used")
```

### Aggressive Reconciliation

```python
def aggressive_reconcile(tool: Tool, installations: list[Installation], config: Config) -> None:
    """Remove non-preferred installations (requires confirmation)"""
    preferred = installations[0]
    others = installations[1:]

    print(f"⚠️  WARNING: Aggressive reconciliation will remove {len(others)} installation(s)\n")

    for inst in others:
        print(f"  - {inst.version} ({inst.method}, {inst.path})")

    if not confirm("Proceed with removal? [y/N]: "):
        print("Aborted.")
        return

    for inst in others:
        if inst.method == 'apt' or inst.method == 'brew':
            # System package removal
            if not has_sudo():
                print(f"❌ Cannot remove {inst.path}: requires sudo")
                continue

            subprocess.run(['sudo', 'apt', 'remove', '-y', tool.name])
            print(f"✓ Removed {inst.path}")

        elif inst.method == 'cargo':
            subprocess.run(['cargo', 'uninstall', tool.name])
            print(f"✓ Removed {inst.path}")

        elif inst.method == 'pipx':
            subprocess.run(['pipx', 'uninstall', tool.name])
            print(f"✓ Removed {inst.path}")

        else:
            print(f"⚠️  Manual removal required for {inst.path}")
```

### Testing Strategy

1. **Unit Tests**: Mock multiple installations, verify detection
2. **Integration Tests**: Install via multiple methods, verify reconciliation
3. **PATH Tests**: Verify PATH ordering logic
4. **Aggressive Tests**: Test removal with mocked package managers

## References

- **[PRD.md](../PRD.md#parallel-installation-approach)** - Phase 2 specification
- **[ADR-001](ADR-001-context-aware-installation.md)** - Context-aware installation modes
- **[ADR-002](ADR-002-package-manager-hierarchy.md)** - Package manager hierarchy
- User Requirements: "Reconciliation aggressiveness: parallel"

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial decision accepted |
