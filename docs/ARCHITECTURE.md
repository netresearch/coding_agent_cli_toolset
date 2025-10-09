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

**Location:** `cli_audit.py::main()`

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
   - Store successful method in hints for speed

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

### 6. Cache Layer (Multi-Tier)

**Cache Hierarchy (fastest → slowest):**

1. **Hints Cache** (`__hints__` in `latest_versions.json`)
   - Stores which API method worked last per tool
   - Example: `"gh:BurntSushi/ripgrep": "latest_redirect"`
   - Purpose: Skip failed methods, try successful ones first
   - Lock: `HINTS_LOCK` (acquired after `MANUAL_LOCK`)

2. **Manual Cache** (`latest_versions.json`)
   - Committed to repository
   - Used in offline mode (`CLI_AUDIT_OFFLINE=1`)
   - Updated on successful upstream fetches (unless `CLI_AUDIT_WRITE_MANUAL=0`)
   - Lock: `MANUAL_LOCK` (acquired first)

3. **Snapshot** (`tools_snapshot.json`)
   - Complete audit results with metadata
   - Schema version 1 with `__meta__` object
   - Used for render-only mode
   - Written atomically after collection

**Lock Ordering Rule:**
```python
with MANUAL_LOCK:
    # Update latest_versions.json
    with HINTS_LOCK:
        # Update __hints__ section
```
**Critical:** MANUAL_LOCK must be acquired before HINTS_LOCK to prevent deadlock.

### 7. Threading Model & Synchronization

**Concurrency Strategy:**

```python
# Global locks for cache writes
MANUAL_LOCK = threading.Lock()  # For latest_versions.json
HINTS_LOCK = threading.Lock()   # For __hints__ in latest_versions.json (nested)

# ThreadPoolExecutor for parallel tool audits
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    # Each worker calls audit_tool(tool)
    # Workers may update caches (with locks)
```

**Thread Safety:**
- Tool audits run in parallel (no shared state except caches)
- Cache updates are serialized via locks
- Atomic file writes prevent corruption (write to temp, then rename)

**Performance Considerations:**
- 16 workers × 3s timeout = max 3s total for 16 tools
- For 50 tools: ~10s best case (3-4 batches)
- Network failures isolated per tool (don't block others)

## Data Flow Diagrams

### Collection Mode (COLLECT_ONLY)

```
User: CLI_AUDIT_COLLECT=1 python3 cli_audit.py
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
User: CLI_AUDIT_RENDER=1 python3 cli_audit.py
  ↓
main() detects RENDER_ONLY mode
  ↓
load_snapshot() → read tools_snapshot.json
  ↓
render_from_snapshot(doc) → extract tool records
  ↓
Apply filters (--only flag)
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
User: python3 cli_audit.py
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
Attempt 2: Check hints cache for alternative method
  ↓ (on failure)
Attempt 3: Use manual cache (latest_versions.json)
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

## See Also

- **[API_REFERENCE.md](API_REFERENCE.md)** - Function signatures and parameters
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - How to contribute
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and debugging
