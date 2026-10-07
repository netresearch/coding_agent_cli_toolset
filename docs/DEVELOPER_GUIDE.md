<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<!-- SPDX-FileCopyrightText: Netresearch DTT GmbH -->

# Developer Guide

## Contributing to AI CLI Preparation

This guide helps you contribute effectively to the project, whether adding new tools, fixing bugs, or improving documentation.

## Prerequisites

- Python 3.9+ (project uses 3.14.0rc2 in development)
- Git and GitHub CLI (`gh`) recommended
- Basic understanding of Python threading and HTTP APIs
- Familiarity with package managers (pip, npm, cargo, etc.)

## Development Workflow

### 1. Setup Development Environment

```bash
# Clone repository
git clone git@github.com:netresearch/coding_agent_cli_toolset.git
cd coding_agent_cli_toolset

# Check your environment
uv run python audit.py | python3 smart_column.py -s "|" -t --right 3,4 --header

# Install optional dependencies for better emoji support
pip install wcwidth  # For smart_column.py
```

### 2. Create Feature Branch

```bash
# Always work on feature branches, never main
git checkout -b feature/add-new-tool
```

### 3. Make Changes

Follow patterns in existing code (see sections below).

### 4. Test Your Changes

```bash
# Manual testing (fresh check, JSON output, snapshot unchanged)
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py your-new-tool

# Smoke test
bash scripts/test_smoke.sh

# Full audit
make update && make audit
```

### 5. Commit and Push

```bash
git add catalog/new-tool.json upstream_versions.json
git commit -m "feat(tools): add support for new-tool"
git push -u origin feature/add-new-tool
```

### 6. Create Pull Request

```bash
gh pr create --title "Add support for new-tool" --body "Description of changes"
```

## Adding New Tools

### Step 1: Define the Tool

Create `catalog/tool-name.json` (tools are loaded from the catalog; see [CATALOG_GUIDE.md](CATALOG_GUIDE.md) for all fields):

```json
{
  "name": "tool-name",
  "install_method": "github_release_binary",
  "category": "general",
  "description": "What the tool does",
  "homepage": "https://github.com/owner/repo",
  "github_repo": "owner/repo",
  "binary_name": "executable",
  "candidates": ["executable"]
}
```

**Placement Considerations:**
- Place in appropriate category (runtimes, package managers, dev tools, security, etc.)
- Consider logical grouping for output organization
- Runtimes should come before tools that depend on them

### Step 2: Choose Source Kind

| Source Kind | Use When | Source Args Example |
|-------------|----------|---------------------|
| `"gh"` | Tool has GitHub releases | `("owner", "repo")` |
| `"pypi"` | Python package on PyPI | `("package-name",)` |
| `"crates"` | Rust crate on crates.io | `("crate-name",)` |
| `"npm"` | npm package | `("package-name",)` |
| `"gnu"` | GNU project with FTP releases | `("project-name",)` |
| `"skip"` | No discoverable upstream | `()` |

### Step 3: Handle Multiple Candidates

If a tool has different names across distributions:

```json
"candidates": ["fd", "fdfind"]
```

Every name is checked; when several are installed, the one whose version string sorts highest (compared as text) is reported.

**Common Cases:**
- Debian renames: `bat` → `batcat`, `fd` → `fdfind`
- Alternative names: `ripgrep` has `rg`, `ast-grep` has `sg`

### Step 4: Add Special Version Detection (if needed)

Most tools work with `--version`, but some need custom handling:

Set `version_flag` or `version_command` in the catalog entry; `get_version_line()` in `cli_audit/detection.py` uses them:

```json
"version_flag": "version"
```

### Step 5: Test Your Addition

```bash
# Test single tool (fresh check with debug output, JSON, snapshot unchanged)
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py your-tool

# Table view (renders from the snapshot written by make update)
make update && make audit-your-tool
```

### Step 6: Update Manual Cache

Add initial version to `upstream_versions.json`:

```json
{
  "your-tool": "1.2.3"
}
```

This provides offline fallback and speeds up first runs.

### Step 7: Document the Tool

Update `TOOL_ECOSYSTEM.md` with:
- Tool name and category
- Purpose and use case
- Installation methods
- Recommended upgrade path

## Complete Example: Adding a New Tool

Let's add `deno` (JavaScript/TypeScript runtime):

**1. Add a catalog entry:**
```json
{
  "name": "deno",
  "install_method": "github_release_binary",
  "category": "node",
  "description": "JavaScript/TypeScript runtime",
  "homepage": "https://github.com/denoland/deno",
  "github_repo": "denoland/deno",
  "binary_name": "deno",
  "candidates": ["deno"]
}
```

**2. Test it:**
```bash
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 uv run python audit.py deno | jq '.'
```

**3. Add to manual cache:**
```json
{
  "deno": "2.1.4"
}
```

**4. Commit:**
```bash
git add catalog/deno.json upstream_versions.json
git commit -m "feat(tools): add Deno runtime support"
```

## Code Style and Conventions

### Python Style

- **PEP 8 compliant** (use `pyflakes` for linting)
- **Type hints:** Use for function signatures
- **Docstrings:** Add for public functions
- **Error handling:** Graceful degradation, never crash
- **Immutability:** Prefer frozen dataclasses and tuples

**Example:**
```python
def get_version_line(path: str, tool_name: str) -> str:
    """Extract version string from executable.

    Args:
        path: Absolute path to executable
        tool_name: Tool name for special handling

    Returns:
        First line of version output, or empty string on failure
    """
    try:
        return run_with_timeout([path, "--version"])
    except Exception:
        return ""  # Graceful failure
```

### Naming Conventions

- **Functions:** `snake_case` (e.g., `get_version_line`)
- **Private functions:** `_leading_underscore` (e.g., `_dpkg_owner_for_path`)
- **Classes:** `PascalCase` (e.g., `Tool`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `TIMEOUT_SECONDS`)
- **Environment variables:** `CLI_AUDIT_*` prefix

### Error Handling Pattern

```python
def risky_operation():
    try:
        result = potentially_failing_operation()
        return result
    except Exception as e:
        if AUDIT_DEBUG:
            print(f"# DEBUG: operation failed: {e}", file=sys.stderr)
        return ""  # or appropriate default
```

**Principles:**
- Never let exceptions propagate to top level
- Log errors only in debug mode
- Return sensible defaults (empty string, empty list, tuple)
- Continue audit even if one tool fails

### Threading Safety

File writes use atomic operations (write to temp, then rename) to prevent corruption.

## Testing Strategies

### Manual Testing

```bash
# Test single tool
uv run python audit.py ripgrep

# Test category
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "python")'

# Test with debug output
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py ripgrep

# Test offline mode
CLI_AUDIT_OFFLINE=1 uv run python audit.py ripgrep

# Test JSON output
CLI_AUDIT_JSON=1 uv run python audit.py ripgrep | jq '.'
```

### Smoke Testing

The project includes a smoke test script:

```bash
bash scripts/test_smoke.sh
```

**What it tests:**
- 5-column table header (last column `notes`)
- JSON mode with expected fields

### Performance Testing

```bash
# Measure collection time
time uv run python audit.py --update

# Measure render time (should be <100ms)
time CLI_AUDIT_RENDER=1 uv run python audit.py > /dev/null

# Find slow tools (debug output while collecting)
make update-debug
```

### Validation Testing

```bash
# Ensure manual cache is valid JSON
jq '.' upstream_versions.json > /dev/null

# Ensure snapshot is valid
jq '.__meta__.schema_version' tools_snapshot.json

# Check for version parsing issues
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.installed_version == "")'
```

## Common Patterns and Idioms

### Pattern 1: Cache-First with Fallback

```python
def get_latest(tool: Tool) -> tuple[str, str]:
    # Try upstream with retries
    version, method = try_upstream(tool)
    if version:
        update_caches(tool.name, version, method)
        return (version, method)

    # Fallback to manual cache
    return get_manual_latest(tool.name)
```

### Pattern 2: Parallel with Timeout

```python
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(task, item): item for item in items}
    for future in as_completed(futures):
        try:
            result = future.result(timeout=TIMEOUT_SECONDS)
            handle_result(result)
        except Exception:
            continue  # Isolated failure
```

### Pattern 3: Atomic File Update

```python
def atomic_update(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)  # Atomic on POSIX
```

### Pattern 4: Version Comparison

```python
from packaging import version

def compare_versions(v1: str, v2: str) -> int:
    try:
        return version.parse(v1).__cmp__(version.parse(v2))
    except Exception:
        return 0  # Can't compare, assume equal
```

## Debugging Techniques

### Enable Debug Output

```bash
CLI_AUDIT_DEBUG=1 uv run python audit.py
```

**Shows:**
- Suppressed exceptions
- Cache read/write operations
- Classification decisions

### Debug Output During Collection

```bash
CLI_AUDIT_DEBUG=1 uv run python audit.py --update --verbose
```

### Isolate Single Tool

```bash
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py problematic-tool 2>&1 | tee debug.log
```

### Check Cache State

```bash
# View upstream versions
jq '.' upstream_versions.json

# View local state
jq '.' local_state.json
```

## Git Workflow Best Practices

### Branch Naming

- Features: `feature/add-new-tool`
- Fixes: `fix/version-detection-bug`
- Refactors: `refactor/simplify-classification`
- Docs: `docs/improve-api-reference`

### Commit Messages

Follow Conventional Commits:

```
feat(tools): add support for tool-name
fix(github): handle rate limiting gracefully
refactor(cache): extract hints management to separate module
docs(api): add examples for get_latest() function
test(smoke): verify JSON output schema
```

**Format:** `type(scope): description`

**Types:** feat, fix, refactor, docs, test, chore

### Pre-Commit Checklist

- [ ] Code passes `pyflakes` lint
- [ ] Manual test passed for affected tools
- [ ] Smoke test passed (`bash scripts/test_smoke.sh`)
- [ ] Updated `upstream_versions.json` if adding tools
- [ ] Updated documentation if changing behavior
- [ ] Commit message follows conventions

## Performance Optimization

### Reduce Network Calls

1. **Use Hints:** Let successful methods guide future runs
2. **Offline Mode:** `CLI_AUDIT_OFFLINE=1` for local-only audits

### Improve Concurrency

```bash
# Increase workers (default: 16)
CLI_AUDIT_MAX_WORKERS=32 uv run python audit.py --update

# Note: Diminishing returns above ~20 workers
```

### Reduce Timeout

```bash
# Faster but may miss slow tools
CLI_AUDIT_TIMEOUT_SECONDS=1 uv run python audit.py --update
```

## Common Pitfalls

### ❌ Unhandled Exceptions in Workers

```python
# WRONG - Exception propagates
def audit_tool(tool):
    version = subprocess.check_output(...)  # May raise
```

```python
# CORRECT - Graceful handling
def audit_tool(tool):
    try:
        version = subprocess.check_output(...)
    except Exception:
        version = ""  # Continue audit
```

### ❌ Non-Atomic File Writes

```python
# WRONG - Can corrupt on crash
with open("cache.json", "w") as f:
    json.dump(data, f)
```

```python
# CORRECT - Atomic replace
_atomic_write_json("cache.json", data)
```

### ❌ Blocking I/O in Worker

```python
# WRONG - Blocks other workers
def audit_tool(tool):
    time.sleep(10)  # Long-running operation
```

```python
# CORRECT - Respect timeout
def audit_tool(tool):
    return run_with_timeout([...], timeout=3)
```

## Getting Help

- **Documentation:** Check docs/INDEX.md for comprehensive guides
- **Issues:** Search existing issues on GitHub
- **Discussions:** Start a discussion for questions
- **Code Review:** Request review from maintainers on PRs

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Study [API_REFERENCE.md](API_REFERENCE.md) for function details
- Explore [TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md) for tool catalog
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

---

**Thank you for contributing to AI CLI Preparation!**
