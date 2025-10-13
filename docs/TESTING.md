# Testing Guide

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-13

Complete testing guide for AI CLI Preparation contributors, covering unit tests, integration tests, coverage requirements, and testing best practices.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Coverage Requirements](#coverage-requirements)
- [Mocking and Fixtures](#mocking-and-fixtures)
- [Testing Patterns](#testing-patterns)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Install development dependencies
pip install -e ".[dev]"
# OR
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=cli_audit --cov-report=term --cov-report=html

# Run specific module tests
pytest tests/test_config.py

# Run tests in parallel
pytest -n auto

# Watch mode (requires pytest-watch)
ptw
```

---

## Test Organization

### Directory Structure

```
tests/
├── __init__.py                # Test package initialization
├── fixtures/                  # Test fixtures and sample data
│   ├── config_valid.yml      # Valid config file
│   ├── config_minimal.yml    # Minimal config
│   ├── config_invalid_*.yml  # Invalid configs for error testing
│   └── ...
├── integration/               # End-to-end integration tests
│   └── test_e2e_install.py   # E2E installation workflow
├── test_config.py            # Configuration parsing tests
├── test_environment.py       # Environment detection tests
├── test_installer.py         # Single-tool installation tests
├── test_bulk.py              # Bulk operations tests
├── test_upgrade.py           # Upgrade management tests
├── test_reconcile.py         # Reconciliation tests
├── test_package_managers.py  # Package manager selection tests
├── test_install_plan.py      # Installation plan generation tests
└── test_logging.py           # Logging framework tests
```

### Test Types

**Unit Tests** (tests/*.py)
- Test individual functions and classes in isolation
- Mock external dependencies (network, filesystem, subprocess)
- Fast execution (<1s per module)
- Target coverage: 80%+

**Integration Tests** (tests/integration/*.py)
- Test complete workflows end-to-end
- May interact with real package managers (in isolated environments)
- Slower execution (5-30s)
- Target coverage: Key workflows

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Very verbose (show test function names)
pytest -vv

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### Running Specific Tests

```bash
# Single test file
pytest tests/test_config.py

# Single test class
pytest tests/test_config.py::TestToolConfig

# Single test method
pytest tests/test_config.py::TestToolConfig::test_tool_config_defaults

# Pattern matching
pytest -k "test_config"
pytest -k "test_tool_config_defaults or test_preferences_defaults"
```

### Coverage Reporting

```bash
# Terminal report
pytest --cov=cli_audit --cov-report=term

# HTML report (opens in browser)
pytest --cov=cli_audit --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Missing lines report
pytest --cov=cli_audit --cov-report=term-missing

# Multiple formats
pytest --cov=cli_audit --cov-report=term --cov-report=html --cov-report=xml

# Minimum coverage threshold (fail if below)
pytest --cov=cli_audit --cov-fail-under=80
```

### Parallel Execution

```bash
# Auto-detect CPU count
pytest -n auto

# Specific number of workers
pytest -n 4

# Parallel with coverage (requires pytest-cov)
pytest -n auto --cov=cli_audit
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run tests with specific marker
pytest -m network  # Tests requiring network
pytest -m subprocess  # Tests spawning processes
```

---

## Writing Tests

### Test Structure

```python
"""
Tests for <module_name>.

Target coverage: 85%+
"""

import pytest
from unittest.mock import patch, MagicMock

from cli_audit.<module> import function_to_test


class TestFunctionName:
    """Tests for function_name function."""

    def test_basic_case(self):
        """Test basic functionality with valid input."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case handling."""
        result = function_to_test("")
        assert result is None

    def test_error_handling(self):
        """Test that errors are raised correctly."""
        with pytest.raises(ValueError, match="Invalid input"):
            function_to_test(None)
```

### Naming Conventions

**Test Classes:**
- `TestFunctionName` - For testing functions
- `TestClassName` - For testing classes
- Group related tests in same class

**Test Methods:**
- `test_<feature>_<scenario>` - Descriptive names
- `test_function_with_valid_input`
- `test_function_with_empty_string`
- `test_function_raises_error_on_none`

**Good Examples:**
```python
def test_install_python_tool_with_pipx()
def test_config_merge_overrides_lower_priority()
def test_environment_detect_ci_with_github_actions()
```

**Bad Examples:**
```python
def test_1()  # Too vague
def test_install()  # Not specific enough
def test_function()  # Missing scenario
```

### Test Documentation

```python
def test_install_tool_with_retry_logic(self):
    """
    Test that install_tool retries on transient failures.

    Scenario:
    - Network failure on first attempt
    - Success on second attempt
    - Verify retry count and backoff delay
    """
    # Test implementation
```

### Assertions

```python
# Basic assertions
assert result == expected
assert result is not None
assert result in [1, 2, 3]
assert len(items) == 5
assert "substring" in text

# Pytest assertions (more informative failures)
assert result == expected, "Custom failure message"

# Approximate comparisons
assert result == pytest.approx(3.14, rel=0.01)

# Exception assertions
with pytest.raises(ValueError):
    function_that_raises()

with pytest.raises(ValueError, match="specific message"):
    function_that_raises()

# Warning assertions
with pytest.warns(UserWarning):
    function_that_warns()
```

---

## Coverage Requirements

### Target Coverage

| Module | Target | Notes |
|--------|--------|-------|
| `config.py` | 85%+ | Configuration is critical |
| `environment.py` | 90%+ | Well-tested, few edge cases |
| `installer.py` | 85%+ | Complex retry logic |
| `bulk.py` | 80%+ | Parallel execution complexity |
| `upgrade.py` | 85%+ | Breaking change detection |
| `reconcile.py` | 80%+ | Multi-installation handling |
| `package_managers.py` | 85%+ | PM selection logic |
| `install_plan.py` | 85%+ | Plan generation |
| `breaking_changes.py` | 90%+ | Policy enforcement |
| `logging_config.py` | 80%+ | Logging setup |
| `common.py` | 85%+ | Utility functions |

### Excluded from Coverage

Lines excluded via `# pragma: no cover`:
- Abstract methods
- `if __name__ == "__main__":`
- Type checking blocks (`if TYPE_CHECKING:`)
- Debug-only code paths
- `__repr__` methods (unless critical)

```python
def debug_only_function():  # pragma: no cover
    """Only used for debugging, not tested."""
    pass
```

### Checking Coverage

```bash
# Overall coverage
pytest --cov=cli_audit --cov-report=term

# Per-module coverage
pytest --cov=cli_audit.config --cov-report=term

# Find untested code
pytest --cov=cli_audit --cov-report=term-missing | grep -v "100%"

# Coverage badge (for README)
coverage-badge -o coverage.svg -f
```

---

## Mocking and Fixtures

### unittest.mock Patterns

```python
from unittest.mock import patch, MagicMock, mock_open

# Mock function return value
@patch('cli_audit.installer.subprocess.run')
def test_install_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Success")
    result = install_tool(...)
    assert result.success

# Mock multiple calls
mock_run.side_effect = [
    MagicMock(returncode=1),  # First call fails
    MagicMock(returncode=0),  # Second succeeds
]

# Mock environment variables
@patch.dict(os.environ, {"CI": "true"}, clear=True)
def test_detect_ci():
    env = detect_environment()
    assert env.mode == "ci"

# Mock file operations
@patch("builtins.open", mock_open(read_data="version: 1"))
def test_read_config():
    config = load_config("config.yml")
    assert config.version == 1

# Mock network requests
@patch('urllib.request.urlopen')
def test_fetch_version(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"version": "1.2.3"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    version = fetch_latest_version("tool")
    assert version == "1.2.3"
```

### pytest Fixtures

```python
import pytest

# Simple fixture
@pytest.fixture
def sample_config():
    """Provide sample configuration for tests."""
    return Config(
        environment_mode="workstation",
        tools={"python": ToolConfig(version="3.12.*")},
    )

def test_with_fixture(sample_config):
    assert sample_config.environment_mode == "workstation"

# Fixture with teardown
@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file."""
    config_file = tmp_path / "config.yml"
    config_file.write_text("version: 1")
    yield str(config_file)
    # Cleanup happens automatically with tmp_path

# Parametrized fixture
@pytest.fixture(params=["ci", "server", "workstation"])
def environment_mode(request):
    """Provide different environment modes."""
    return request.param

def test_modes(environment_mode):
    # Runs 3 times with different modes
    env = detect_environment(override=environment_mode)
    assert env.mode == environment_mode

# Module-scoped fixture (setup once per module)
@pytest.fixture(scope="module")
def expensive_setup():
    """Setup that's expensive to create."""
    data = load_large_dataset()
    yield data
    cleanup(data)
```

### Fixture Location

**conftest.py** (shared fixtures):
```python
# tests/conftest.py
import pytest

@pytest.fixture
def mock_network():
    """Mock network calls for all tests."""
    with patch('urllib.request.urlopen') as mock:
        yield mock

@pytest.fixture(autouse=True)
def reset_caches():
    """Auto-reset caches before each test."""
    from cli_audit import reconcile, upgrade
    reconcile.clear_detection_cache()
    upgrade.clear_version_cache()
```

---

## Testing Patterns

### Testing Configuration

```python
class TestConfigLoading:
    """Test configuration loading and validation."""

    def test_load_valid_config(self, tmp_path):
        """Test loading valid YAML configuration."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
version: 1
environment:
  mode: workstation
""")

        config = load_config_file(str(config_file))
        assert config is not None
        assert config.environment_mode == "workstation"

    def test_config_validation_error(self):
        """Test that invalid config raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported config version"):
            Config(version=999)
```

### Testing Environment Detection

```python
class TestEnvironmentDetection:
    """Test environment detection logic."""

    @patch.dict(os.environ, {"CI": "true"}, clear=True)
    def test_detect_ci(self):
        """Test CI detection with CI environment variable."""
        env = detect_environment()
        assert env.mode == "ci"
        assert env.confidence >= 0.9
        assert any("CI" in ind for ind in env.indicators)

    @patch("cli_audit.environment.get_active_user_count", return_value=5)
    @patch("cli_audit.environment.get_system_uptime_days", return_value=60)
    def test_detect_server(self, mock_uptime, mock_users):
        """Test server detection with mocked system info."""
        env = detect_environment()
        assert env.mode == "server"
```

### Testing Installation

```python
class TestInstaller:
    """Test installation logic."""

    @patch('subprocess.run')
    def test_install_success(self, mock_run):
        """Test successful installation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Successfully installed"
        )

        result = install_tool(
            tool_name="ripgrep",
            package_name="ripgrep",
            target_version="latest",
            config=Config(),
            env=Environment(mode="workstation", confidence=1.0),
            language="rust",
        )

        assert result.success
        assert result.tool_name == "ripgrep"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_install_retry_on_failure(self, mock_run):
        """Test retry logic on transient failures."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # First attempt fails
            MagicMock(returncode=0),  # Second succeeds
        ]

        result = install_tool(...)
        assert result.success
        assert mock_run.call_count == 2
```

### Testing Bulk Operations

```python
class TestBulkOperations:
    """Test bulk installation operations."""

    @patch('cli_audit.bulk.install_tool')
    def test_bulk_install_parallel(self, mock_install):
        """Test parallel bulk installation."""
        mock_install.return_value = InstallResult(
            tool_name="test",
            success=True,
            installed_version="1.0.0",
            package_manager_used="cargo",
            steps_completed=(),
            duration_seconds=1.0,
        )

        result = bulk_install(
            mode="explicit",
            tool_names=["tool1", "tool2", "tool3"],
            config=Config(),
            env=Environment(mode="workstation", confidence=1.0),
            max_workers=3,
        )

        assert len(result.successes) == 3
        assert mock_install.call_count == 3
```

### Testing Error Handling

```python
class TestErrorHandling:
    """Test error handling and recovery."""

    def test_invalid_version_format(self):
        """Test error on invalid version format."""
        with pytest.raises(ValueError, match="Invalid version"):
            validate_version("not-a-version")

    def test_network_timeout(self):
        """Test timeout handling."""
        with patch('urllib.request.urlopen') as mock:
            mock.side_effect = urllib.error.URLError("Timeout")

            result = fetch_latest_version("tool", timeout=1)
            assert result is None

    def test_rollback_on_failure(self):
        """Test automatic rollback on installation failure."""
        with patch('cli_audit.installer.install_tool') as mock_install:
            mock_install.return_value = InstallResult(success=False)

            result = upgrade_tool("tool", config=Config())
            assert result.rollback_executed
```

### Parametrized Tests

```python
@pytest.mark.parametrize("mode,expected", [
    ("ci", "ci"),
    ("server", "server"),
    ("workstation", "workstation"),
])
def test_environment_modes(mode, expected):
    """Test all environment modes."""
    env = detect_environment(override=mode)
    assert env.mode == expected

@pytest.mark.parametrize("version,is_breaking", [
    ("1.0.0", "2.0.0", True),   # Major version bump
    ("1.0.0", "1.1.0", False),  # Minor version bump
    ("1.0.0", "1.0.1", False),  # Patch version bump
])
def test_breaking_change_detection(version, target, is_breaking):
    """Test breaking change detection for various version jumps."""
    result = is_major_upgrade(version, target)
    assert result == is_breaking
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Lint with flake8
        run: flake8 cli_audit tests

      - name: Type check with mypy
        run: mypy cli_audit

      - name: Test with pytest
        run: |
          pytest --cov=cli_audit --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Running Tests Locally (Pre-commit)

```bash
# Format code
black cli_audit tests
isort cli_audit tests

# Lint
flake8 cli_audit tests

# Type check
mypy cli_audit

# Run tests with coverage
pytest --cov=cli_audit --cov-fail-under=80

# Security checks
bandit -r cli_audit
safety check
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Format
black --check cli_audit tests || { echo "❌ black formatting failed"; exit 1; }

# Lint
flake8 cli_audit tests || { echo "❌ flake8 linting failed"; exit 1; }

# Type check
mypy cli_audit || { echo "❌ mypy type checking failed"; exit 1; }

# Tests
pytest --cov=cli_audit --cov-fail-under=80 || { echo "❌ tests failed"; exit 1; }

echo "✅ All checks passed"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Common Issues

**ImportError: No module named 'cli_audit'**
```bash
# Install package in editable mode
pip install -e .
```

**Tests can't find fixtures**
```bash
# Ensure pytest.ini testpaths is correct
# Check that fixtures directory exists
ls -la tests/fixtures/
```

**Mocks not working**
```python
# Ensure you're patching the right location
# Patch where it's used, not where it's defined
@patch('cli_audit.installer.subprocess.run')  # ✓ Correct
@patch('subprocess.run')  # ✗ Wrong location
```

**Coverage too low**
```bash
# Find untested code
pytest --cov=cli_audit --cov-report=term-missing

# Focus on critical paths first
pytest --cov=cli_audit.installer --cov-report=term-missing
```

**Slow tests**
```bash
# Profile slow tests
pytest --durations=10

# Run in parallel
pytest -n auto

# Skip slow tests during development
pytest -m "not slow"
```

**Flaky tests (intermittent failures)**
```python
# Add retries for network tests
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_network_operation():
    ...

# Increase timeouts
@patch('cli_audit.config.TIMEOUT_SECONDS', 10)
def test_with_longer_timeout():
    ...
```

### Debugging Tests

```bash
# Print output (use -s to see print statements)
pytest -s tests/test_config.py

# Drop into debugger on failure
pytest --pdb

# Drop into debugger on first failure
pytest -x --pdb

# Show local variables on failure
pytest -l

# Very verbose output
pytest -vv
```

**Using pdb:**
```python
def test_debug_example():
    import pdb; pdb.set_trace()  # Breakpoint
    result = complex_function()
    assert result == expected
```

**Using pytest.set_trace():**
```python
def test_debug_example():
    pytest.set_trace()  # Pytest-aware breakpoint
    result = complex_function()
    assert result == expected
```

---

## Best Practices

### DO

✅ **Write descriptive test names**
```python
def test_install_python_tool_with_pipx_retries_on_network_failure():
```

✅ **Test one thing per test**
```python
def test_config_loads_from_yaml():
def test_config_validates_version():
def test_config_raises_on_invalid_mode():
```

✅ **Use fixtures for common setup**
```python
@pytest.fixture
def sample_config():
    return Config(...)
```

✅ **Mock external dependencies**
```python
@patch('subprocess.run')
@patch('urllib.request.urlopen')
def test_install(...):
```

✅ **Test edge cases**
```python
def test_empty_string():
def test_none_input():
def test_very_long_input():
```

✅ **Test error paths**
```python
def test_raises_on_invalid_input():
    with pytest.raises(ValueError):
        ...
```

### DON'T

❌ **Don't test multiple things in one test**
```python
# Bad: Tests loading, validation, and merging
def test_config_everything():
    config = load_config()
    assert config.version == 1
    merged = config.merge_with(other)
    ...
```

❌ **Don't use hard-coded paths**
```python
# Bad
config = load_config("/home/user/.config/app/config.yml")

# Good
config = load_config(tmp_path / "config.yml")
```

❌ **Don't skip tests without good reason**
```python
# Bad
@pytest.mark.skip
def test_important_feature():
    ...

# Good
@pytest.mark.skip(reason="Waiting for upstream fix #123")
def test_blocked_feature():
    ...
```

❌ **Don't test implementation details**
```python
# Bad: Tests internal variable names
assert obj._internal_cache == {...}

# Good: Tests public API behavior
assert obj.get_cached_value() == expected
```

---

## Related Documentation

- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines
- **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - API documentation
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Development guide
- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Command-line reference

---

**Last Updated:** 2025-10-13
**Maintainers:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
