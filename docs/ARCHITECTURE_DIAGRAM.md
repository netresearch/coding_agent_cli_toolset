# AI CLI Preparation - Architecture Diagrams

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-09

## Module Dependency Graph

### Phase 2 Package Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2 Architecture                      │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │  common.py   │  (Shared utilities)
                    └──────────────┘
                            ↑
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────────────┐                      ┌──────────────┐
│ environment.py│                      │ logging_     │
│               │                      │ config.py    │
└───────┬───────┘                      └──────────────┘
        │                                      ↑
        ↓                                      │
┌───────────────┐                              │
│   config.py   │                              │
│ (Config, Prefs)                             │
└───────┬───────┘                              │
        │                                      │
        ↓                                      │
┌───────────────────┐                          │
│ package_          │                          │
│ managers.py       │                          │
└─────────┬─────────┘                          │
          │                                    │
          ↓                                    │
┌───────────────────┐                          │
│ install_plan.py   │                          │
│ (Plan, Step)      │                          │
└─────────┬─────────┘                          │
          │                                    │
          ↓                                    │
┌───────────────────┐                          │
│   installer.py    │◄─────────────────────────┘
│ (Core execution)  │           Uses logging
└─────────┬─────────┘
          │
          ├────────────────┬──────────────────┬──────────────┐
          ↓                ↓                  ↓              ↓
┌─────────────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────┐
│    bulk.py      │  │ upgrade.py │  │reconcile.py  │  │breaking_ │
│ (Parallel ops)  │  │(Versions)  │  │(Conflicts)   │  │changes.py│
└─────────────────┘  └────┬───────┘  └──────────────┘  └────┬─────┘
                          │                                  │
                          └──────────────────────────────────┘
                                 upgrade.py imports
                                 breaking_changes.py

Legend:
  ┌─────┐
  │ Box │  = Module
  └─────┘
     │
     ↓     = Dependency (imports from)
```

### Dependency Layers

```
Layer 1 (Foundation):
  - common.py          [Shared utilities]
  - logging_config.py  [Logging infrastructure]

Layer 2 (Context):
  - environment.py     [System detection]
  - config.py          [Configuration management]

Layer 3 (Resources):
  - package_managers.py [PM abstraction]

Layer 4 (Planning):
  - install_plan.py    [Plan generation]

Layer 5 (Execution):
  - installer.py       [Core installation]

Layer 6 (High-Level Operations):
  - bulk.py            [Parallel operations]
  - upgrade.py         [Version management]
  - reconcile.py       [Conflict resolution]
  - breaking_changes.py [Breaking change detection]
```

### Import Matrix

| Module | Imports From |
|--------|--------------|
| common.py | (no internal imports) |
| logging_config.py | (no internal imports) |
| environment.py | common |
| config.py | common |
| package_managers.py | common, config |
| install_plan.py | common, config, package_managers |
| installer.py | common, config, package_managers, install_plan, logging_config |
| bulk.py | common, config, installer, logging_config |
| upgrade.py | common, config, installer, breaking_changes, logging_config |
| breaking_changes.py | config |
| reconcile.py | common, config, installer, upgrade, logging_config |

**Zero Circular Dependencies** ✅

---

## Data Flow Diagrams

### Single Tool Installation Flow

```
User Code
   │
   ↓
install_tool(tool_name, package_name, version, config, env)
   │
   ├─→ select_package_manager(language, config, env)
   │        └─→ Returns: PackageManager
   │
   ├─→ generate_install_plan(tool, package, version, pm)
   │        └─→ Returns: InstallPlan (steps)
   │
   └─→ Execute plan steps:
       │
       ├─→ execute_step_with_retry(step, max_retries)
       │        │
       │        ├─→ execute_step(step)
       │        │        └─→ subprocess.run(command)
       │        │
       │        └─→ Retry on transient failures
       │
       ├─→ validate_installation(tool_name, version)
       │        └─→ shutil.which() + version check
       │
       └─→ Returns: InstallResult
```

### Bulk Installation Flow

```
User Code
   │
   ↓
bulk_install(mode, tool_names, config, env)
   │
   ├─→ get_missing_tools(tool_names)
   │        └─→ Filter to tools not installed
   │
   ├─→ resolve_dependencies(tool_specs)
   │        └─→ Topological sort → levels
   │
   └─→ For each level:
       │
       ├─→ ThreadPoolExecutor(max_workers)
       │        │
       │        └─→ Parallel: install_tool() for each tool
       │
       ├─→ ProgressTracker.update() (thread-safe)
       │
       └─→ Collect results
           │
           └─→ Returns: BulkInstallResult
```

### Upgrade Workflow

```
User Code
   │
   ↓
get_upgrade_candidates(tools, config, env)
   │
   ├─→ For each tool:
   │   │
   │   ├─→ get_available_version(tool, pm, cache_ttl)
   │   │        │
   │   │        ├─→ Check version cache (1 hour TTL)
   │   │        ├─→ Query upstream API
   │   │        └─→ Update cache
   │   │
   │   ├─→ compare_versions(current, available)
   │   │        └─→ semantic versioning comparison
   │   │
   │   ├─→ is_major_upgrade(current, available)
   │   │        └─→ breaking_changes.py
   │   │
   │   └─→ Create: UpgradeCandidate
   │
   └─→ filter_by_breaking_changes(candidates, policy)
       │
       └─→ Returns: (allowed, blocked)
           │
           ↓
upgrade_tool(tool, target_version, config, env)
   │
   ├─→ create_upgrade_backup(tool)
   │        └─→ Save current binary + metadata
   │
   ├─→ install_tool(tool, target_version)
   │
   ├─→ validate_installation(tool, target_version)
   │
   └─→ Returns: UpgradeResult
```

### Reconciliation Workflow

```
User Code
   │
   ↓
reconcile_tool(tool_name, config, env)
   │
   ├─→ detect_installations(tool_name)
   │        │
   │        ├─→ Search PATH + common locations
   │        ├─→ classify_install_method(path)
   │        │        │
   │        │        ├─→ Pattern matching:
   │        │        │    ~/.cargo/ → "cargo"
   │        │        │    ~/.local/bin/ → "pipx"
   │        │        │    /usr/bin/ → "apt/dpkg"
   │        │        │    etc.
   │        │        │
   │        │        └─→ Returns: Installation(path, method, version)
   │        │
   │        └─→ Returns: List[Installation]
   │
   ├─→ sort_by_preference(installations, config)
   │        │
   │        ├─→ Tier 1: User tools (pipx, cargo)
   │        ├─→ Tier 2: Version managers (nvm, pyenv)
   │        ├─→ Tier 3: System tools (apt, brew)
   │        │
   │        └─→ Within tier: sort by version (highest first)
   │
   ├─→ Check SYSTEM_TOOL_SAFELIST
   │        └─→ Protect critical tools (sh, bash, python, etc.)
   │
   ├─→ Select preferred installation (index 0)
   │
   ├─→ Remove other installations
   │        └─→ Generate uninstall commands per method
   │
   └─→ Returns: ReconciliationResult
```

---

## Component Interaction Patterns

### Pattern 1: Config-Driven Behavior

```
┌────────────┐
│   User     │
│  Provides  │
│  .cli-     │
│  audit.yml │
└─────┬──────┘
      │
      ↓
┌────────────┐      ┌──────────────┐
│ load_config│─────→│   Config     │
└────────────┘      │  (frozen     │
                    │ dataclass)   │
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ↓               ↓               ↓
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ installer  │  │   bulk     │  │  upgrade   │
    │  uses      │  │   uses     │  │   uses     │
    │ config.    │  │ config.    │  │ config.    │
    │preferences │  │preferences │  │preferences │
    └────────────┘  └────────────┘  └────────────┘
```

**Key Config Uses:**
- `config.preferences.breaking_changes` → upgrade policy
- `config.preferences.max_workers` → parallel execution
- `config.preferences.cache_ttl_seconds` → version cache
- `config.preferences.reconciliation` → conflict strategy
- `config.get_tool_config(tool)` → tool-specific settings

### Pattern 2: Progressive Enhancement

```
Simple → Complex

install_tool()
    ↓ (single tool)
bulk_install()
    ↓ (multiple tools, parallel)
bulk_upgrade()
    ↓ (version management)
bulk_reconcile()
    ↓ (conflict resolution)
```

Each level builds on the previous, adding:
- More concurrency
- More error handling
- More user interaction
- More validation

### Pattern 3: Retry with Backoff

```
execute_step_with_retry(step, max_retries=3)
    │
    ├─→ Attempt 1: execute_step()
    │        ├─→ Success → return
    │        └─→ Failure → check if retryable
    │
    ├─→ Sleep: base * 2^0 + jitter
    │
    ├─→ Attempt 2: execute_step()
    │        ├─→ Success → return
    │        └─→ Failure → check if retryable
    │
    ├─→ Sleep: base * 2^1 + jitter
    │
    └─→ Attempt 3: execute_step()
         ├─→ Success → return
         └─→ Failure → return error

Retryable Errors:
  - Network: "connection refused", "timed out"
  - Resource: "could not get lock"
  - Transient: HTTP 429, 503, 504

Non-Retryable Errors:
  - Not found: "package not found"
  - Permission: "permission denied"
  - Invalid: "invalid version"
```

### Pattern 4: Thread-Safe Progress Tracking

```
┌────────────────────────────────────┐
│     ThreadPoolExecutor             │
│                                    │
│  ┌──────────┐  ┌──────────┐       │
│  │ Worker 1 │  │ Worker 2 │  ...  │
│  └────┬─────┘  └────┬─────┘       │
│       │             │              │
│       └─────┬───────┘              │
└─────────────┼────────────────────┘
              │
              ↓ (thread-safe updates)
    ┌─────────────────────┐
    │  ProgressTracker    │
    │                     │
    │  _lock: Lock        │
    │  _progress: dict    │
    │                     │
    │  def update():      │
    │    with self._lock: │
    │      update dict    │
    └─────────────────────┘
              │
              ↓ (callback)
    ┌─────────────────────┐
    │  User Callback      │
    │  (display progress) │
    └─────────────────────┘
```

---

## Security Architecture

### Subprocess Safety

```
ALL subprocess calls use list arguments:
✅ subprocess.run(["cargo", "install", tool])
❌ subprocess.run(f"cargo install {tool}", shell=True)  # NEVER

No shell=True found in entire codebase
```

### Input Validation

```
User Input → Validation → Safe Execution

tool_name (str)
    ├─→ No validation needed (used in list args)
    └─→ Safe: ["cargo", "install", tool_name]

version (str)
    ├─→ Parse with packaging.version
    └─→ Semantic version validation

config_file (Path)
    ├─→ YAML safe_load() (not unsafe load)
    └─→ Schema validation via dataclasses
```

### System Tool Protection

```
SYSTEM_TOOL_SAFELIST = {
    "sh", "bash", "zsh", "fish",
    "python", "python3",
    "git", "ssh", "sudo",
    # ... 26 total
}

Before uninstall:
    if tool in SYSTEM_TOOL_SAFELIST:
        raise Error("Cannot uninstall system tool")
```

---

## Performance Architecture

### Concurrency Model

```
I/O-Bound Workload → ThreadPoolExecutor (appropriate choice)
NOT ProcessPoolExecutor (GIL not a bottleneck)

┌────────────────────────────────────┐
│     Main Thread                    │
│                                    │
│  ThreadPoolExecutor(max_workers)   │
│  ┌──────────────────────────────┐  │
│  │ Worker Pool (default: 16)    │  │
│  │                              │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐   │  │
│  │  │ W1  │ │ W2  │ │ W3  │...│  │
│  │  └──┬──┘ └──┬──┘ └──┬──┘   │  │
│  │     │       │       │        │  │
│  │     ↓       ↓       ↓        │  │
│  │  ┌──────────────────────┐   │  │
│  │  │  Task Queue          │   │  │
│  │  │  [install(ripgrep),  │   │  │
│  │  │   install(fd),       │   │  │
│  │  │   install(bat), ...]  │   │  │
│  │  └──────────────────────┘   │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
         │
         ↓ (subprocess.run)
┌────────────────────────────────────┐
│  External Processes                 │
│  cargo, pipx, npm, etc.             │
└────────────────────────────────────┘
```

### Caching Strategy

```
┌──────────────────────────────────────┐
│     Version Query Flow                │
└──────────────────────────────────────┘

get_available_version(tool, pm, cache_ttl)
    │
    ├─→ Check in-memory cache (TTL: 1 hour)
    │   └─→ HIT → return cached version
    │
    ├─→ MISS → Query upstream API
    │   │
    │   ├─→ Check hints cache (last working method)
    │   │        └─→ Try: github/pypi/crates/npm
    │   │
    │   ├─→ Retry with exponential backoff (2x)
    │   │
    │   ├─→ SUCCESS:
    │   │   ├─→ Update in-memory cache
    │   │   ├─→ Update hints cache
    │   │   └─→ Write to latest_versions.json
    │   │
    │   └─→ FAILURE:
    │       └─→ Fallback to latest_versions.json
    │           └─→ Return cached or "UNKNOWN"
    │
    └─→ Returns: version string

Multi-Tier Cache Hierarchy:
1. In-memory (fastest)
2. Hints (method preference)
3. Manual cache (latest_versions.json)
4. Snapshot (tools_snapshot.json)
```

### Lock Hierarchy

```
MANUAL_LOCK (file-level cache updates)
    └─→ HINTS_LOCK (hints section updates)

Rule: Always acquire MANUAL_LOCK before HINTS_LOCK
Prevents: Deadlocks

with MANUAL_LOCK:
    # Update latest_versions.json
    with HINTS_LOCK:
        # Update __hints__ section
```

---

## Error Handling Architecture

### Exception Hierarchy

```
Exception
    ├─→ InstallError (custom)
    │   ├─→ retryable: bool
    │   ├─→ remediation: str | None
    │   └─→ Used by: installer.py, bulk.py
    │
    ├─→ subprocess.CalledProcessError
    │   └─→ Caught and converted to InstallError
    │
    ├─→ subprocess.TimeoutExpired
    │   └─→ Caught and retried or failed
    │
    └─→ FileNotFoundError
        └─→ Caught for command not found errors
```

### Error Classification

```
is_retryable_error(exit_code, stderr):
    │
    ├─→ Network errors:
    │   ├─→ "connection refused"
    │   ├─→ "connection timed out"
    │   └─→ "network unreachable"
    │   → retryable = True
    │
    ├─→ Resource contention:
    │   └─→ "could not get lock"
    │   → retryable = True
    │
    ├─→ Rate limiting:
    │   └─→ HTTP 429, 503, 504
    │   → retryable = True
    │
    └─→ All others:
        → retryable = False
```

### Graceful Degradation

```
Try Operation
    ├─→ Success → return result
    │
    └─→ Failure:
        ├─→ Log warning
        ├─→ Try fallback method
        │   ├─→ Success → return result
        │   └─→ Failure:
        │       ├─→ Log error
        │       └─→ Return safe default (empty, None, "UNKNOWN")
        └─→ Continue execution (don't crash)

Example: Version lookup failure
  → Try GitHub → Fail
  → Try cache → Fail
  → Mark as "UNKNOWN"
  → Continue with other tools
```

---

## Deployment Architecture

### Offline Mode

```
┌──────────────────────────────────────┐
│     Online Mode (Default)            │
└──────────────────────────────────────┘
    │
    ├─→ Network available
    ├─→ Query upstream APIs
    ├─→ Update caches
    └─→ Full version checking

┌──────────────────────────────────────┐
│     Offline Mode                      │
│     (CLI_AUDIT_OFFLINE=1)            │
└──────────────────────────────────────┘
    │
    ├─→ No network requests
    ├─→ Use committed cache (latest_versions.json)
    ├─→ Use snapshot (tools_snapshot.json)
    └─→ Baseline version checking only
```

### Snapshot Workflow

```
┌───────────────────────────────────┐
│  Collect Phase (make update)      │
│  - Verbose output                 │
│  - Network queries                │
│  - Cache updates                  │
│  - Write snapshot                 │
└─────────────┬─────────────────────┘
              │
              ↓
    ┌─────────────────────┐
    │ tools_snapshot.json │
    │                     │
    │ {                   │
    │   "__meta__": {...},│
    │   "tools": [...]    │
    │ }                   │
    └─────────┬───────────┘
              │
              ↓
┌───────────────────────────────────┐
│  Render Phase (make audit)        │
│  - Silent/fast                    │
│  - No network                     │
│  - Read snapshot                  │
│  - Print table                    │
└───────────────────────────────────┘
```

---

## Document Status

**Created:** 2025-10-09
**Purpose:** Visual architecture documentation for component relationships
**Audience:** Developers, architects, maintainers
**Maintenance:** Update when adding new modules or changing dependencies

**Related Documents:**
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Detailed architecture
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Master navigation
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - API documentation
