# Migration Guide: v1.x → v2.0 Modular Architecture

**Last Updated:** 2025-11-03
**Target Audience:** Existing users, integrators, contributors

## Overview

Version 2.0 represents a major architectural evolution from a 3,387-line monolithic `cli_audit.py` to a modular design with:
- **18 specialized Python modules** (6,608 total lines)
- **73 JSON tool catalog entries**
- **New entry point:** `audit.py` (50 lines)
- **Backward-compatible API** via `__init__.py` exports

**Good News:** Most integrations will continue to work without changes thanks to comprehensive API exports in `cli_audit/__init__.py`.

## What Changed

### Entry Point

**Before (v1.x):**
```bash
python3 cli_audit.py
CLI_AUDIT_COLLECT=1 python3 cli_audit.py
```

**After (v2.0):**
```bash
python3 audit.py
CLI_AUDIT_COLLECT=1 python3 audit.py --update
```

**Makefile Commands (Unchanged):**
```bash
make audit        # Still works
make update       # Still works
make upgrade      # Still works
```

### Module Structure

**Before (v1.x):**
- Single file: `cli_audit.py` (3,387 lines)
- All functions in one namespace

**After (v2.0):**
```
audit.py (entry point, 50 lines)
cli_audit/
├── __init__.py          # Public API exports
├── catalog.py           # JSON catalog management
├── collectors.py        # Upstream version collection
├── detection.py         # Tool installation detection
├── render.py            # Output formatting
├── snapshot.py          # Snapshot management
├── tools.py             # Tool definitions
├── common.py            # Shared types
├── config.py            # Configuration
├── environment.py       # OS/arch detection
├── package_managers.py  # Package manager abstractions
├── installer.py         # Installation logic
├── install_plan.py      # Planning & dependencies
├── bulk.py              # Bulk operations
├── upgrade.py           # Upgrade workflows
├── breaking_changes.py  # Semver analysis
├── reconcile.py         # Duplicate cleanup
└── logging_config.py    # Logging setup
```

### Tool Definitions

**Before (v1.x):**
- Tools defined in Python code (TOOLS tuple)
- Required code changes to add tools

**After (v2.0):**
- Tools defined in `catalog/*.json` files (73 entries)
- Add tools by creating JSON files (no code changes)
- Python TOOLS tuple remains as fallback

### File Locations

**Unchanged:**
- `latest_versions.json` (cache)
- `tools_snapshot.json` (snapshot)
- `smart_column.py` (formatting)
- `Makefile` and `Makefile.d/`
- `scripts/` directory
- `tests/` directory

**New:**
- `catalog/` directory (73 JSON files)
- `cli_audit/` package (18 Python modules)
- `audit.py` entry point

**Renamed:**
- `cli_audit.py` → `cli_audit_legacy.py` (backup, may be removed later)

## API Compatibility

### Backward-Compatible Imports

All Phase 1 and Phase 2 APIs are re-exported through `cli_audit/__init__.py` for compatibility:

**These imports still work:**
```python
# Phase 1: Detection & Auditing
from cli_audit import Tool, all_tools, filter_tools
from cli_audit import audit_tool_installation, extract_version_number
from cli_audit import load_snapshot, write_snapshot, render_from_snapshot
from cli_audit import collect_github, collect_pypi, collect_npm, collect_crates
from cli_audit import status_icon, render_table, print_summary

# Phase 2: Installation & Upgrade
from cli_audit import Environment, detect_environment
from cli_audit import Config, load_config
from cli_audit import install_tool, upgrade_tool
from cli_audit import bulk_install, bulk_upgrade, bulk_reconcile
from cli_audit import detect_breaking_changes
```

### New Modular Imports (Recommended)

For new code, import directly from modules:

```python
# Detection & Auditing
from cli_audit.tools import Tool, all_tools, filter_tools
from cli_audit.catalog import ToolCatalog, ToolCatalogEntry
from cli_audit.detection import audit_tool_installation
from cli_audit.collectors import collect_github, collect_pypi
from cli_audit.snapshot import load_snapshot, write_snapshot
from cli_audit.render import render_table, status_icon

# Foundation
from cli_audit.environment import Environment, detect_environment
from cli_audit.config import Config, load_config
from cli_audit.common import InstallResult, AuditResult

# Installation
from cli_audit.installer import install_tool
from cli_audit.upgrade import upgrade_tool
from cli_audit.bulk import bulk_install, bulk_upgrade
from cli_audit.reconcile import reconcile_installations
```

## Breaking Changes

### 1. Direct Python Invocation

**Before:**
```bash
python3 cli_audit.py --only ripgrep
```

**After:**
```bash
python3 audit.py --only ripgrep
```

**Migration:**
- Update scripts/automation to use `audit.py`
- Or continue using `make audit` which abstracts the entry point

### 2. Location References in Documentation

**Before:**
```python
# Location: cli_audit.py:729
@dataclass(frozen=True)
class Tool:
    ...
```

**After:**
```python
# Location: cli_audit/tools.py:14
@dataclass(frozen=True)
class Tool:
    ...
```

**Migration:**
- Update documentation/comments referencing line numbers
- Use module paths instead: `cli_audit.tools.Tool`

### 3. Internal Function Access

**Before:**
```python
from cli_audit import _debug_log, _validate_cache  # Private functions
```

**After:**
```python
# Private functions NOT exported in __init__.py
# Access directly from modules if absolutely necessary:
from cli_audit.logging_config import _debug_log
from cli_audit.snapshot import _validate_snapshot
```

**Migration:**
- Avoid using private functions (prefixed with `_`)
- Use public APIs where possible
- If unavoidable, import from specific modules

### 4. Tool Catalog Access

**Before:**
```python
# Tools hardcoded in cli_audit.py
from cli_audit import TOOLS
tool = TOOLS[0]
```

**After:**
```python
# Option 1: Use tools.py fallback (maintains compatibility)
from cli_audit.tools import TOOLS
tool = TOOLS[0]

# Option 2: Use new catalog system (recommended)
from cli_audit.catalog import ToolCatalog
catalog = ToolCatalog()
entry = catalog.get("ripgrep")
```

**Migration:**
- `TOOLS` tuple still exists in `cli_audit.tools` for compatibility
- New code should use `ToolCatalog` for accessing tool metadata

## Migration Steps by Use Case

### Use Case 1: Command-Line User

**No Action Required** ✅

Makefile commands abstract the entry point:
```bash
make audit      # Uses audit.py internally
make update     # Uses audit.py internally
make upgrade    # Uses scripts/guide.sh
```

### Use Case 2: CI/CD Integration

**Check and Update Entry Point:**

**Before:**
```yaml
# GitHub Actions
- run: python3 cli_audit.py --only python-core
```

**After:**
```yaml
# GitHub Actions
- run: python3 audit.py --only python-core
# OR use Makefile abstraction:
- run: make audit-python-core
```

**GitLab CI:**
```yaml
audit:
  script:
    - python3 audit.py --only agent-core
    # OR: make audit-agent-core
```

### Use Case 3: Python API Integration

**Option A: No Changes (Backward Compatible)**

```python
# This still works due to __init__.py exports
from cli_audit import audit_tool_installation, all_tools
from cli_audit import load_snapshot, render_table

tools = all_tools()
snapshot = load_snapshot()
render_table(snapshot)
```

**Option B: Update to Modular Imports (Recommended)**

```python
# New modular approach
from cli_audit.tools import all_tools, filter_tools
from cli_audit.snapshot import load_snapshot, render_from_snapshot
from cli_audit.render import render_table, print_summary

tools = all_tools()
snapshot = load_snapshot()
render_table(snapshot)
```

### Use Case 4: Adding New Tools

**Before (v1.x): Edit Python Code**

```python
# Edit cli_audit.py, add to TOOLS tuple:
Tool("my-tool", ("my-tool",), "gh", ("owner", "repo"), "category", "hint")
```

**After (v2.0): Create JSON File**

```bash
# Create catalog/my-tool.json:
{
  "name": "my-tool",
  "install_method": "github_release_binary",
  "description": "My amazing tool",
  "homepage": "https://github.com/owner/my-tool",
  "github_repo": "owner/my-tool",
  "binary_name": "my-tool",
  "version_flag": "--version",
  "notes": ""
}
```

**Migration:**
- Tool definitions can be JSON files in `catalog/`
- Python `TOOLS` tuple in `cli_audit.tools` remains as fallback
- See [CATALOG_GUIDE.md](CATALOG_GUIDE.md) for schema details

### Use Case 5: Custom Tool Detection

**Before:**
```python
from cli_audit import find_paths, get_version_line, extract_version_number

paths = find_paths("ripgrep")
version_line = get_version_line(paths[0], ("--version",))
version = extract_version_number(version_line)
```

**After (Same, Backward Compatible):**
```python
# Works unchanged due to __init__.py exports
from cli_audit import find_paths, get_version_line, extract_version_number

# OR use modular imports:
from cli_audit.detection import find_paths, get_version_line, extract_version_number
```

### Use Case 6: Custom Collectors

**Before:**
```python
from cli_audit import collect_github, collect_pypi
tag, version = collect_github("sharkdp", "fd")
```

**After (Backward Compatible):**
```python
# Works unchanged
from cli_audit import collect_github, collect_pypi

# OR modular:
from cli_audit.collectors import collect_github, collect_pypi
```

## Testing Your Migration

### 1. Validate Entry Point

```bash
# Test basic audit
python3 audit.py --only ripgrep

# Test collection
CLI_AUDIT_COLLECT=1 python3 audit.py --update

# Test with Make
make audit
make update
```

### 2. Validate Python Imports

```python
# Test backward-compatible imports
python3 -c "from cli_audit import Tool, all_tools; print(f'Tools: {len(all_tools())}')"

# Test modular imports
python3 -c "from cli_audit.tools import all_tools; print(f'Tools: {len(all_tools())}')"

# Test catalog
python3 -c "from cli_audit.catalog import ToolCatalog; catalog = ToolCatalog(); print(f'Catalog entries: {len(catalog)}')"
```

### 3. Run Test Suite

```bash
# Unit tests
python3 -m pytest tests/test_config.py -v

# Integration tests
python3 -m pytest tests/integration/ -v

# Smoke test
./scripts/test_smoke.sh
```

## Troubleshooting

### Error: `ModuleNotFoundError: No module named 'cli_audit'`

**Cause:** Python path not set correctly

**Solution:**
```bash
export PYTHONPATH=/path/to/ai_cli_preparation:$PYTHONPATH
# OR run from project root
cd /path/to/ai_cli_preparation
python3 audit.py
```

### Error: `FileNotFoundError: catalog directory not found`

**Cause:** Running from wrong directory

**Solution:**
```bash
# Always run from project root
cd /path/to/ai_cli_preparation
python3 audit.py
```

### Error: `ImportError: cannot import name 'audit_tool' from 'cli_audit'`

**Cause:** Function not exported in `__init__.py` (may be private or renamed)

**Solution:**
```python
# Check if function is private (_prefixed)
# Import from specific module:
from cli_audit.detection import audit_tool_installation  # Correct name
```

### Performance Regression

**Cause:** Module loading overhead (minimal, ~10ms)

**Solution:**
- Use snapshot-based workflow: `make update` once, then `make audit` repeatedly
- Performance should be equivalent after initial load

### Catalog Not Loading

**Cause:** catalog/*.json files missing or invalid

**Solution:**
```bash
# Check catalog directory exists
ls -l catalog/

# Validate JSON files
for f in catalog/*.json; do jq . "$f" > /dev/null || echo "Invalid: $f"; done

# Fallback to Python TOOLS tuple automatically used if catalog missing
```

## Rollback Procedure

If you encounter critical issues, you can temporarily revert to the legacy monolith:

### Option 1: Use Legacy File (Temporary)

```bash
# cli_audit_legacy.py is the renamed original
python3 cli_audit_legacy.py
```

### Option 2: Git Revert (Development)

```bash
# Revert to pre-v2.0 commit
git checkout <pre-v2.0-commit>
```

### Option 3: Pin to v1.x (Production)

```bash
# If using pip/package manager
pip install ai-cli-preparation==1.x.x
```

**Note:** Legacy support is temporary. Plan migration to v2.0 modular architecture.

## Benefits of v2.0 Architecture

After migration, you gain:

1. **Maintainability**: Focused modules vs 3,387-line monolith
2. **Extensibility**: Add tools via JSON, not code changes
3. **Testability**: Isolated modules with targeted tests
4. **Performance**: Optimized imports, faster startup
5. **Community**: JSON contributions easier than Python code
6. **Documentation**: Clearer module responsibilities

## Getting Help

**Resources:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Understand modular design
- [CATALOG_GUIDE.md](CATALOG_GUIDE.md) - Work with JSON tool definitions
- [API_REFERENCE.md](API_REFERENCE.md) - Comprehensive API documentation
- [INDEX.md](INDEX.md) - Documentation navigation

**Issues:**
- GitHub Issues: Report migration problems
- Discussions: Ask questions about migration

## Summary

**Minimum Migration Effort:**
- ✅ Makefile commands work unchanged
- ✅ Most Python imports work unchanged (via `__init__.py`)
- ⚠️  Update entry point: `cli_audit.py` → `audit.py` (if direct invocation)
- ⚠️  Update documentation references (line numbers)

**Recommended Migration:**
- Use modular imports for new code
- Adopt JSON catalog for new tools
- Update CI/CD to use `audit.py` or Makefile abstractions
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for deep understanding

**Timeline:**
- **Immediate**: Test with your integration
- **Short-term (days)**: Update entry points in automation
- **Medium-term (weeks)**: Adopt modular imports
- **Long-term (months)**: Contribute JSON catalog entries

Welcome to v2.0! 🎉
