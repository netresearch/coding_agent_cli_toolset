# ADR-004: Always-Latest Version Policy

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** AI CLI Preparation Team, User Requirements
**Tags:** versioning, upgrades, breaking-changes

## Context

Developer tools release new versions frequently with:
- **Patch releases** (14.0.0 → 14.0.1): Bug fixes, no breaking changes
- **Minor releases** (14.0.0 → 14.1.0): New features, backwards compatible
- **Major releases** (13.0.0 → 14.0.0): Breaking changes, incompatible APIs

When upgrading tools, we must decide:
1. Should we auto-upgrade to latest versions?
2. How do we handle breaking changes (major version bumps)?
3. Should users approve upgrades, or should they happen automatically?

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Always Latest** | Performance, features, bug fixes | Breaking changes may disrupt workflow |
| **Conservative** | Stability, predictability | Missing improvements, security fixes |
| **User Approval** | User control | Slow, requires manual intervention |

**Problem:** What version selection policy balances performance (latest features) with stability (avoid breakage)?

## Decision

Implement **always-latest version policy** with breaking change warnings:

### Version Selection Rules

**1. Default: Always Latest**
```python
def get_target_version(tool: Tool, installed: str, latest: str) -> str:
    """Determine target version for installation/upgrade"""
    return latest  # Always prefer latest available version
```

**2. Major Version Upgrade: Warn User**
```python
def is_major_upgrade(current: str, latest: str) -> bool:
    """Check if upgrade crosses major version boundary"""
    try:
        curr_major = int(current.split('.')[0])
        latest_major = int(latest.split('.')[0])
        return latest_major > curr_major
    except (ValueError, IndexError):
        return False  # Conservative: assume major if parsing fails

def upgrade_tool(tool: Tool, current: str, latest: str) -> Result:
    """Upgrade tool with breaking change warnings"""
    if is_major_upgrade(current, latest):
        # Warn user
        print(f"⚠️  Major version upgrade detected:")
        print(f"    Tool: {tool.name}")
        print(f"    Current: {current}")
        print(f"    Latest: {latest}")
        print(f"\n    Potential breaking changes:")
        print(f"    - API changes")
        print(f"    - Flag deprecations")
        print(f"    - Output format changes")
        print(f"\n    Review release notes: {tool.release_notes_url}")

        # Context-aware handling
        if detect_environment() == 'workstation':
            if not confirm("Proceed with upgrade? [Y/n]: ", default=True):
                return Result.skipped("User declined major upgrade")
        elif detect_environment() == 'server':
            if not confirm("Proceed with upgrade? [y/N]: ", default=False):
                return Result.skipped("User declined major upgrade")
        elif detect_environment() == 'ci':
            return Result.skipped("Major upgrades disabled in CI")

    # Minor/patch upgrades: no confirmation needed
    return install_version(tool, latest)
```

**3. Configuration Overrides**
```yaml
# .cli-audit.yml
preferences:
  breaking_changes: accept  # accept | warn | reject
  auto_upgrade: true        # Auto-upgrade minor/patch versions

tools:
  python:
    version: "3.12.*"  # Lock to 3.12.x (no major upgrades)

  ripgrep:
    version: "latest"  # Always latest (default)

  node:
    version: "=20.10.0"  # Exact version lock
```

**4. Rollback Capability**
```bash
# Before upgrade, create restore point
cli_audit upgrade --create-snapshot

# After upgrade, if issues occur
cli_audit rollback --from-snapshot

# Manual rollback: reinstall previous version
cli_audit install ripgrep@13.0.0
```

## Rationale

### Why Always Latest?

**Performance and Features:**
- Latest versions include performance improvements (e.g., ripgrep 14.x is 20% faster than 13.x)
- New features improve developer productivity (e.g., ast-grep pattern matching improvements)
- Bug fixes prevent issues (e.g., security vulnerabilities, edge case crashes)

**AI Agent Performance:**
- AI agents benefit from latest tool capabilities
- Newer versions often have better error messages (easier for agents to parse)
- Feature parity with documentation (agents reference latest docs)

**Security:**
- CVE fixes in latest versions
- Deprecated features removed (reduces attack surface)

**User Requirement:**
- Explicit requirement: "Breaking change tolerance: always latest"
- Developer workstations prioritize performance over stability

**Example: ripgrep 13.x → 14.x**
```
Performance improvements:
  - 20% faster on large codebases
  - Better Unicode handling
  - Improved regex engine

Breaking changes:
  - Flag --context renamed to -C (minor workflow impact)
  - Deprecated --smart-case removed (use -S instead)

Net impact: Significant performance gain >> minor flag changes
```

### Why Warn for Major Upgrades?

**Balance Safety and Progress:**

1. **User Awareness**: Major upgrades often have breaking changes
2. **Informed Decision**: User reviews release notes before proceeding
3. **Context-Aware**: Workstation (default: accept), Server (default: reject), CI (always reject)
4. **Rollback Available**: User can revert if issues occur

**Breaking Change Examples:**

| Tool | Version | Breaking Change | Impact |
|------|---------|-----------------|--------|
| Python | 3.11 → 3.12 | Removed deprecated APIs (PEP 594) | High (code changes) |
| ripgrep | 13.x → 14.x | Flag renames | Low (workflow) |
| Node.js | 18.x → 20.x | OpenSSL 3.0, V8 updates | Medium (dependencies) |

**Warning Output:**
```
⚠️  Major version upgrade: python 3.11.5 → 3.12.1

Potential breaking changes:
  - Removed deprecated modules (see PEP 594)
  - Changes to f-string syntax
  - Type inference improvements may expose bugs

Impact assessment:
  - 12 project dependencies may require updates
  - Estimated compatibility: 85%
  - Review release notes: https://docs.python.org/3/whatsnew/3.12.html

Proceed with upgrade? [Y/n]
```

### Why Not Conservative (Lock Versions)?

**Stagnation Risks:**
- Miss performance improvements (e.g., 20% faster ripgrep)
- Miss security fixes (CVEs in old versions)
- Diverge from documentation (agents reference latest docs)
- Technical debt accumulates (harder to upgrade after long delay)

**Example: Python 3.8 (2019) vs 3.12 (2023)**
```
Performance: 3.12 is 25% faster (PEP 659 adaptive interpreter)
Features: Pattern matching, improved error messages, faster asyncio
Security: Multiple CVEs fixed in 3.9-3.12
Type hints: Improved static analysis (better IDE support)

Cost of staying on 3.8:
  - Slower code execution
  - Missing features for new projects
  - Unsupported (EOL October 2024)
```

### Why Auto-Upgrade Minor/Patch?

**Low Risk:**
- Semantic versioning guarantees backwards compatibility
- Patch: Bug fixes only (14.0.0 → 14.0.1)
- Minor: New features, no breaking changes (14.0.0 → 14.1.0)

**High Value:**
- Security fixes in patch releases
- Bug fixes prevent issues
- New features available immediately

**Example: ripgrep 14.0.0 → 14.0.1**
```
Changes:
  - Fix crash on malformed UTF-8
  - Improve performance on Windows
  - Fix regex edge case

Risk: Minimal (bug fixes only)
Value: Prevents crashes, improves performance
```

## Consequences

### Positive

- **Performance**: Latest versions provide speed improvements
- **Security**: CVE fixes applied automatically
- **Features**: New capabilities available immediately
- **Documentation Alignment**: Tools match latest docs
- **AI Agent Performance**: Agents leverage latest features

### Negative

- **Breaking Changes**: Major upgrades may disrupt workflows
- **Testing Burden**: User must validate major upgrades
- **Rollback Required**: User may need to revert if issues occur

### Neutral

- **User Responsibility**: User handles breaking changes (explicit requirement)
- **Configuration Required**: Version locks require .cli-audit.yml

## Alternatives Considered

### Alternative 1: Conservative (Lock to Current)

**Description:** Never auto-upgrade, require explicit user action

```python
def get_target_version(tool: Tool, installed: str, latest: str) -> str:
    return installed  # Stay on current version
```

**Pros:**
- Maximum stability
- No breaking changes
- Predictable environment

**Cons:**
- Miss performance improvements
- Miss security fixes
- Stagnation over time
- Violates user requirement: "always latest"

**Why Rejected:** Doesn't align with user requirements, misses performance gains

### Alternative 2: Auto-Upgrade Everything (No Warnings)

**Description:** Upgrade to latest without warnings, even major versions

**Pros:**
- Simplest implementation
- Always latest
- No user intervention

**Cons:**
- Breaking changes surprise users
- May break workflows without warning
- No rollback preparation
- Dangerous on servers

**Why Rejected:** Too risky, doesn't respect major version breakage

### Alternative 3: Prompt for All Upgrades

**Description:** Require user confirmation for all upgrades (minor/patch/major)

```
Upgrade ripgrep 14.0.0 → 14.0.1 (patch)?
Upgrade fd 8.7.0 → 8.7.1 (patch)?
Upgrade bat 0.24.0 → 0.24.1 (patch)?
... (50+ prompts)
```

**Pros:**
- Maximum user control
- Explicit awareness

**Cons:**
- Poor user experience (50+ prompts)
- Slows workflow
- Users blindly accept anyway
- Misses value of semantic versioning

**Why Rejected:** Too much friction, semantic versioning makes minor/patch safe

### Alternative 4: Version Range Locking

**Description:** Auto-upgrade within ranges (e.g., 14.x.x but not 15.x.x)

```yaml
tools:
  ripgrep:
    version: "14.*"  # Auto-upgrade 14.0.0 → 14.1.0 → 14.2.0, not 15.0.0
```

**Pros:**
- Balance safety and updates
- Standard in package managers (npm, cargo)

**Cons:**
- Requires configuration for all tools
- Delays major version benefits
- Doesn't align with "always latest" requirement

**Why Rejected:** Adds complexity, doesn't match user requirement (always latest)

## Implementation Notes

### Version Comparison

```python
from packaging import version

def compare_versions(v1: str, v2: str) -> int:
    """Compare versions, return -1 (v1 < v2), 0 (equal), 1 (v1 > v2)"""
    try:
        ver1 = version.parse(v1)
        ver2 = version.parse(v2)
        if ver1 < ver2:
            return -1
        if ver1 > ver2:
            return 1
        return 0
    except Exception:
        # Fallback: string comparison
        return -1 if v1 < v2 else (1 if v1 > v2 else 0)
```

### Breaking Change Detection

```python
def detect_breaking_changes(tool: Tool, from_ver: str, to_ver: str) -> list[str]:
    """Detect potential breaking changes (heuristic-based)"""
    changes = []

    if is_major_upgrade(from_ver, to_ver):
        changes.append("Major version upgrade (potential breaking changes)")
        changes.append(f"Review release notes: {tool.release_notes_url}")

        # Tool-specific heuristics
        if tool.name == 'python':
            changes.append("Check for removed deprecated modules (PEP 594)")
            changes.append("Test type hints (improved type checking)")

        if tool.name == 'node':
            changes.append("Check npm package compatibility")
            changes.append("Test native modules (V8 API changes)")

    return changes
```

### Snapshot Creation (Rollback Preparation)

```python
def create_upgrade_snapshot(tools: list[Tool]) -> Snapshot:
    """Create snapshot before upgrade for rollback"""
    snapshot = {
        '__meta__': {
            'created_at': datetime.now().isoformat(),
            'purpose': 'pre-upgrade-rollback',
            'count': len(tools),
        },
        'tools': []
    }

    for tool in tools:
        installed_version = get_installed_version(tool)
        snapshot['tools'].append({
            'tool': tool.name,
            'version': installed_version,
            'method': classify_install_method(tool),
            'path': shutil.which(tool.candidates[0]),
        })

    snapshot_path = f'.cli-audit-snapshot-{int(time.time())}.json'
    with open(snapshot_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    print(f"✓ Snapshot created: {snapshot_path}")
    return snapshot
```

### Testing Strategy

1. **Unit Tests**: Test version comparison, major upgrade detection
2. **Integration Tests**: Test upgrades with mocked package managers
3. **Rollback Tests**: Test snapshot creation and restoration
4. **Breaking Change Tests**: Test warning messages and confirmations

## References

- **[PRD.md](../PRD.md#always-latest-version-policy)** - Phase 2 specification
- **[ADR-001](ADR-001-context-aware-installation.md)** - Context-aware installation modes
- **[ADR-003](ADR-003-parallel-installation-approach.md)** - Parallel installation approach
- User Requirements: "Breaking change tolerance: always latest"
- Semantic Versioning: https://semver.org/

---

**Revision History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial decision accepted |
