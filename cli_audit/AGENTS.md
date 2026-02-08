<!-- Managed by agent: keep sections & order; edit content, not structure. Last updated: 2026-02-06 -->

# cli_audit/ — Python Package

**Modular architecture** with 21 specialized modules for tool detection, auditing, installation, and upgrade management.

## Overview

The `cli_audit` package provides the core functionality for AI CLI Preparation:

**Phase 1: Detection & Auditing (6 modules)**
- `tools.py` — Tool definitions and metadata
- `catalog.py` — JSON catalog management (79 entries)
- `detection.py` — Installation detection, version extraction, multi-version detection
- `collectors.py` — Upstream version collection (GitHub, PyPI, npm, crates, endoflife.date)
- `snapshot.py` — Snapshot-based caching
- `render.py` — Output formatting and table rendering

**Phase 2: Foundation (5 modules)**
- `common.py` — Shared types (InstallResult, AuditResult, etc.)
- `environment.py` — OS/arch detection, package manager detection
- `config.py` — Configuration management (YAML, user prefs, auto_update)
- `package_managers.py` — Package manager abstractions
- `logging_config.py` — Logging configuration

**Phase 2: Installation & Upgrade (5 modules)**
- `installer.py` — Tool installation with retry/validation
- `install_plan.py` — Installation planning, dependency resolution
- `prerequisites.py` — Prerequisite resolution and dependency chain handling
- `bulk.py` — Parallel bulk operations
- `upgrade.py` — Upgrade workflows

**Phase 2: State Management (2 modules)**
- `local_state.py` — Machine-specific installation state (gitignored)
- `upstream_cache.py` — Upstream version cache (committed baseline)

**Phase 2: Advanced Features (3 modules)**
- `breaking_changes.py` — Semver analysis for breaking changes
- `reconcile.py` — Duplicate installation cleanup
- `__init__.py` — Public API exports (backward compatibility)

## Data model

**2-file data model** (Phase 2.1 consolidation):
```
upstream_versions.json  # Committed - latest available versions (shared baseline)
local_state.json        # Gitignored - machine-specific installation state
```

**User configuration:**
```
~/.config/cli-audit/config.yml  # User preferences (auto_update, tool overrides)
```

**Catalog entries** (79 JSON files in `catalog/`):
- Each tool has `name`, `candidates`, `source_kind`, `source_args`, `category`
- Categories: python, node, go, rust, ruby, php, shell, git, devops, platform, ai, general
- User preferences (auto_update) stored in user config, not catalog

**Multi-version runtimes** (PHP, Python, Node.js, Ruby, Go):
- Catalog entries with `multi_version.enabled: true` support concurrent versions
- Version lifecycle data from [endoflife.date](https://endoflife.date/) API
- Detection via binary patterns (`php8.4`) or version manager dirs (`~/.nvm/versions/node/`)
- See: `collect_endoflife()`, `detect_multi_versions()`

## Setup & environment

**Requirements:**
```bash
# Python 3.10+ required
python3 --version  # 3.10, 3.11, 3.12, 3.14 tested

# No external dependencies for core (stdlib only)
# Optional dev dependencies in pyproject.toml
```

**Development setup:**
```bash
# Optional: Install dev dependencies
pip install -e ".[dev]"

# Or with uv (preferred)
uv pip install -e ".[dev]"

# Enable direnv (if using)
direnv allow
```

## Build & tests

**Linting:**
```bash
# From project root
make lint                    # flake8 (PEP 8, line length 127)
make lint-types              # mypy (optional, when configured)
```

**Testing:**
```bash
# From project root
python3 -m pytest tests/test_config.py -v
python3 -m pytest tests/ -v
./scripts/test_smoke.sh
```

**Module-specific testing:**
```python
# Test specific module imports
python3 -c "from cli_audit.catalog import ToolCatalog; print(f'Catalog: {len(ToolCatalog())} entries')"
python3 -c "from cli_audit.tools import all_tools; print(f'Tools: {len(all_tools())}')"
python3 -c "from cli_audit.detection import audit_tool_installation; print('Detection OK')"
```

## Code style & conventions

**Python style:**
- PEP 8 compliant (line length: 127 characters)
- Type hints required for all public functions
- Modern syntax: `list[str]`, `dict[str, int]`, `str | None`
- Frozen dataclasses for immutable value objects

**Naming:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

**Module organization:**
- Each module has single responsibility
- Avoid circular dependencies
- Import order: stdlib → third-party → local
- Explicit imports preferred (`from x import y`)

**Dataclass patterns:**
```python
# Immutable value objects
@dataclass(frozen=True)
class Tool:
    name: str
    candidates: tuple[str, ...]
    source_kind: str
    source_args: tuple[str, ...]

# Mutable results
@dataclass
class InstallResult:
    success: bool
    message: str
    installed_tools: list[str] = field(default_factory=list)
```

**Error handling:**
- Catch specific exceptions, not bare `except:`
- Fail gracefully with logging
- Use try/except around network, subprocess, file I/O
- Best-effort operations: log and continue

## Security & safety

**API exports:**
- All public APIs exported via `__init__.py`
- Private functions (`_prefixed`) NOT exported
- Maintain backward compatibility for major version

**Input validation:**
- Validate tool names from user input
- Sanitize paths and file operations
- Check JSON schema for catalog entries
- Prevent command injection in subprocess calls

**Subprocess safety:**
```python
# Good: Array-style arguments (prevents shell injection)
subprocess.run(["tool", "--version"], capture_output=True, timeout=3)

# Bad: Shell string (vulnerable to injection)
subprocess.run("tool --version", shell=True)  # NEVER DO THIS
```

**File operations:**
- Atomic writes: write to temp file, then rename
- Lock ordering: MANUAL_LOCK → HINTS_LOCK (prevent deadlock)
- Validate JSON before loading

## PR/commit checklist

Before committing changes to `cli_audit/`:

- [ ] **Linting:** `make lint` passes (no flake8 errors)
- [ ] **Type hints:** Added for new public functions
- [ ] **Imports:** Module imports work: `from cli_audit.module import func`
- [ ] **API exports:** Public functions added to `__init__.py` if needed
- [ ] **Tests:** Existing tests pass: `pytest tests/`
- [ ] **Smoke test:** `./scripts/test_smoke.sh` passes
- [ ] **Documentation:** Docstrings added for complex functions
- [ ] **Backward compatibility:** API changes don't break existing code

**Module-specific checks:**
- **catalog.py:** JSON validation, ToolCatalog loads correctly
- **detection.py:** Version extraction handles edge cases
- **collectors.py:** HTTP retries work, rate limiting respected
- **snapshot.py:** Atomic writes, lock ordering correct
- **installer.py:** Subprocess safety, no shell=True

## Good vs. bad examples

**Good: Modular imports**
```python
# Import from specific modules (v2.0 style)
from cli_audit.catalog import ToolCatalog, ToolCatalogEntry
from cli_audit.detection import audit_tool_installation
from cli_audit.collectors import collect_github
from cli_audit.snapshot import load_snapshot, write_snapshot
```

**Good: Backward-compatible imports**
```python
# Works for existing code (via __init__.py exports)
from cli_audit import Tool, all_tools, filter_tools
from cli_audit import audit_tool_installation, collect_github
```

**Bad: Private function access**
```python
# Don't import private functions (not in __init__.py)
from cli_audit.snapshot import _validate_snapshot  # ❌ Private
from cli_audit.logging_config import _debug_log     # ❌ Private
```

**Good: Frozen dataclasses for immutability**
```python
@dataclass(frozen=True)
class Tool:
    name: str
    candidates: tuple[str, ...]  # Immutable
```

**Bad: Mutable defaults**
```python
@dataclass
class BadTool:
    name: str
    candidates: list[str] = []  # ❌ Shared mutable default!

# Correct:
@dataclass
class GoodTool:
    name: str
    candidates: list[str] = field(default_factory=list)  # ✅
```

**Good: Subprocess safety**
```python
# Safe: Array-style arguments
result = subprocess.run(
    ["git", "--version"],
    capture_output=True,
    timeout=3,
    text=True
)
```

**Bad: Shell injection vulnerability**
```python
# Vulnerable: shell=True
tool_name = get_user_input()  # Could be "git; rm -rf /"
subprocess.run(f"{tool_name} --version", shell=True)  # ❌ NEVER
```

**Good: Type hints with modern syntax**
```python
def collect_versions(tools: list[Tool]) -> dict[str, str | None]:
    """Collect versions for tools."""
    versions: dict[str, str | None] = {}
    for tool in tools:
        versions[tool.name] = get_version(tool)
    return versions
```

**Good: Error handling**
```python
try:
    data = json.load(f)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON: {e}")
    return None  # Graceful degradation
```

## When stuck

**Resources:**
- API Reference: `docs/API_REFERENCE.md` — Complete module API
- Migration Guide: `docs/MIGRATION_GUIDE.md` — v1.x → v2.0 transition
- Catalog Guide: `docs/CATALOG_GUIDE.md` — JSON catalog system
- Architecture: `docs/ARCHITECTURE.md` — Modular design patterns

**Debugging:**
```bash
# Enable debug logging
CLI_AUDIT_DEBUG=1 python3 audit.py ripgrep

# Test specific module
python3 -c "from cli_audit.catalog import ToolCatalog; c = ToolCatalog(); print(len(c))"

# Validate JSON catalog
jq . catalog/my-tool.json

# Check imports
python3 -c "from cli_audit import Tool; print('OK')"
```

**Common issues:**
- **ModuleNotFoundError:** Run from project root, ensure PYTHONPATH set
- **Catalog not loading:** Check `catalog/` directory exists, validate JSON syntax
- **Import errors:** Check `__init__.py` exports, use modular imports
- **Type errors:** Add type hints, run `make lint-types`

## House rules

**Module-specific overrides:**

1. **Line length:** 127 characters (not 80)
   - Configured in `.flake8`, `pyproject.toml`, `.editorconfig`

2. **Import order:** Enforced by isort (optional)
   - stdlib → third-party → local modules
   - Separated by blank lines

3. **Docstrings:** Minimal unless complex
   - Required for public API functions
   - Google-style format preferred
   - Focus on inline comments for clarity

4. **Private functions:** Not exported in `__init__.py`
   - Use `_prefix` for internal-only
   - Double `__prefix` for truly private (rare)

5. **Backward compatibility:** Maintain for major version
   - All Phase 1 + Phase 2 APIs exported
   - Breaking changes require major version bump
