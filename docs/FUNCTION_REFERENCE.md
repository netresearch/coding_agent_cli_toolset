# Function Reference

Quick lookup reference for functions in `cli_audit.py`, organized by category.

## Quick Lookup Table

| Category | Key Functions | Purpose |
|----------|---------------|---------|
| **Snapshot** | `load_snapshot`, `write_snapshot`, `render_from_snapshot` | Snapshot file management |
| **Version Discovery** | `find_paths`, `get_version_line`, `extract_version_number`, `choose_highest` | Local tool detection |
| **Classification** | `detect_install_method`, `_classify_install_method` | Installation method detection |
| **Upstream APIs** | `latest_github`, `latest_pypi`, `latest_crates`, `latest_npm`, `latest_gnu` | Fetch upstream versions |
| **HTTP** | `http_fetch`, `http_get` | Network layer with retries |
| **Cache** | `load_manual_versions`, `get_manual_latest`, `set_manual_latest` | Cache management |
| **Core** | `audit_tool`, `get_latest`, `main` | Main audit logic |

---

## Snapshot Management

Functions for reading/writing snapshot files that decouple data collection from rendering.

### `load_snapshot(paths=None) -> dict[str, Any]`

Load snapshot from file.

**Parameters:**
- `paths` (`Sequence[str] | None`) - Custom paths to try (default: `[SNAPSHOT_FILE, "upstream_versions.json"]`)

**Returns:**
- `dict[str, Any]` - Document with `__meta__` and `tools` keys

**Usage:**
```python
doc = load_snapshot()
meta = doc["__meta__"]
tools = doc["tools"]
print(f"Snapshot has {meta['count']} tools from {meta['created_at']}")
```

**See:** [API_REFERENCE.md#load_snapshot](API_REFERENCE.md#load_snapshot)

---

### `write_snapshot(tools_payload, extra=None) -> dict[str, Any]`

Write audit results to snapshot file atomically.

**Parameters:**
- `tools_payload` (`list[dict]`) - Tool audit results
- `extra` (`dict | None`) - Additional metadata fields

**Returns:**
- `dict[str, Any]` - Metadata object that was written

**Side Effects:** Writes `tools_snapshot.json` atomically

**Usage:**
```python
results = [audit_tool(tool) for tool in TOOLS]
meta = write_snapshot(results, extra={"partial": True})
```

**See:** [API_REFERENCE.md#write_snapshot](API_REFERENCE.md#write_snapshot)

---

### `render_from_snapshot(doc, selected=None) -> list[tuple]`

Extract and filter tools from snapshot for rendering.

**Parameters:**
- `doc` (`dict`) - Snapshot document from `load_snapshot()`
- `selected` (`set[str] | None`) - Tool names to include (lowercase)

**Returns:**
- `list[tuple]` - List of 8-element tuples: `(name, installed, installed_method, latest, upstream_method, status, tool_url, latest_url)`

**Usage:**
```python
doc = load_snapshot()
selected = {"python", "ripgrep", "jq"}
rows = render_from_snapshot(doc, selected)
for name, installed, method, latest, _, status, _, _ in rows:
    print(f"{name}: {installed} via {method} (latest: {latest}) - {status}")
```

**See:** [API_REFERENCE.md#render_from_snapshot](API_REFERENCE.md#render_from_snapshot)

---

## Version Discovery

Functions for discovering installed tool versions on the local system.

### `find_paths(command_name, deep=False) -> list[str]`

Find all paths for a command on PATH.

**Parameters:**
- `command_name` (`str`) - Executable name to search
- `deep` (`bool`) - If True, also checks `~/.cargo/bin` for Rust tools

**Returns:**
- `list[str]` - List of absolute paths (duplicates removed)

**Usage:**
```python
# Basic search
paths = find_paths("python3")
# ["/usr/bin/python3", "/usr/local/bin/python3"]

# Deep search for Rust tools
paths = find_paths("rg", deep=True)
# ["/usr/bin/rg", "/home/user/.cargo/bin/rg"]
```

**See:** [API_REFERENCE.md#find_paths](API_REFERENCE.md#find_paths)

---

### `get_version_line(path, tool_name) -> str`

Extract version string from executable.

**Parameters:**
- `path` (`str`) - Absolute path to executable
- `tool_name` (`str`) - Tool name for special handling

**Returns:**
- `str` - First line of version output, or empty string on failure

**Special Cases:**
- Most tools: `<path> --version`
- `go`, `curlie`, `isort`: Custom version flags
- `entr`, `sponge`: No version flag (returns empty)

**Usage:**
```python
line = get_version_line("/usr/bin/rg", "ripgrep")
# "ripgrep 14.1.1"

line = get_version_line("/usr/bin/go", "go")
# "go version go1.22.0 linux/amd64"
```

**See:** [API_REFERENCE.md#get_version_line](API_REFERENCE.md#get_version_line)

---

### `extract_version_number(s) -> str`

Parse semantic version from string.

**Parameters:**
- `s` (`str`) - Raw version string

**Returns:**
- `str` - Cleaned version number (e.g., "14.1.1")

**Patterns Handled:**
- Semantic: `v14.1.1`, `14.1.1`, `1.2.3-beta`
- Prefixed: `jq-1.8.1`, `go1.25.1`, `poetry (version 1.8.2)`
- Date-based: `20250822` (GNU parallel)

**Usage:**
```python
extract_version_number("ripgrep 14.1.1 (rev abc123)")
# "14.1.1"

extract_version_number("jq-1.8.1")
# "1.8.1"

extract_version_number("go version go1.22.0 linux/amd64")
# "1.22.0"
```

**See:** [API_REFERENCE.md#extract_version_number](API_REFERENCE.md#extract_version_number)

---

### `choose_highest(installed) -> tuple[str, str, str] | tuple[()]`

Select highest version from multiple installations.

**Parameters:**
- `installed` (`list[tuple[str, str, str]]`) - List of `(version, path, method)` tuples

**Returns:**
- `tuple[str, str, str]` - Best version tuple: `(version, path, method)`
- `tuple[()]` - Empty tuple if no valid versions

**Logic:**
1. Parse each version as semantic version
2. Select highest by major.minor.patch comparison
3. Tiebreak by path (prefer user installs over system)

**Usage:**
```python
installed = [
    ("14.1.0", "/usr/bin/rg", "apt/dpkg"),
    ("14.1.1", "/home/user/.cargo/bin/rg", "rustup/cargo")
]
best = choose_highest(installed)
# ("14.1.1", "/home/user/.cargo/bin/rg", "rustup/cargo")
```

**See:** [API_REFERENCE.md#choose_highest](API_REFERENCE.md#choose_highest)

---

### `choose_node_preferred(installed) -> tuple[str, str, str] | tuple[()]`

Select preferred Node.js installation (nvm-managed over system).

**Parameters:**
- `installed` (`list[tuple[str, str, str]]`) - List of Node installation tuples

**Returns:**
- `tuple[str, str, str]` - Preferred installation (prioritizes nvm)

**Logic:**
1. Prefer nvm-managed installations over system
2. Among nvm installations, choose highest version
3. Fall back to highest system version if no nvm

**Usage:**
```python
installed = [
    ("18.20.0", "/usr/bin/node", "apt/dpkg"),
    ("22.13.0", "/home/user/.nvm/versions/node/v22.13.0/bin/node", "nvm/npm")
]
best = choose_node_preferred(installed)
# ("22.13.0", "/home/user/.nvm/.../bin/node", "nvm/npm")
```

---

## Installation Classification

Functions for identifying how tools were installed.

### `detect_install_method(path, tool_name) -> str`

Classify how a tool was installed.

**Parameters:**
- `path` (`str`) - Absolute path to executable
- `tool_name` (`str`) - Tool name for context

**Returns:**
- `str` - Human-readable method string

**Classifications:**

| Method | Path Pattern | Example |
|--------|--------------|---------|
| `uv tool` | `~/.local/share/uv/`, uv tools list | `uv tool install black` |
| `uv venv` | `~/.venvs/` in shebang | `uv venv` project |
| `pipx/user` | `~/.local/pipx/venvs/` | `pipx install black` |
| `nvm/npm` | `~/.nvm/versions/` | `nvm install 20` |
| `rustup/cargo` | `~/.cargo/bin/` | `cargo install ripgrep` |
| `go install` | `$GOPATH/bin/` | `go install ...` |
| `asdf` | `~/.asdf/shims/`, `~/.asdf/installs/` | `asdf install python` |
| `pyenv` | `~/.pyenv/shims/` | `pyenv install 3.12` |
| `volta` | `~/.volta/` | `volta install node` |
| `homebrew` | `/opt/homebrew/`, `/home/linuxbrew/` | `brew install fd` |
| `apt/dpkg` | `/usr/bin/`, dpkg-owned | `apt install ripgrep` |
| `snap` | `/snap/` | `snap install kubectl` |
| `~/.local/bin` | `~/.local/bin/` | Manual user install |
| `/usr/local/bin` | `/usr/local/bin/` | Manual system install |

**Usage:**
```python
method = detect_install_method("/home/user/.cargo/bin/rg", "ripgrep")
# "rustup/cargo"

method = detect_install_method("/usr/bin/python3.12", "python")
# "apt/dpkg"

method = detect_install_method("/home/user/.local/bin/black", "black")
# Could be "pipx/user", "uv tool", or "~/.local/bin" depending on shebang
```

**See:** [API_REFERENCE.md#detect_install_method](API_REFERENCE.md#detect_install_method)

---

### `_classify_install_method(path, tool_name) -> tuple[str, str]`

Internal function returning method and classification reason.

**Parameters:**
- `path` (`str`) - Absolute path to executable
- `tool_name` (`str`) - Tool name for context

**Returns:**
- `tuple[str, str]` - `(method, reason)` tuple

**Reason Codes:**
- `"path-under-~/.cargo/bin"` - Rust cargo installation
- `"shebang-pipx-venv"` - pipx wrapper script
- `"dpkg-cache-hit"` - Previously cached dpkg query
- `"no-match"` - Unknown installation method

**Usage:**
```python
method, reason = _classify_install_method("/usr/bin/rg", "ripgrep")
# ("apt/dpkg", "dpkg-query")

method, reason = _classify_install_method("/home/user/.local/bin/black", "black")
# Could be ("pipx/user", "shebang-pipx-venv") if shebang points to pipx
```

---

## Upstream APIs

Functions for fetching latest versions from upstream sources.

### `latest_github(owner, repo) -> tuple[str, str]`

Fetch latest GitHub release.

**Parameters:**
- `owner` (`str`) - GitHub username/org
- `repo` (`str`) - Repository name

**Returns:**
- `tuple[str, str]` - `(version_tag, method)` where method is:
  - `"latest_redirect"` - Used `/releases/latest` with redirect
  - `"atom"` - Parsed Atom feed

**Strategies:**
1. Try `/repos/{owner}/{repo}/releases/latest` with redirect following
2. On failure, try Atom feed at `/releases.atom`

**Usage:**
```python
tag, method = latest_github("sharkdp", "fd")
# ("v10.3.0", "latest_redirect")

tag, method = latest_github("BurntSushi", "ripgrep")
# ("14.1.1", "latest_redirect")
# "latest_redirect"
```

**See:** [API_REFERENCE.md#latest_github](API_REFERENCE.md#latest_github)

---

### `latest_pypi(package) -> tuple[str, str]`

Fetch latest PyPI version.

**Parameters:**
- `package` (`str`) - PyPI package name

**Returns:**
- `tuple[str, str]` - `(version, "pypi")`

**API:** `https://pypi.org/pypi/{package}/json`

**Usage:**
```python
version, method = latest_pypi("black")
# ("25.1.0", "pypi")

version, method = latest_pypi("poetry")
# ("1.8.2", "pypi")
```

**See:** [API_REFERENCE.md#latest_pypi](API_REFERENCE.md#latest_pypi)

---

### `latest_crates(crate) -> tuple[str, str]`

Fetch latest crates.io version.

**Parameters:**
- `crate` (`str`) - Crate name

**Returns:**
- `tuple[str, str]` - `(version, "crates")`

**API:** `https://crates.io/api/v1/crates/{crate}`

**Usage:**
```python
version, method = latest_crates("ripgrep")
# ("14.1.1", "crates")

version, method = latest_crates("fd-find")
# ("10.3.0", "crates")
```

**See:** [API_REFERENCE.md#latest_crates](API_REFERENCE.md#latest_crates)

---

### `latest_npm(package) -> tuple[str, str]`

Fetch latest npm version.

**Parameters:**
- `package` (`str`) - npm package name

**Returns:**
- `tuple[str, str]` - `(version, "npm")`

**API:** `https://registry.npmjs.org/{package}`

**Usage:**
```python
version, method = latest_npm("eslint")
# ("9.35.0", "npm")

version, method = latest_npm("prettier")
# ("3.4.2", "npm")
```

**See:** [API_REFERENCE.md#latest_npm](API_REFERENCE.md#latest_npm)

---

### `latest_gnu(project) -> tuple[str, str]`

Fetch latest GNU project version via FTP.

**Parameters:**
- `project` (`str`) - GNU project name

**Returns:**
- `tuple[str, str]` - `(version, "gnu-ftp")`

**API:** `https://ftp.gnu.org/gnu/{project}/`

**Usage:**
```python
version, method = latest_gnu("parallel")
# ("20250822", "gnu-ftp")

version, method = latest_gnu("tar")
# ("1.35", "gnu-ftp")
```

**See:** [API_REFERENCE.md#latest_gnu](API_REFERENCE.md#latest_gnu)

---

### `latest_yarn() -> tuple[str, str]`

Fetch latest Yarn version from official tags feed.

**Returns:**
- `tuple[str, str]` - `(version, "yarn-tags")`

**API:** `https://repo.yarnpkg.com/tags`

**Usage:**
```python
version, method = latest_yarn()
# ("4.6.0", "yarn-tags")
```

---

## HTTP Layer

Network functions with retry logic and per-origin rate limiting.

### `http_fetch(url, timeout=3, headers=None, retries=2, ...) -> bytes`

Fetch URL with retries and backoff.

**Parameters:**
- `url` (`str`) - Target URL
- `timeout` (`float | int`) - Timeout per attempt in seconds (default: 3)
- `headers` (`dict[str, str] | None`) - HTTP headers (default: User-Agent only)
- `retries` (`int`) - Retry attempts (default: 2, via `CLI_AUDIT_HTTP_RETRIES`)
- `backoff_base` (`float`) - Exponential backoff base (default: 0.2s)
- `jitter` (`float`) - Random jitter range (default: 0.1s)
- `method` (`str | None`) - HTTP method (default: GET)

**Returns:**
- `bytes` - Response body, or empty bytes on failure

**Features:**
- Exponential backoff: `base * 2^attempt + random(0, jitter)`
- Per-host Accept header negotiation
- Per-origin concurrency caps (semaphores)
- GitHub token authentication for api.github.com
- Retryable HTTP errors: 429 (rate limit), 5xx (server errors), 403 (GitHub)

**Usage:**
```python
# Basic fetch
data = http_fetch("https://pypi.org/pypi/black/json")
if data:
    response = json.loads(data)

# With custom headers
data = http_fetch(
    "https://api.github.com/repos/owner/repo",
    headers={"Accept": "application/vnd.github+json"}
)

# With increased retries
data = http_fetch(url, retries=5, timeout=5)
```

**See:** [API_REFERENCE.md#http_fetch](API_REFERENCE.md#http_fetch)

---

### `http_get(url) -> bytes`

Simplified wrapper around `http_fetch` with defaults.

**Parameters:**
- `url` (`str`) - Target URL

**Returns:**
- `bytes` - Response body

**Usage:**
```python
data = http_get("https://pypi.org/pypi/black/json")
```

---

## Cache Management

Multi-tier caching system for offline operation and performance.

### `load_manual_versions() -> None`

Load manual cache from `upstream_versions.json`.

**Side Effects:** Populates global `MANUAL_VERSIONS` dict

**Called:** Automatically at module import

**Usage:**
```python
# Usually automatic, but can be called explicitly
load_manual_versions()
version = MANUAL_VERSIONS.get("ripgrep", "")
```

**See:** [API_REFERENCE.md#load_manual_versions](API_REFERENCE.md#load_manual_versions)

---

### `get_manual_latest(tool_name) -> tuple[str, str]`

Get cached version for a tool.

**Parameters:**
- `tool_name` (`str`) - Tool name (lowercase)

**Returns:**
- `tuple[str, str]` - `(tag, version)` or `("", "")` if not cached

**Usage:**
```python
tag, version = get_manual_latest("ripgrep")
if version:
    print(f"Cached version: {version}")
else:
    print("No cached version")
```

**See:** [API_REFERENCE.md#get_manual_latest](API_REFERENCE.md#get_manual_latest)

---

### `set_manual_latest(tool_name, tag_or_version) -> None`

Update manual cache with new version.

**Parameters:**
- `tool_name` (`str`) - Tool name
- `tag_or_version` (`str`) - Version string or tag

**Side Effects:** Writes to `upstream_versions.json` (requires `MANUAL_LOCK`)

**Usage:**
```python
set_manual_latest("ripgrep", "14.1.1")
# Updates upstream_versions.json atomically
```

**See:** [API_REFERENCE.md#set_manual_latest](API_REFERENCE.md#set_manual_latest)

---

## Core Audit Functions

Main audit logic coordinating all subsystems.

### `audit_tool(tool) -> tuple[str, str, str, str, str, str, str, str]`

Perform complete audit for one tool.

**Parameters:**
- `tool` (`Tool`) - Tool definition

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
1. Find all installed versions via `find_paths()`
2. Extract version from each via `get_version_line()` + `extract_version_number()`
3. Classify installation methods via `detect_install_method()`
4. Choose best version via `choose_highest()`
5. Fetch latest from upstream via `get_latest()`
6. Compare versions and determine status
7. Generate URLs if `ENABLE_LINKS=1`

**Usage:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
result = audit_tool(tool)

name, installed, method, latest, source, status, _, _ = result
print(f"{name}: {installed} via {method} (latest: {latest}) - {status}")
# ripgrep: 14.1.1 (150ms) via rustup/cargo (latest: 14.1.1 (220ms)) - UP-TO-DATE
```

**See:** [API_REFERENCE.md#audit_tool](API_REFERENCE.md#audit_tool)

---

### `get_latest(tool) -> tuple[str, str]`

Get latest upstream version for a tool.

**Parameters:**
- `tool` (`Tool`) - Tool definition

**Returns:**
- `tuple[str, str]` - `(version, method)` - version string and source method

**Cache Strategy:**
1. Try upstream API (with retries)
2. On success, update cache
3. On failure, fall back to cached upstream
4. Final fallback: return `("", "")`

**Usage:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
version, method = get_latest(tool)
# ("14.1.1", "github")

# In offline mode (OFFLINE_MODE=1):
version, method = get_latest(tool)
# Uses manual cache only: ("14.1.1", "manual")
```

**See:** [API_REFERENCE.md#get_latest](API_REFERENCE.md#get_latest)

---

### `main() -> int`

CLI entry point and mode router.

**Returns:**
- `int` - Exit code (0 for success)

**Modes:**
- **COLLECT_ONLY** (`CLI_AUDIT_COLLECT=1`): Fetch data, write snapshot, no output
- **RENDER_ONLY** (`CLI_AUDIT_RENDER=1`): Read snapshot, render output, no network
- **NORMAL**: Full audit with collection and rendering

**Flow:**
```
main()
  ├─ Parse arguments (--only, --json, --alpha)
  ├─ Detect mode (COLLECT_ONLY | RENDER_ONLY | NORMAL)
  │
  ├─ COLLECT_ONLY:
  │   ├─ ThreadPoolExecutor(MAX_WORKERS)
  │   ├─ audit_tool() for each tool in parallel
  │   └─ write_snapshot(results)
  │
  ├─ RENDER_ONLY:
  │   ├─ load_snapshot()
  │   ├─ render_from_snapshot(doc, selected)
  │   └─ format_output(rows)
  │
  └─ NORMAL:
      ├─ [COLLECT_ONLY pipeline]
      └─ [RENDER_ONLY pipeline]
```

**Usage:**
```python
# From command line
if __name__ == "__main__":
    sys.exit(main())

# Programmatic
exit_code = main()
```

---

## Utility Functions

Helper functions for formatting and display.

### `status_icon(status, installed_line) -> str`

Return a single-character icon for the installed state/status.

**Parameters:**
- `status` (`str`) - Status: "UP-TO-DATE", "OUTDATED", "NOT INSTALLED", "UNKNOWN"
- `installed_line` (`str`) - Installed version line ("X" if not installed)

**Returns:**
- `str` - Icon character (emoji if `USE_EMOJI_ICONS=1`, ASCII otherwise)

**Icons:**

| Status | Emoji Mode | ASCII Mode |
|--------|------------|------------|
| UP-TO-DATE | ✅ | + |
| OUTDATED | 🔼 | ! |
| NOT INSTALLED | ❌ | x |
| UNKNOWN | ❓ | ? |

**Usage:**
```python
icon = status_icon("UP-TO-DATE", "14.1.1")
# "✅" (if USE_EMOJI_ICONS=1) or "+" (if USE_EMOJI_ICONS=0)

icon = status_icon("NOT INSTALLED", "X")
# "❌" (emoji) or "x" (ASCII)
```

---

### `_format_duration(seconds) -> str`

Format duration for display.

**Parameters:**
- `seconds` (`float`) - Duration in seconds

**Returns:**
- `str` - Formatted duration: "150ms" or "2s"

**Usage:**
```python
_format_duration(0.15)
# "150ms"

_format_duration(2.3)
# "2s"
```

---

### `osc8(url, text) -> str`

Create OSC 8 hyperlink for terminal display.

**Parameters:**
- `url` (`str`) - Target URL
- `text` (`str`) - Display text

**Returns:**
- `str` - ANSI escape sequence for hyperlink

**Usage:**
```python
link = osc8("https://github.com/BurntSushi/ripgrep", "ripgrep")
print(link)
# Displays as clickable "ripgrep" in supporting terminals
```

---

### `tool_homepage_url(tool) -> str`

Generate homepage URL for a tool.

**Parameters:**
- `tool` (`Tool`) - Tool definition

**Returns:**
- `str` - Homepage URL based on source kind

**Usage:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
url = tool_homepage_url(tool)
# "https://github.com/BurntSushi/ripgrep"
```

---

### `latest_target_url(tool, latest_tag, latest_num) -> str`

Generate URL for latest release.

**Parameters:**
- `tool` (`Tool`) - Tool definition
- `latest_tag` (`str`) - Latest version tag
- `latest_num` (`str`) - Latest version number

**Returns:**
- `str` - URL to latest release page

**Usage:**
```python
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
url = latest_target_url(tool, "14.1.1", "14.1.1")
# "https://github.com/BurntSushi/ripgrep/releases/tag/14.1.1"
```

---

## Internal Utilities

Private functions supporting core operations.

### `_read_json_safe(path) -> dict[str, Any]`

Read JSON file with error suppression.

**Parameters:**
- `path` (`str`) - File path

**Returns:**
- `dict[str, Any]` - Parsed JSON or empty dict on error

---

### `_atomic_write_json(path, obj) -> None`

Write JSON file atomically (write to temp, then rename).

**Parameters:**
- `path` (`str`) - Target file path
- `obj` (`Any`) - Object to serialize

**Side Effects:** Writes file atomically

---

### `_now_iso() -> str`

Get current UTC timestamp in ISO 8601 format.

**Returns:**
- `str` - Timestamp like "2025-10-09T12:34:56Z"

---

### `_vlog(msg) -> None`

Log verbose message to stderr.

**Parameters:**
- `msg` (`str`) - Message to log

**Enabled:** When `PROGRESS=1` or `TRACE=1`

---

### `_tlog(msg) -> None`

Log trace message to stderr.

**Parameters:**
- `msg` (`str`) - Trace message

**Enabled:** When `TRACE=1`

---

### `_accept_header_for_host(host) -> str`

Determine appropriate Accept header for host.

**Parameters:**
- `host` (`str`) - Hostname

**Returns:**
- `str` - Accept header value

**Mappings:**
- `api.github.com` → `"application/vnd.github+json"`
- `registry.npmjs.org`, `crates.io` → `"application/json"`
- GNU FTP mirrors → `"text/html,..."`

---

### `_load_uv_tools() -> None`

Populate UV_TOOLS set by running `uv tool list`.

**Side Effects:** Populates global `UV_TOOLS` set

---

### `_is_uv_tool(tool_name) -> bool`

Check if tool is managed by uv.

**Parameters:**
- `tool_name` (`str`) - Tool name

**Returns:**
- `bool` - True if tool in UV_TOOLS

---

### `_dpkg_owner_for_path(path) -> str`

Query dpkg to find package owning a file.

**Parameters:**
- `path` (`str`) - File path

**Returns:**
- `str` - Package name or empty string

**Caching:** Results cached in `DPKG_OWNER_CACHE`

---

### `_dpkg_version_for_pkg(pkg) -> str`

Query dpkg for installed version of package.

**Parameters:**
- `pkg` (`str`) - Package name

**Returns:**
- `str` - Version string

**Caching:** Results cached in `DPKG_VERSION_CACHE`

---

### `_node_pkg_version_from_path(tool_name, exe_path) -> str`

Extract Node package version from adjacent package.json.

**Parameters:**
- `tool_name` (`str`) - Tool name
- `exe_path` (`str`) - Executable path

**Returns:**
- `str` - Version from package.json or empty

---

### `_python_dist_version_from_venv(tool_name, exe_path, dist_name) -> str`

Extract Python distribution version from venv metadata.

**Parameters:**
- `tool_name` (`str`) - Tool name
- `exe_path` (`str`) - Executable path
- `dist_name` (`str`) - Distribution name

**Returns:**
- `str` - Version from importlib.metadata or empty

---

### `_uv_primary_python() -> tuple[str, str, str] | tuple[()]`

Detect uv's primary Python installation.

**Returns:**
- `tuple[str, str, str]` - `(version, path, method)` or empty tuple

---

## Category Helpers

### `category_for(tool_name) -> str`

Determine category for a tool (used for grouping).

**Parameters:**
- `tool_name` (`str`) - Tool name

**Returns:**
- `str` - Category: "Language Runtimes", "Package Managers", "Core Developer Tools", etc.

**Usage:**
```python
category = category_for("python")
# "Language Runtimes"

category = category_for("ripgrep")
# "Core Developer Tools"
```

---

### `hint_for(tool_name) -> str`

Get remediation hint for a tool (used for hints display).

**Parameters:**
- `tool_name` (`str`) - Tool name

**Returns:**
- `str` - Hint like "Install via: cargo install ripgrep"

**Usage:**
```python
hint = hint_for("ripgrep")
# "Install via: cargo install ripgrep"

hint = hint_for("black")
# "Install via: uv tool install black"
```

---

## Environment Variables Reference

See [API_REFERENCE.md#environment-variables](API_REFERENCE.md#environment-variables) for complete list.

**Key Variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLI_AUDIT_COLLECT` | `0` | Collect-only mode |
| `CLI_AUDIT_RENDER` | `0` | Render-only mode |
| `CLI_AUDIT_OFFLINE` | `0` | Force offline (use cache only) |
| `CLI_AUDIT_MAX_WORKERS` | `16` | ThreadPoolExecutor concurrency |
| `CLI_AUDIT_TIMEOUT_SECONDS` | `3` | Timeout per tool audit |
| `CLI_AUDIT_HTTP_RETRIES` | `2` | HTTP retry attempts |
| `CLI_AUDIT_TIMINGS` | `1` | Show timing info |
| `CLI_AUDIT_EMOJI` | `1` | Use emoji icons |
| `CLI_AUDIT_LINKS` | `1` | Include OSC 8 hyperlinks |
| `GITHUB_TOKEN` | `""` | GitHub API token |

---

## Cross-References

### Architecture

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, data flow, resilience patterns
- **Component Details** - How functions fit into broader system
- **Threading Model** - Lock ordering, concurrency strategy

### API Reference

- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete function signatures
- **Data Structures** - Tool dataclass, TOOLS registry
- **File Schemas** - tools_snapshot.json, upstream_versions.json

### Developer Guide

- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - How to use APIs
- **Extension Points** - Adding new tools, sources, classification rules

### Troubleshooting

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Debugging with environment variables
- **Common Issues** - Function failures and solutions

---

## Usage Patterns

### Pattern 1: Full Audit Workflow

```python
# 1. Audit all tools in parallel
results = []
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {executor.submit(audit_tool, tool): tool for tool in TOOLS}
    for future in as_completed(futures):
        results.append(future.result())

# 2. Write snapshot
meta = write_snapshot(results)

# 3. Render output
doc = load_snapshot()
rows = render_from_snapshot(doc)
for row in rows:
    print("|".join(row))
```

### Pattern 2: Offline Audit from Cache

```python
# Set offline mode
import os
os.environ["CLI_AUDIT_OFFLINE"] = "1"

# Audit uses manual cache only
for tool in TOOLS:
    result = audit_tool(tool)
    print(result)
```

### Pattern 3: Incremental Updates

```python
# Check single tool
tool = Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))
result = audit_tool(tool)
name, installed, method, latest, _, status, _, _ = result

if status == "OUTDATED":
    print(f"{name} needs update: {installed} → {latest}")
```

### Pattern 4: Custom Classification

```python
# Detect installation method
path = "/home/user/.cargo/bin/rg"
method = detect_install_method(path, "ripgrep")
# "rustup/cargo"

# Get detailed reason
method, reason = _classify_install_method(path, "ripgrep")
# ("rustup/cargo", "path-under-~/.cargo/bin")
```

### Pattern 5: Version Discovery

```python
# Find all installations
paths = find_paths("python3", deep=False)
# ["/usr/bin/python3", "/usr/local/bin/python3"]

# Get versions
installed = []
for path in paths:
    line = get_version_line(path, "python")
    version = extract_version_number(line)
    method = detect_install_method(path, "python")
    installed.append((version, path, method))

# Choose best
best = choose_highest(installed)
version, path, method = best
print(f"Best: {version} at {path} via {method}")
```

---

## See Also

- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System architecture and design
- **[API_REFERENCE.md](../docs/API_REFERENCE.md)** - Complete API documentation
- **[DEVELOPER_GUIDE.md](../docs/DEVELOPER_GUIDE.md)** - Development practices
- **[TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)** - Debugging guide
- **[scripts/README.md](../scripts/README.md)** - Installation scripts documentation
