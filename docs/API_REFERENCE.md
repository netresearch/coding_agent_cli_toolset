# API Reference

## Data Structures

### Tool Dataclass

**Location:** `cli_audit.py:729`

```python
@dataclass(frozen=True)
class Tool:
    name: str                    # Logical tool name (e.g., "python", "ripgrep")
    candidates: tuple[str, ...]  # Executable names to search on PATH
    source_kind: str            # "gh" | "pypi" | "crates" | "npm" | "gnu" | "skip"
    source_args: tuple[str, ...] # Parameters for upstream source
```

**Fields:**

- **name** (`str`): Display name for the tool
  - Used in output rendering
  - Should match common usage (e.g., "ripgrep" not "rg")

- **candidates** (`tuple[str, ...]`): Executable names to search
  - Searched in order on PATH
  - Handles distribution naming differences (e.g., `("fd", "fdfind")`)
  - First match wins unless multiple versions found

- **source_kind** (`str`): Upstream source type
  - `"gh"` - GitHub releases
  - `"pypi"` - Python Package Index
  - `"crates"` - crates.io (Rust)
  - `"npm"` - npm registry
  - `"gnu"` - GNU FTP server
  - `"skip"` - No upstream lookup (manual-only)

- **source_args** (`tuple[str, ...]`): Source-specific parameters
  - GitHub: `(owner, repo)` - e.g., `("sharkdp", "fd")`
  - PyPI: `(package,)` - e.g., `("black",)`
  - crates: `(crate,)` - e.g., `("ripgrep",)`
  - npm: `(package,)` - e.g., `("eslint",)`
  - GNU: `(project,)` - e.g., `("parallel",)`
  - skip: `()` - empty tuple

**Examples:**

```python
# GitHub tool with single candidate
Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))

# Tool with multiple candidates (distro naming)
Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd"))
Tool("bat", ("bat", "batcat"), "gh", ("sharkdp", "bat"))

# PyPI package
Tool("black", ("black",), "pypi", ("black",))

# npm package
Tool("eslint", ("eslint",), "npm", ("eslint",))

# Tool without upstream lookup
Tool("sponge", ("sponge",), "skip", ())
```

### TOOLS Registry

**Location:** `cli_audit.py:738`

```python
TOOLS: tuple[Tool, ...] = (
    # Ordered list of 50+ tools
    Tool("go", ...),
    Tool("python", ...),
    # ... more tools
)
```

**Organization:**
1. Language runtimes (go, python, rust, node)
2. Package managers (pip, pipx, poetry, npm, pnpm, yarn, uv)
3. Core developer tools (fd, fzf, ctags, ripgrep, jq, etc.)
4. Security tools (trivy, gitleaks, semgrep, bandit)
5. Formatters & linters (black, eslint, prettier, shellcheck)
6. Git tools (git, gh, glab, git-absorb, git-branchless)
7. Cloud/infra tools (aws, kubectl, terraform, docker)

**Access:**
```python
for tool in TOOLS:
    print(f"{tool.name}: {tool.candidates}")
```

## Core Functions

### Snapshot Management

#### `load_snapshot(paths=None) -> dict[str, Any]`

Load snapshot from file.

**Parameters:**
- `paths` (`Sequence[str] | None`): Custom paths to try (default: `[SNAPSHOT_FILE, "latest_versions.json"]`)

**Returns:** Dictionary with keys:
- `"__meta__"`: Metadata object (schema version, timestamp, count)
- `"tools"`: List of tool audit results

**Example:**
```python
doc = load_snapshot()
meta = doc["__meta__"]
tools = doc["tools"]
print(f"Snapshot created at {meta['created_at']} with {meta['count']} tools")
```

#### `write_snapshot(tools_payload, extra=None) -> dict[str, Any]`

Write audit results to snapshot file atomically.

**Parameters:**
- `tools_payload` (`list[dict]`): Tool audit results
- `extra` (`dict | None`): Additional metadata to include

**Returns:** Metadata object that was written

**Side Effects:** Writes `tools_snapshot.json` (or `CLI_AUDIT_SNAPSHOT_FILE`)

**Example:**
```python
results = [audit_tool(tool) for tool in TOOLS]
meta = write_snapshot(results, extra={"partial": True})
```

#### `render_from_snapshot(doc, selected=None) -> list[tuple]`

Extract and filter tools from snapshot for rendering.

**Parameters:**
- `doc` (`dict`): Snapshot document from `load_snapshot()`
- `selected` (`set[str] | None`): Tool names to include (lowercase)

**Returns:** List of tuples:
```python
(name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url)
```

**Example:**
```python
doc = load_snapshot()
selected = {"python", "ripgrep", "jq"}
rows = render_from_snapshot(doc, selected)
for row in rows:
    print(row)
```

### Version Discovery

#### `find_paths(command_name, deep=False) -> list[str]`

Find all paths for a command.

**Parameters:**
- `command_name` (`str`): Executable name to search
- `deep` (`bool`): If `True`, also checks `~/.cargo/bin` for Rust tools

**Returns:** List of absolute paths (duplicates removed)

**Example:**
```python
paths = find_paths("rg", deep=True)
# ["/usr/bin/rg", "/home/user/.cargo/bin/rg"]
```

#### `get_version_line(path, tool_name) -> str`

Extract version string from executable.

**Parameters:**
- `path` (`str`): Absolute path to executable
- `tool_name` (`str`): Tool name for special handling

**Returns:** First line of version output, or empty string on failure

**Special Cases:**
- Most tools: `<path> --version`
- `go`, `curlie`, `isort`: Custom version flags
- `entr`, `sponge`: No version flag (returns empty)

**Example:**
```python
line = get_version_line("/usr/bin/rg", "ripgrep")
# "ripgrep 14.1.1"
```

#### `extract_version_number(s) -> str`

Parse semantic version from string.

**Parameters:**
- `s` (`str`): Raw version string

**Returns:** Cleaned version number (e.g., "14.1.1")

**Patterns Handled:**
- Semantic: `v14.1.1`, `14.1.1`, `1.2.3-beta`
- Prefixed: `jq-1.8.1`, `go1.25.1`
- Date-based: `20250822`

**Example:**
```python
extract_version_number("ripgrep 14.1.1 (rev abc123)")
# "14.1.1"

extract_version_number("jq-1.8.1")
# "1.8.1"
```

#### `choose_highest(installed) -> tuple[str, str, str] | tuple[()]`

Select highest version from multiple installations.

**Parameters:**
- `installed` (`list[tuple[str, str, str]]`): List of `(version, path, method)` tuples

**Returns:** Best version tuple, or empty tuple if none

**Logic:**
1. Parse each version as semantic version
2. Select highest by major.minor.patch comparison
3. Tiebreak by path (prefer user installs over system)

**Example:**
```python
installed = [
    ("14.1.0", "/usr/bin/rg", "apt/dpkg"),
    ("14.1.1", "/home/user/.cargo/bin/rg", "rustup/cargo")
]
best = choose_highest(installed)
# ("14.1.1", "/home/user/.cargo/bin/rg", "rustup/cargo")
```

### Installation Classification

#### `detect_install_method(path, tool_name) -> str`

Classify how a tool was installed.

**Parameters:**
- `path` (`str`): Absolute path to executable
- `tool_name` (`str`): Tool name for context

**Returns:** Human-readable method string

**Classifications:**
- **Version managers:** `"uv tool"`, `"pipx/user"`, `"nvm/npm"`, `"asdf"`, `"pyenv"`, `"rbenv"`, `"volta"`, `"sdkman"`, `"rustup/cargo"`
- **System packages:** `"apt/dpkg"`, `"snap"`, `"homebrew"`, `"/usr/local/bin"`
- **User installs:** `"~/.local/bin"`, `"npm (user)"`, `"npm (global)"`, `"npm (project)"`
- **Project-local:** `"venv"`, `"npm (project)"`

**Example:**
```python
method = detect_install_method("/home/user/.local/bin/rg", "ripgrep")
# Checks shebang, environment, path patterns
# Returns: "rustup/cargo" or "~/.local/bin" depending on analysis
```

### Upstream APIs

#### `latest_github(owner, repo) -> tuple[str, str]`

Fetch latest GitHub release.

**Parameters:**
- `owner` (`str`): GitHub username/org
- `repo` (`str`): Repository name

**Returns:** `(version_tag, method)` where method is:
- `"latest_redirect"` - Used `/releases/latest` with redirect
- `"atom"` - Parsed Atom feed

**Strategies:**
1. Try `/repos/{owner}/{repo}/releases/latest` with redirect following
2. On failure, try Atom feed at `/releases.atom`
3. Use hints cache to skip failed methods

**Example:**
```python
tag, method = latest_github("sharkdp", "fd")
# ("v10.3.0", "latest_redirect")

# Stores hint for next run:
set_hint(f"gh:{owner}/{repo}", method)
```

#### `latest_pypi(package) -> tuple[str, str]`

Fetch latest PyPI version.

**Parameters:**
- `package` (`str`): PyPI package name

**Returns:** `(version, "pypi")`

**API:** `https://pypi.org/pypi/{package}/json`

**Example:**
```python
version, method = latest_pypi("black")
# ("25.1.0", "pypi")
```

#### `latest_crates(crate) -> tuple[str, str]`

Fetch latest crates.io version.

**Parameters:**
- `crate` (`str`): Crate name

**Returns:** `(version, "crates")`

**API:** `https://crates.io/api/v1/crates/{crate}`

**Example:**
```python
version, method = latest_crates("ripgrep")
# ("14.1.1", "crates")
```

#### `latest_npm(package) -> tuple[str, str]`

Fetch latest npm version.

**Parameters:**
- `package` (`str`): npm package name

**Returns:** `(version, "npm")`

**API:** `https://registry.npmjs.org/{package}`

**Example:**
```python
version, method = latest_npm("eslint")
# ("9.35.0", "npm")
```

#### `latest_gnu(project) -> tuple[str, str]`

Fetch latest GNU project version via FTP.

**Parameters:**
- `project` (`str`): GNU project name

**Returns:** `(version, "gnu-ftp")`

**API:** `https://ftp.gnu.org/gnu/{project}/`

**Example:**
```python
version, method = latest_gnu("parallel")
# ("20250822", "gnu-ftp")
```

### HTTP Layer

#### `http_fetch(url, headers=None, retries=2, timeout=3) -> bytes`

Fetch URL with retries and backoff.

**Parameters:**
- `url` (`str`): Target URL
- `headers` (`dict | None`): HTTP headers (default: User-Agent only)
- `retries` (`int`): Retry attempts (default: 2, configurable via `CLI_AUDIT_HTTP_RETRIES`)
- `timeout` (`int`): Timeout per attempt in seconds (default: 3)

**Returns:** Response body as bytes, or empty bytes on all failures

**Features:**
- Exponential backoff: `base * 2^attempt + jitter`
- Per-host Accept header negotiation
- Graceful failure (returns empty bytes, never raises)

**Example:**
```python
data = http_fetch("https://api.github.com/repos/owner/repo", headers={"Accept": "application/json"})
if data:
    response = json.loads(data)
```

### Cache Management

#### `load_manual_versions() -> None`

Load manual cache from `latest_versions.json`.

**Side Effects:** Populates global `MANUAL_VERSIONS` dict

**Called:** Automatically at module import

#### `get_manual_latest(tool_name) -> tuple[str, str]`

Get cached version for a tool.

**Parameters:**
- `tool_name` (`str`): Tool name (lowercase)

**Returns:** `(version, "manual")` or `("", "")` if not cached

**Example:**
```python
version, method = get_manual_latest("ripgrep")
if version:
    print(f"Cached version: {version}")
```

#### `set_manual_latest(tool_name, version) -> None`

Update manual cache with new version.

**Parameters:**
- `tool_name` (`str`): Tool name
- `version` (`str`): Version string

**Side Effects:** Writes to `latest_versions.json` (requires `MANUAL_LOCK`)

**Example:**
```python
set_manual_latest("ripgrep", "14.1.1")
```

#### `load_hints() -> None`

Load API method hints from `__hints__` in `latest_versions.json`.

**Side Effects:** Populates global `HINTS` dict

#### `get_hint(key) -> str`

Get cached API method for a source.

**Parameters:**
- `key` (`str`): Hint key (e.g., `"gh:owner/repo"`, `"local_flag:tool"`)

**Returns:** Method string (e.g., `"latest_redirect"`, `"--version"`) or empty

**Example:**
```python
method = get_hint("gh:sharkdp/fd")
if method == "latest_redirect":
    # Try latest redirect first
```

#### `set_hint(key, value) -> None`

Store API method hint for future runs.

**Parameters:**
- `key` (`str`): Hint key
- `value` (`str`): Method that worked

**Side Effects:** Writes to `__hints__` in `latest_versions.json` (requires `HINTS_LOCK` nested in `MANUAL_LOCK`)

### Core Audit Functions

#### `audit_tool(tool) -> tuple[str, str, str, str, str, str, str, str]`

Perform complete audit for one tool.

**Parameters:**
- `tool` (`Tool`): Tool definition

**Returns:** Tuple of 8 strings:
```python
(
    name,              # Tool name
    installed,         # Installed version (with timing)
    installed_method,  # Classification (e.g., "uv tool")
    latest_upstream,   # Latest version (with timing)
    upstream_method,   # Source (e.g., "github")
    status,            # "UP-TO-DATE", "OUTDATED", "NOT INSTALLED", "UNKNOWN"
    tool_url,          # Homepage URL (if ENABLE_LINKS)
    latest_url         # Latest release URL (if ENABLE_LINKS)
)
```

**Logic:**
1. Find all installed versions
2. Classify installation methods
3. Fetch latest from upstream (cache-first)
4. Compare versions and determine status
5. Generate URLs if enabled

**Example:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
result = audit_tool(tool)
# ("ripgrep", "14.1.1 (150ms)", "rustup/cargo", "14.1.1 (220ms)", "github", "UP-TO-DATE", "...", "...")
```

#### `get_latest(tool) -> tuple[str, str]`

Get latest upstream version for a tool.

**Parameters:**
- `tool` (`Tool`): Tool definition

**Returns:** `(version, method)` - version string and source method

**Cache Strategy:**
1. Check hints cache for fastest method
2. Try upstream API (with retries)
3. On success, update hints and manual caches
4. On failure, fall back to manual cache
5. Final fallback: return `("", "")`

**Example:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
version, method = get_latest(tool)
# ("14.1.1", "github")
```

## Environment Variables

### Mode Control

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_COLLECT` | `0`, `1` | `0` | Collect-only mode (no rendering) |
| `CLI_AUDIT_RENDER` | `0`, `1` | `0` | Render-only mode (no network) |
| `CLI_AUDIT_OFFLINE` | `0`, `1` | `0` | Force offline (use manual cache only) |

### Output Control

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_JSON` | `0`, `1` | `0` | Output JSON instead of table |
| `CLI_AUDIT_LINKS` | `0`, `1` | `1` | Include OSC 8 hyperlinks |
| `CLI_AUDIT_EMOJI` | `0`, `1` | `1` | Use emoji status icons |
| `CLI_AUDIT_TIMINGS` | `0`, `1` | `1` | Show timing info in output |
| `CLI_AUDIT_GROUP` | `0`, `1` | `1` | Group by category |
| `CLI_AUDIT_HINTS` | `0`, `1` | `1` | Show remediation hints |
| `CLI_AUDIT_STREAM` | `0`, `1` | `0` | Stream output row-by-row |

### Performance

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_MAX_WORKERS` | `1-32` | `16` | ThreadPoolExecutor concurrency |
| `CLI_AUDIT_TIMEOUT_SECONDS` | `1-30` | `3` | Timeout per subprocess/HTTP request |
| `CLI_AUDIT_FAST` | `0`, `1` | `0` | Skip slow operations |

### Network

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_HTTP_RETRIES` | `0-5` | `2` | HTTP retry attempts |
| `CLI_AUDIT_BACKOFF_BASE` | float | `0.2` | Exponential backoff base (seconds) |
| `CLI_AUDIT_BACKOFF_JITTER` | float | `0.1` | Random jitter range (seconds) |
| `GITHUB_TOKEN` | string | `""` | GitHub API token (for rate limits) |

### Debugging

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_DEBUG` | `0`, `1` | `0` | Print debug messages to stderr |
| `CLI_AUDIT_TRACE` | `0`, `1` | `0` | Print detailed trace messages |
| `CLI_AUDIT_TRACE_NET` | `0`, `1` | `0` | Trace network calls |
| `CLI_AUDIT_PROGRESS` | `0`, `1` | `0` | Show progress during collection |

### File Paths

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_SNAPSHOT_FILE` | path | `tools_snapshot.json` | Snapshot output file |
| `CLI_AUDIT_MANUAL_FILE` | path | `latest_versions.json` | Manual cache file |

### Cache Behavior

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CLI_AUDIT_WRITE_MANUAL` | `0`, `1` | `1` | Update manual cache on success |
| `CLI_AUDIT_MANUAL_FIRST` | `0`, `1` | `0` | Try manual cache before upstream |

## File Schemas

### tools_snapshot.json

```json
{
  "__meta__": {
    "schema_version": 1,
    "created_at": "2025-10-09T12:34:56Z",
    "offline": false,
    "count": 50,
    "partial_failures": 2
  },
  "tools": [
    {
      "tool": "ripgrep",
      "installed": "14.1.1 (150ms)",
      "installed_version": "14.1.1",
      "installed_method": "rustup/cargo",
      "installed_path_resolved": "/home/user/.cargo/bin/rg",
      "installed_path_selected": "/home/user/.cargo/bin/rg",
      "classification_reason": "path-under-~/.cargo/bin",
      "classification_reason_selected": "path-under-~/.cargo/bin",
      "latest_upstream": "14.1.1 (220ms)",
      "latest_version": "14.1.1",
      "upstream_method": "github",
      "status": "UP-TO-DATE",
      "tool_url": "https://github.com/BurntSushi/ripgrep",
      "latest_url": "https://github.com/BurntSushi/ripgrep/releases/tag/14.1.1"
    }
  ]
}
```

### latest_versions.json

```json
{
  "__hints__": {
    "gh:BurntSushi/ripgrep": "latest_redirect",
    "gh:sharkdp/fd": "latest_redirect",
    "local_flag:ripgrep": "-V",
    "local_flag:fd": "--version"
  },
  "__methods__": {
    "pip": "pypi",
    "pipx": "pypi",
    "poetry": "pypi"
  },
  "ripgrep": "14.1.1",
  "fd": "10.3.0",
  "black": "25.1.0"
}
```

**Fields:**
- `__hints__`: API method cache (which methods worked)
- `__methods__`: Upstream source overrides per tool
- `<tool_name>`: Latest version string

---

## See Also

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and data flow
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - How to use these APIs
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Debugging with environment variables
