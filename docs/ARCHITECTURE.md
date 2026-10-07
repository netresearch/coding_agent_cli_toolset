# Architecture Documentation

## Overview

AI CLI Preparation is designed as a **fast, reliable, offline-first tool version auditing system** for AI coding agent environments. The architecture emphasizes resilience, performance, and graceful degradation under network failures or rate limiting.

### Design Philosophy

1. **Offline-First:** Can operate without network access using committed cache
2. **Resilient:** Multiple fallback layers handle failures gracefully
3. **Parallel:** Concurrent execution for fast audits (16 workers default)
4. **Immutable Data:** Frozen dataclasses and atomic file writes
5. **Separation of Concerns:** Decouple collection (network) from rendering (local)

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ CLI Entry Point (main)                                  │
│ - Argument parsing                                      │
│ - Mode detection (COLLECT/RENDER/NORMAL)               │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────v─────────────────────────────────┐
│ Mode Router                                             │
│ ├─ COLLECT_ONLY → Data Collection Pipeline             │
│ ├─ RENDER_ONLY  → Snapshot Renderer                    │
│ └─ NORMAL       → Full Audit (Collect + Render)        │
└───────────────────────┬─────────────────────────────────┘
                        │
    ┌───────────────────┴──────────────────┐
    │                                       │
    v                                       v
┌───────────────────────┐      ┌──────────────────────────┐
│ Data Collection       │      │ Snapshot Renderer        │
│ Pipeline              │      │ - Load snapshot          │
│ (ThreadPoolExecutor)  │      │ - Filter/sort tools      │
└───────────┬───────────┘      │ - Format output          │
            │                  │ - Stream or batch        │
            v                  └──────────────────────────┘
┌───────────────────────────────────────────┐
│ Parallel Tool Audit (audit_tool × N)     │
│ - 16 concurrent workers (configurable)   │
│ - Timeout per tool: 3s                   │
│ - Independent failure isolation          │
└───────────┬───────────────────────────────┘
            │
            v
┌───────────────────────────────────────────────────────┐
│ Per-Tool Pipeline                                     │
│ 1. Local Discovery                                    │
│    └─ find_paths → get_version_line → classify       │
│ 2. Upstream Check                                     │
│    └─ get_latest → cache → http_fetch                │
│ 3. Comparison & Status                                │
│    └─ version_compare → status_icon                  │
└───────────┬───────────────────────────────────────────┘
            │
    ┌───────┴────────┐
    v                v
┌──────────────┐  ┌─────────────────┐
│ Local        │  │ Upstream APIs   │
│ Discovery    │  │ - GitHub        │
│ - PATH       │  │ - PyPI          │
│ - Version    │  │ - crates.io     │
│ - Classify   │  │ - npm registry  │
└──────────────┘  │ - GNU FTP       │
                  └────────┬────────┘
                           │
                           v
                  ┌────────────────────┐
                  │ HTTP Layer         │
                  │ - Retries (2x)     │
                  │ - Backoff          │
                  │ - Accept headers   │
                  │ - Timeout (3s)     │
                  └────────┬───────────┘
                           │
                           v
                  ┌────────────────────┐
                  │ Cache Layer        │
                  │ ├─ Hints           │
                  │ ├─ Manual          │
                  │ └─ Snapshot        │
                  └────────────────────┘
```

## Component Details

### 1. CLI Entry Point & Mode Router

**Location:** `audit.py::main()`

The entry point determines operating mode based on environment variables:

```python
COLLECT_ONLY = os.environ.get("CLI_AUDIT_COLLECT", "0") == "1"
RENDER_ONLY = os.environ.get("CLI_AUDIT_RENDER", "0") == "1"
```

**Modes:**
- **COLLECT_ONLY:** Fetches data, writes snapshot, no output
- **RENDER_ONLY:** Reads snapshot, renders output, no network
- **NORMAL:** Full audit with collection and rendering

### 2. Data Collection Pipeline

**Architecture:** ThreadPoolExecutor-based parallelism

```python
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(audit_tool, tool): tool for tool in TOOLS}
    for future in as_completed(futures):
        result = future.result()  # (state, tool, installed, ...)
```

**Key Features:**
- Configurable concurrency (default: 16 workers, via `CLI_AUDIT_MAX_WORKERS`)
- Independent tool audits (one failure doesn't block others)
- Timeout per tool (3s default, via `CLI_AUDIT_TIMEOUT_SECONDS`)
- Results aggregation for snapshot writing

### 3. Version Discovery Layer

**Local Discovery Flow:**

```
find_paths(candidates)
  → ["/usr/bin/rg", "/home/user/.cargo/bin/rg"]
  → get_version_line(path, tool_name)
  → extract_version_number(line)
  → classify_install_method(path)
  → choose_highest(installed_list)
```

**Installation Classification:**

The system identifies how tools were installed by inspecting paths:

```python
def _classify_install_method(path: str, tool_name: str) -> tuple[str, str]:
    # Check for version managers
    if "/.cargo/bin/" in path: return "rustup/cargo"
    if "/.local/bin/" in path:
        # Read shebang to distinguish pipx, uv, manual
        ...
    if "/node_modules/.bin/" in path: return "npm (project)"
    # ... 20+ more classification rules
```

**Supported Classifications:**
- Version managers: uv, pipx, nvm, asdf, pyenv, rbenv, volta
- System packages: apt/dpkg, snap, homebrew
- User installs: ~/.local/bin, npm (user/global), cargo
- Project-local: npm (project), venv

### 4. Upstream APIs Layer

**Supported Sources:**

| Source | Function | Example |
|--------|----------|---------|
| GitHub | `latest_github(owner, repo)` | `("BurntSushi", "ripgrep")` |
| PyPI | `latest_pypi(package)` | `("black",)` |
| crates.io | `latest_crates(crate)` | `("ripgrep",)` |
| npm | `latest_npm(package)` | `("eslint",)` |
| GNU FTP | `latest_gnu(project)` | `("parallel",)` |

**API Resolution Strategies:**

1. **GitHub:**
   - Try `/repos/{owner}/{repo}/releases/latest` with redirect following
   - Fallback to Atom feed parsing if API fails

2. **PyPI:**
   - Query `https://pypi.org/pypi/{package}/json`
   - Extract `info.version`

3. **crates.io:**
   - Query `https://crates.io/api/v1/crates/{crate}`
   - Extract `crate.max_version`

4. **npm:**
   - Query `https://registry.npmjs.org/{package}`
   - Extract `dist-tags.latest`

### 5. HTTP Layer

**Function:** `http_fetch(url, headers, retries, timeout)`

**Features:**
- **Retries:** 2 retries with exponential backoff (200ms base + jitter)
- **Accept Headers:** Per-host negotiation (e.g., `application/vnd.github+json` for GitHub)
- **Timeout:** 3s per request (configurable)
- **User-Agent:** Identifies as `cli-audit/1.0`
- **Error Handling:** Returns empty bytes on all failures (graceful degradation)

**Backoff Formula:**
```python
sleep_time = base * (2 ** attempt) + random.uniform(0, jitter)
# Example: attempt 1 → 200ms + 0-100ms = 200-300ms
```

### 6. Data Files

**Two-file model:**

1. **Upstream Cache** (`upstream_versions.json`) - Committed
   - Latest available versions from upstream sources
   - Used in offline mode (`CLI_AUDIT_OFFLINE=1`)
   - Updated via `--update-baseline`

2. **Local State** (`local_state.json`) - Gitignored
   - Machine-specific installed tool versions
   - Updated via `--update-local`

### 7. Threading Model & Synchronization

**Concurrency Strategy:**

```python
# ThreadPoolExecutor for parallel tool audits
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Each worker calls audit_tool(tool)
```

**Thread Safety:**
- Tool audits run in parallel (no shared state)
- Atomic file writes prevent corruption (write to temp, then rename)

**Performance Considerations:**
- 16 workers × 3s timeout = max 3s total for 16 tools
- For 50 tools: ~10s best case (3-4 batches)
- Network failures isolated per tool (don't block others)

## Data Flow Diagrams

### Collection Mode (COLLECT_ONLY)

```
User: CLI_AUDIT_COLLECT=1 uv run python audit.py
  ↓
main() detects COLLECT_ONLY mode
  ↓
Load TOOLS registry (50+ tools)
  ↓
ThreadPoolExecutor spawns workers (×16)
  ↓
For each tool in parallel:
  ├─ find_paths() → discover executables
  ├─ get_version_line() → extract version
  ├─ detect_install_method() → classify source
  ├─ get_latest() → fetch upstream (cache-first)
  └─ Compare versions → determine status
  ↓
Aggregate results
  ↓
write_snapshot(results) → tools_snapshot.json
  ↓
Exit (no output rendering)
```

### Render Mode (RENDER_ONLY)

```
User: CLI_AUDIT_RENDER=1 uv run python audit.py
  ↓
main() detects RENDER_ONLY mode
  ↓
load_snapshot() → read tools_snapshot.json
  ↓
render_from_snapshot(doc) → extract tool records
  ↓
Apply filters (positional tool names)
  ↓
Sort (by order or alpha)
  ↓
Format output:
  ├─ Table mode → pipe-delimited rows
  └─ JSON mode → array of objects
  ↓
Output to stdout (no network, fast)
```

### Normal Mode (Full Audit)

```
User: uv run python audit.py
  ↓
main() detects NORMAL mode
  ↓
[Execute Collection Pipeline]
  ↓
[Execute Render Pipeline]
  ↓
Output to stdout
```

## Resilience Patterns

### 1. Timeout Enforcement

**Problem:** Network calls or subprocess execution may hang

**Solution:**
```python
TIMEOUT_SECONDS = 3  # Global timeout

def run_with_timeout(args):
    proc = subprocess.Popen(...)
    try:
        stdout, _ = proc.communicate(timeout=TIMEOUT_SECONDS)
        return stdout.decode("utf-8", errors="ignore")
    except subprocess.TimeoutExpired:
        proc.kill()
        return ""  # Graceful failure
```

### 2. Retry with Exponential Backoff

**Problem:** Transient network failures should be retried

**Solution:**
```python
for attempt in range(retries + 1):
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
        return response.read()
    except Exception:
        if attempt < retries:
            sleep_time = base * (2 ** attempt) + random.uniform(0, jitter)
            time.sleep(sleep_time)
        else:
            return b""  # Final failure → empty bytes
```

### 3. Fallback Cache Hierarchy

**Problem:** Upstream APIs may be unreachable or rate-limited

**Solution:**
```
Attempt 1: Try upstream API (with retries)
  ↓ (on failure)
Attempt 2: Use cached upstream (upstream_versions.json)
  ↓ (on failure)
Result: Mark as UNKNOWN, continue audit
```

### 4. Atomic File Writes

**Problem:** Concurrent writes or crashes may corrupt cache files

**Solution:**
```python
def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)  # Atomic on POSIX
```

### 5. Independent Failure Isolation

**Problem:** One tool failure shouldn't block others

**Solution:**
- Each tool audit is independent (no shared state except caches)
- Exceptions caught per tool, logged, marked as UNKNOWN
- Parallel execution ensures one slow tool doesn't block 49 others

## Performance Characteristics

### Benchmarks (Typical System)

| Scenario | Time | Notes |
|----------|------|-------|
| Collection (online, 50 tools) | ~10s | 3-4 batches of 16 workers |
| Collection (offline, cache hit) | ~3s | No network, instant cache reads |
| Render (from snapshot) | <100ms | Pure JSON read + format |
| Single tool audit | ~300ms | Version check + upstream fetch |

### Optimization Strategies

1. **Hints System:** Skip failed API methods, try successful ones first
2. **Parallel Execution:** 16 concurrent workers reduce wall time
3. **Snapshot Separation:** Render without network in subsequent runs
4. **Timeout Tuning:** 3s per tool balances speed vs. completeness
5. **Cache Persistence:** Committed cache works offline immediately

### Bottlenecks

- **GitHub API:** Rate limiting (60 req/hour unauthenticated)
  - Mitigation: Hints cache, manual cache, `GITHUB_TOKEN` support
- **Subprocess Execution:** 50+ version checks add up
  - Mitigation: Parallel execution, PATH caching
- **Network Latency:** Upstream APIs may be slow
  - Mitigation: Timeouts, retries, offline mode

## Extension Points

### Adding New Tool Sources

To support a new upstream source (e.g., Homebrew API):

1. Implement `latest_homebrew(formula)` function
2. Add `"homebrew"` to `source_kind` options
3. Update `get_latest()` dispatcher:
   ```python
   elif tool.source_kind == "homebrew":
       return latest_homebrew(tool.source_args[0])
   ```

### Custom Classification Rules

To add new installation method detection:

1. Update `_classify_install_method()`:
   ```python
   if "/my-package-manager/" in path:
       return "my-pkg-mgr"
   ```

2. Document in TOOL_ECOSYSTEM.md

### Alternative Output Formats

Current: Table (piped) and JSON

To add YAML output:
1. Add `CLI_AUDIT_YAML` environment variable
2. Implement YAML serialization in render pipeline
3. Update DEPLOYMENT.md

---

## Phase 2: Installation & Upgrade Management Architecture

**Status:** ✅ Implementation Complete | 📝 Documentation Complete

### Phase 2 Overview

Phase 2 extends Phase 1's audit capabilities with automated installation, upgrade management, and reconciliation. The architecture emphasizes context-aware decisions, safe operations with rollback, and parallel execution.

**Design Principles:**
1. **Context-Aware:** Environment detection (CI/server/workstation) influences installation strategies
2. **Safe Operations:** Backup and automatic rollback on failures
3. **Parallel Execution:** Bulk operations use ThreadPoolExecutor for speed
4. **Retryable Errors:** Network and lock contention errors retry with exponential backoff
5. **Flexible Configuration:** Multi-source configuration with precedence rules

### Phase 2 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Configuration Layer                                     │
│ ├─ Project (.cli-audit.yml)                            │
│ ├─ User (~/.config/cli-audit/config.yml)               │
│ └─ System (/etc/cli-audit/config.yml)                  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        v
┌─────────────────────────────────────────────────────────┐
│ Environment Detection                                   │
│ - CI detection (CI=true, GITHUB_ACTIONS, etc.)         │
│ - Server detection (multiple users, high uptime)       │
│ - Workstation detection (DISPLAY, single user)         │
│ - Confidence scoring (0.0-1.0)                         │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        v                               v
┌───────────────────┐      ┌────────────────────────┐
│ Install Pipeline  │      │ Upgrade Pipeline       │
│ - Tool selection  │      │ - Version comparison   │
│ - PM selection    │      │ - Breaking detection   │
│ - Dependency res  │      │ - Backup creation      │
│ - Parallel exec   │      │ - Auto rollback        │
│ - Validation      │      │ - Cache management     │
└─────────┬─────────┘      └────────┬───────────────┘
          │                         │
          v                         v
┌─────────────────────────────────────────────────────────┐
│ Package Manager Selection (Hierarchical)                │
│ Python: [uv, pipx, pip]                                 │
│ Rust:   [cargo]                                         │
│ Node:   [npm, pnpm, yarn]                               │
│ System: [apt, dnf, pacman, brew]                        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        v
┌─────────────────────────────────────────────────────────┐
│ Installation Execution                                  │
│ - Command generation                                    │
│ - Subprocess execution                                  │
│ - Retry logic (network, lock)                          │
│ - Timeout enforcement (5-60s)                          │
│ - Progress tracking                                     │
└───────────────────────┬─────────────────────────────────┘
                        │
                        v
┌─────────────────────────────────────────────────────────┐
│ Post-Install Validation                                 │
│ - Binary availability in PATH                           │
│ - Version verification                                  │
│ - Checksum validation (optional)                        │
└─────────────────────────────────────────────────────────┘
```

### Component Details: Phase 2

#### 1. Environment Detection

**Location:** `cli_audit/environment.py`

Detects runtime environment to influence installation decisions:

```python
@dataclass(frozen=True)
class Environment:
    mode: str          # "ci", "server", or "workstation"
    confidence: float  # 0.0-1.0
    indicators: tuple[str, ...]
    override: bool = False

def detect_environment(override: str | None = None) -> Environment:
    # CI detection
    if os.environ.get("CI") == "true": return Environment("ci", 0.95, ("CI=true",))
    if "GITHUB_ACTIONS" in os.environ: return Environment("ci", 0.99, ("GITHUB_ACTIONS",))

    # Server detection (multiple active users, high uptime)
    if users > 3: return Environment("server", 0.85, ("multiple_users",))

    # Workstation detection
    if "DISPLAY" in os.environ: return Environment("workstation", 0.90, ("DISPLAY",))
```

**Environment Impact:**
- **CI:** Non-interactive, fail-fast, no confirmation prompts
- **Server:** Conservative updates, system package managers preferred
- **Workstation:** User package managers, interactive confirmations

#### 2. Configuration Management

**Location:** `cli_audit/config.py`

Multi-source configuration with precedence rules:

```python
@dataclass(frozen=True)
class Config:
    version: int = 1
    environment_mode: str = "auto"
    tools: dict[str, ToolConfig] = field(default_factory=dict)
    preferences: Preferences = field(default_factory=Preferences)
    presets: dict[str, list[str]] = field(default_factory=dict)
    source: str = ""

@dataclass(frozen=True)
class Preferences:
    reconciliation: str = "parallel"       # "parallel" or "aggressive"
    breaking_changes: str = "warn"         # "accept", "warn", or "reject"
    auto_upgrade: bool = True
    timeout_seconds: int = 5               # 1-60
    max_workers: int = 16                  # 1-32
    cache_ttl_seconds: int = 3600          # 60-86400
    package_managers: dict[str, list[str]] = field(default_factory=dict)
```

**Configuration Precedence:**
1. Project (`.cli-audit.yml`)
2. User (`~/.config/cli-audit/config.yml`)
3. System (`/etc/cli-audit/config.yml`)

#### 3. Installation Pipeline

**Location:** `cli_audit/installer.py`

Single tool installation with retry logic:

```python
def install_tool(
    tool_name: str,
    package_name: str,
    target_version: str = "latest",
    config: Config | None = None,
    env: Environment | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> InstallResult:
    # 1. Select package manager
    pm_name, reason = select_package_manager(tool_name, language, config, env)

    # 2. Generate install command
    install_cmd = generate_install_command(pm_name, package_name, target_version)

    # 3. Execute with retry
    try:
        result = subprocess.run(install_cmd, timeout=timeout, capture_output=True)
        if result.returncode != 0:
            if is_retryable_error(result.returncode, result.stderr):
                # Auto-retry with exponential backoff
                ...
    except subprocess.TimeoutExpired:
        raise InstallError("Command timed out", retryable=False)

    # 4. Validate installation
    success, binary_path, version = validate_installation(tool_name)

    return InstallResult(...)
```

**Retryable Error Detection:**

```python
def is_retryable_error(exit_code: int, stderr: str) -> bool:
    # Network errors
    network_indicators = [
        "connection refused", "connection timed out",
        "connection reset", "network unreachable",
        "could not resolve host", "temporary failure"
    ]

    # Lock contention
    lock_indicators = [
        "could not get lock", "lock file exists",
        "waiting for cache lock", "dpkg frontend lock"
    ]

    # Exit codes
    if exit_code in (75, 111, 128):  # EAGAIN, conn refused, git error
        return True

    return any(ind in stderr.lower() for ind in network_indicators + lock_indicators)
```

#### 4. Bulk Operations

**Location:** `cli_audit/bulk.py`

Parallel installation with dependency resolution:

```python
def bulk_install(
    mode: str = "explicit",
    tool_names: Sequence[str] | None = None,
    max_workers: int | None = None,
    fail_fast: bool = False,
    atomic: bool = False,
    progress_tracker: ProgressTracker | None = None,
) -> BulkInstallResult:
    # 1. Determine tools to install
    specs = get_tools_to_install(mode, tool_names, preset_name, config)

    # 2. Resolve dependencies (topological sort)
    levels = resolve_dependencies(specs)

    # 3. Execute level by level
    for level_specs in levels:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_install_with_progress, spec, config, env, tracker): spec
                for spec in level_specs
            }

            for future in as_completed(futures):
                result = future.result()
                if result.success:
                    successes.append(result)
                else:
                    failures.append(result)
                    if fail_fast:
                        break

    # 4. Generate rollback script
    if successes:
        rollback_script = generate_rollback_script(successes)

    # 5. Handle atomic rollback
    if atomic and failures:
        execute_rollback(rollback_script)

    return BulkInstallResult(...)
```

**Dependency Resolution:**

```python
def resolve_dependencies(specs: Sequence[ToolSpec]) -> list[list[ToolSpec]]:
    # Topological sort by levels
    levels = []
    in_degree = {spec.tool_name: 0 for spec in specs}

    for spec in specs:
        for dep in spec.dependencies:
            if dep in spec_map:
                in_degree[spec.tool_name] += 1

    # Find tools with no dependencies
    while remaining:
        ready = [tool for tool in remaining if in_degree[tool] == 0]
        levels.append([spec_map[tool] for tool in ready])
        # Update in-degrees...

    return levels
```

#### 5. Upgrade Management

**Location:** `cli_audit/upgrade.py`

Safe upgrades with backup and rollback:

```python
def upgrade_tool(
    tool_name: str,
    target_version: str = "latest",
    force: bool = False,
    skip_backup: bool = False,
) -> UpgradeResult:
    # 1. Validate tool is installed
    success, binary_path, current_version = validate_installation(tool_name)

    # 2. Determine target version
    if target_version == "latest":
        target_version = get_available_version(tool_name, pm_name, cache_ttl)

    # 3. Check breaking change policy
    is_breaking = is_major_upgrade(current_version, target_version)
    if is_breaking:
        allowed, reason = check_breaking_change_policy(config, current, target)
        if not allowed and not force:
            return UpgradeResult(..., error_message="Breaking change blocked")

        if reason == "breaking_warning" and not force:
            if not confirm_breaking_change(warning):
                return UpgradeResult(..., error_message="User declined")

    # 4. Create backup
    if not skip_backup:
        backup = create_upgrade_backup(tool_name, binary_path, current_version, pm_name)

    # 5. Execute upgrade
    try:
        install_result = install_tool(tool_name, tool_name, target_version, config, env)
        if install_result.success:
            return UpgradeResult(..., success=True)
        else:
            # Auto-rollback on failure
            if backup:
                rollback_success = restore_from_backup(backup)
            return UpgradeResult(..., rollback_executed=True, rollback_success=...)
    except Exception as e:
        if backup:
            restore_from_backup(backup)
        raise
```

**Breaking Change Detection:**

```python
def is_major_upgrade(current: str, target: str) -> bool:
    from packaging import version
    current_ver = version.parse(current)
    target_ver = version.parse(target)
    return target_ver.major > current_ver.major
```

#### 6. Reconciliation Strategies

**Location:** `cli_audit/reconcile.py`

Manages multiple installations of the same tool:

```python
def reconcile_tool(
    tool_name: str,
    mode: str = "parallel",  # "parallel" or "aggressive"
    config: Config | None = None,
) -> ReconciliationResult:
    # 1. Detect all installations
    installations = detect_installations(tool_name)

    # 2. Determine preferred installation
    preferred = select_preferred_installation(installations, config)

    # 3. Apply reconciliation strategy
    if mode == "aggressive":
        # Remove non-preferred installations
        removed = []
        for install in installations:
            if install != preferred and tool_name not in SYSTEM_TOOL_SAFELIST:
                if remove_installation(install):
                    removed.append(install)
        return ReconciliationResult(..., installations_removed=removed)
    else:
        # Keep all installations
        return ReconciliationResult(..., installations_removed=[])
```

**System Tool Safelist:**
- Protected tools: python, python3, pip, node, npm, cargo, git, etc.
- Never removed during aggressive reconciliation

#### 7. Package Manager Selection

**Location:** `cli_audit/package_managers.py`

Hierarchical selection with environment awareness:

```python
def select_package_manager(
    tool_name: str,
    language: str | None,
    config: Config,
    env: Environment,
) -> tuple[str, str]:
    # 1. Get hierarchy from config
    if language:
        hierarchy = config.preferences.package_managers.get(language, [])
    else:
        hierarchy = infer_hierarchy_from_tool(tool_name)

    # 2. Filter by availability
    available = []
    for pm in hierarchy:
        if is_package_manager_available(pm):
            available.append(pm)

    # 3. Environment-aware selection
    if env.mode == "ci":
        # Prefer fast, user-level PMs (uv, pipx, cargo)
        ...
    elif env.mode == "server":
        # Prefer system PMs (apt, dnf, brew)
        ...

    # 4. Return first available
    if available:
        return (available[0], f"First available from {hierarchy}")
    else:
        raise ValueError(f"No suitable package manager for {tool_name}")
```

### Phase 2 Data Flow Diagrams

#### Installation Flow

```
User: bulk_install(mode="missing")
  ↓
Load Config + Detect Environment
  ↓
Determine tools to install
  ↓
Resolve dependencies (topological sort)
  ↓
For each level (parallel within level):
  ├─ Select package manager
  ├─ Generate install command
  ├─ Execute with retry (network, lock)
  ├─ Validate installation (PATH, version)
  └─ Update progress tracker
  ↓
Generate rollback script
  ↓
Return BulkInstallResult
```

#### Upgrade Flow

```
User: upgrade_tool("ruff", "latest")
  ↓
Validate tool is installed
  ↓
Query available version (with cache, TTL=1h)
  ↓
Compare versions (current vs target)
  ↓
Check breaking change policy
  ├─ If major: warn/block based on config
  └─ If minor/patch: proceed
  ↓
Create backup (binary + configs)
  ↓
Execute upgrade via install_tool()
  ↓
Success? → Return UpgradeResult
Failure? → Auto-rollback from backup
```

### Phase 2 Resilience Patterns

#### 1. Retry with Exponential Backoff

**Problem:** Network failures and lock contention are transient

**Solution:**
```python
max_retries = 3
base_delay = 0.5

for attempt in range(max_retries + 1):
    try:
        result = subprocess.run(cmd, timeout=timeout, check=True)
        return result
    except subprocess.CalledProcessError as e:
        if is_retryable_error(e.returncode, e.stderr) and attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
        else:
            raise InstallError(str(e), retryable=False)
```

#### 2. Backup and Rollback

**Problem:** Upgrades may fail or introduce issues

**Solution:**
- Create backup before upgrade (binary + configs)
- Verify backup integrity (SHA256 checksum)
- Automatic rollback on failure
- Manual rollback script for complex scenarios

#### 3. Atomic Operations

**Problem:** Partial installations leave system in inconsistent state

**Solution:**
```python
# Atomic mode: rollback ALL on ANY failure
result = bulk_install(mode="preset", preset_name="python-dev", atomic=True)

if atomic and result.failures:
    execute_rollback(result.rollback_script)
```

### Phase 2 Performance Characteristics

| Operation | Time (typical) | Notes |
|-----------|---------------|-------|
| Single install | 5-30s | Depends on package size, network |
| Bulk install (10 tools) | 30-60s | Parallel execution (16 workers) |
| Upgrade check | 1-3s | With version cache (TTL=1h) |
| Reconciliation | 2-5s | Detection + selective removal |
| Environment detection | <50ms | Quick heuristics |
| Config loading | <20ms | YAML parsing + validation |

### Phase 2 Extension Points

#### Adding New Package Manager

```python
# 1. Register in package_managers.py
PACKAGE_MANAGERS = {
    "my-pm": {
        "check_cmd": ["my-pm", "--version"],
        "install_cmd": ["my-pm", "install"],
        "languages": ["python", "rust"],
    }
}

# 2. Add to hierarchy
preferences:
  package_managers:
    python: [uv, pipx, my-pm, pip]
```

#### Custom Breaking Change Rules

```python
# Override breaking change policy per tool
tools:
  ruff:
    breaking_changes: reject  # Never allow major upgrades
  pytest:
    breaking_changes: accept  # Always allow
```

---

## See Also

### Phase 1 Documentation
- **[API_REFERENCE.md](API_REFERENCE.md)** - Phase 1 audit functions
- **[FUNCTION_REFERENCE.md](FUNCTION_REFERENCE.md)** - Function reference card
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and debugging

### Phase 2 Documentation
- **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - Complete Phase 2 API documentation
- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-line reference
- **[TESTING.md](TESTING.md)** - Testing guide
- **[ERROR_CATALOG.md](ERROR_CATALOG.md)** - Error reference and troubleshooting
- **[INTEGRATION_EXAMPLES.md](INTEGRATION_EXAMPLES.md)** - Real-world integration patterns
