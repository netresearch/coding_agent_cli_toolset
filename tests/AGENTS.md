<!-- Managed by agent: keep sections & order; edit content, not structure. Last updated: 2026-01-16 -->

# tests/ — Test Suite

**Comprehensive testing** with unit, integration, and E2E tests for the modular cli_audit package.

## Overview

The test suite validates all 20 modules across Phase 1 (Detection & Auditing) and Phase 2 (Installation & Upgrade Management).

**Test organization:**
```
tests/
├── test_bulk.py                  # Bulk operations
├── test_catalog_and_collectors.py # Catalog and version collectors
├── test_config.py                # Configuration management
├── test_environment.py           # Environment detection
├── test_install_plan.py          # Planning & dependencies
├── test_installer.py             # Installation logic
├── test_local_state.py           # Local state management
├── test_logging.py               # Logging configuration
├── test_package_managers.py      # Package manager abstractions
├── test_reconcile.py             # Duplicate cleanup
├── test_upgrade.py               # Upgrade workflows
├── test_upstream_cache.py        # Upstream cache management
└── integration/
    └── test_e2e_install.py       # End-to-end installation tests
```

**Test coverage:**
- 12 unit test files covering all 20 modules
- 1 integration test directory
- Fixtures for mocking external services

## Setup & environment

**Requirements:**
```bash
# Python 3.14+ with uv package manager
python3 --version  # 3.14 required
uv --version       # uv required

# Sync all dependencies (including dev)
uv sync --extra dev
```

**Test dependencies (from pyproject.toml):**
- pytest — Test framework
- pytest-cov — Coverage reporting
- pytest-mock — Mocking utilities
- pytest-xdist — Parallel test execution

**Test environment variables:**
```bash
CLI_AUDIT_DEBUG=1           # Enable debug logging in tests
CLI_AUDIT_OFFLINE=1         # Force offline mode (no network calls)
CLI_AUDIT_TIMEOUT_SECONDS=1 # Fast timeout for tests
```

## Build & tests

**Run all tests (use uv run):**
```bash
# From project root - ALWAYS use uv run
uv run python -m pytest

# Verbose output
uv run python -m pytest -v

# With coverage
uv run python -m pytest --cov=cli_audit --cov-report=html

# Parallel execution (fast)
uv run python -m pytest -n auto
```

**Run specific test files:**
```bash
# Single test file
uv run python -m pytest tests/test_config.py -v

# Single test class
uv run python -m pytest tests/test_config.py::TestToolConfig -v

# Single test function
uv run python -m pytest tests/test_config.py::TestToolConfig::test_tool_config_defaults -v
```

**Run integration tests:**
```bash
uv run python -m pytest tests/integration/ -v
```

**Smoke test (quick validation):**
```bash
./scripts/test_smoke.sh
```

**Filter tests by marker:**
```bash
# Run only slow tests
uv run python -m pytest -m slow

# Skip slow tests
uv run python -m pytest -m "not slow"

# Run only unit tests
uv run python -m pytest -m unit
```

## Code style & conventions

**Test naming:**
- Test files: `test_<module>.py`
- Test classes: `Test<Component>`
- Test functions: `test_<behavior>`
- Use descriptive names: `test_config_invalid_timeout_too_low`

**Test structure (Arrange-Act-Assert):**
```python
def test_tool_config_defaults():
    # Arrange
    config = ToolConfig()

    # Act
    result = config.get_install_method()

    # Assert
    assert result == "auto"
```

**Fixture patterns:**
```python
import pytest

@pytest.fixture
def sample_tool():
    """Provide a sample Tool instance for tests."""
    return Tool("ripgrep", ("rg",), "gh", ("BurntSushi", "ripgrep"))

def test_tool_detection(sample_tool):
    """Test tool detection with fixture."""
    assert sample_tool.name == "ripgrep"
```

**Mocking external calls:**
```python
from unittest.mock import patch, MagicMock

@patch('cli_audit.collectors.collect_github')
def test_version_collection(mock_collect):
    """Mock GitHub API calls."""
    mock_collect.return_value = ("v1.2.3", "1.2.3")

    tag, version = collect_github("owner", "repo")
    assert version == "1.2.3"
    mock_collect.assert_called_once()
```

## Security & safety

**Test isolation:**
- Tests should not depend on each other
- Use fixtures for shared setup
- Clean up resources (files, processes) in teardown
- Mock external services (no real API calls in unit tests)

**File system safety:**
```python
import tempfile
from pathlib import Path

def test_file_operations(tmp_path: Path):
    """Use pytest tmp_path fixture for safe file operations."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"key": "value"}')

    # Test file operations
    assert test_file.exists()
    # No cleanup needed, tmp_path auto-cleaned
```

**Network isolation:**
```python
# Mock network calls in unit tests
@patch('urllib.request.urlopen')
def test_http_fetch(mock_urlopen):
    """No real network calls in unit tests."""
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"version": "1.2.3"}'
    mock_urlopen.return_value = mock_response

    # Test proceeds without real network
```

**Subprocess safety:**
```python
@patch('subprocess.run')
def test_tool_execution(mock_run):
    """Mock subprocess calls."""
    mock_run.return_value = MagicMock(
        stdout="ripgrep 15.1.0",
        returncode=0
    )

    # Test without executing real commands
```

## PR/commit checklist

Before committing test changes:

- [ ] **All tests pass:** `uv run python -m pytest` succeeds
- [ ] **No skipped tests:** Fix or document skipped tests
- [ ] **Coverage maintained:** New code has corresponding tests
- [ ] **Isolation:** Tests don't depend on execution order
- [ ] **Fast execution:** Unit tests complete in <5s total
- [ ] **Descriptive names:** Test names clearly describe what's tested
- [ ] **Mocking:** External services/network mocked appropriately
- [ ] **Cleanup:** Temporary files/resources cleaned up
- [ ] **Documentation:** Complex test logic has comments

**Integration test checklist:**
- [ ] E2E tests pass: `uv run python -m pytest tests/integration/ -v`
- [ ] Real environment tested: Not just mocks
- [ ] Idempotent: Can run multiple times safely
- [ ] Reasonable timeout: Integration tests <30s each

## Good vs. bad examples

**Good: Descriptive test names**
```python
def test_config_invalid_timeout_too_low():
    """Test that timeout < 1 raises ValueError."""
    with pytest.raises(ValueError, match="timeout must be >= 1"):
        Preferences(timeout_seconds=0)
```

**Bad: Vague test names**
```python
def test_config():  # ❌ What about config?
    assert True
```

**Good: Arrange-Act-Assert structure**
```python
def test_tool_catalog_get():
    # Arrange
    catalog = ToolCatalog()

    # Act
    entry = catalog.get("ripgrep")

    # Assert
    assert entry is not None
    assert entry.name == "ripgrep"
```

**Good: Use fixtures for shared setup**
```python
@pytest.fixture
def catalog():
    """Provide ToolCatalog instance."""
    return ToolCatalog()

def test_catalog_has(catalog):
    assert catalog.has("ripgrep")

def test_catalog_get(catalog):
    assert catalog.get("ripgrep") is not None
```

**Bad: Repeated setup in each test**
```python
def test_catalog_has():
    catalog = ToolCatalog()  # ❌ Repeated
    assert catalog.has("ripgrep")

def test_catalog_get():
    catalog = ToolCatalog()  # ❌ Repeated
    assert catalog.get("ripgrep") is not None
```

**Good: Mock external dependencies**
```python
@patch('cli_audit.collectors.collect_github')
def test_github_rate_limit(mock_collect):
    mock_collect.side_effect = Exception("Rate limit exceeded")

    with pytest.raises(Exception, match="Rate limit"):
        collect_github("owner", "repo")
```

**Bad: Real API calls in unit tests**
```python
def test_github_collection():
    # ❌ Real network call, slow and flaky
    tag, version = collect_github("owner", "repo")
    assert version
```

**Good: Parametrized tests for multiple cases**
```python
@pytest.mark.parametrize("timeout,expected", [
    (1, 1),
    (5, 5),
    (100, 100),
])
def test_timeout_valid_values(timeout, expected):
    prefs = Preferences(timeout_seconds=timeout)
    assert prefs.timeout_seconds == expected
```

**Good: Use tmp_path for file operations**
```python
def test_snapshot_write(tmp_path):
    snapshot_file = tmp_path / "test_snapshot.json"
    data = {"tools": []}

    write_snapshot(data, str(snapshot_file))

    assert snapshot_file.exists()
    loaded = json.loads(snapshot_file.read_text())
    assert loaded == data
```

## When stuck

**Resources:**
- Testing Guide: `docs/TESTING.md` — Comprehensive testing strategies
- Developer Guide: `docs/DEVELOPER_GUIDE.md` — Contribution guidelines
- Error Catalog: `docs/ERROR_CATALOG.md` — Common error patterns

**Debugging failing tests:**
```bash
# Run with verbose output
uv run python -m pytest tests/test_config.py -vv

# Show print statements
uv run python -m pytest tests/test_config.py -s

# Stop on first failure
uv run python -m pytest -x

# Enter debugger on failure
uv run python -m pytest --pdb

# Show last failed tests
uv run python -m pytest --lf
```

**Common issues:**
- **Import errors:** Run `uv sync --extra dev` first, ensure uv run is used
- **Fixture not found:** Check fixture scope and location
- **Test order dependency:** Tests should be independent, fix test isolation
- **Slow tests:** Mock external calls, use tmp_path, check for real network/subprocess
- **Flaky tests:** Usually timing issues, mock time-dependent operations
- **VIRTUAL_ENV warning:** Run `deactivate` first if another venv is active

**Test coverage:**
```bash
# Generate coverage report
uv run python -m pytest --cov=cli_audit --cov-report=html

# View report
open htmlcov/index.html

# Show missing lines
uv run python -m pytest --cov=cli_audit --cov-report=term-missing
```

## House rules

**Test-specific overrides:**

1. **Test discovery:** pytest auto-discovers `test_*.py` files
   - All test files must start with `test_`
   - All test functions must start with `test_`

2. **Markers:** Use pytest markers for test categorization
   ```python
   @pytest.mark.slow
   def test_full_integration():
       pass

   @pytest.mark.unit
   def test_config_defaults():
       pass
   ```

3. **Fixtures:** Prefer fixtures over setup/teardown
   - Use `conftest.py` for shared fixtures
   - Use `tmp_path` for file operations
   - Use `monkeypatch` for environment variables

4. **Coverage target:** Aim for ≥80% coverage
   - New modules should have ≥80% test coverage
   - Critical paths (detection, installation) should have ≥90%
   - 100% not required, focus on meaningful tests

5. **Test speed:** Keep unit tests fast
   - Unit tests: <5s total
   - Integration tests: <30s total
   - Mock slow operations (network, subprocess)
