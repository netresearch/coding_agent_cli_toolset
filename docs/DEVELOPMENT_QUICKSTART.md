# Development Quickstart

**Get productive in 5 minutes**

---

## ⚡ 5-Minute Setup

```bash
# 1. Clone & enter
git clone https://github.com/your-org/ai_cli_preparation.git
cd ai_cli_preparation

# 2. Setup environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dev dependencies
pip install -e ".[dev]"

# 4. Verify setup
pytest --version
black --version
```

**Done!** You're ready to develop.

---

## 🔥 Common Workflows

### Make a Change

```bash
# 1. Create feature branch
git checkout -b feature/your-feature

# 2. Make changes
vim cli_audit/your_module.py

# 3. Run tests
pytest tests/test_your_module.py -v

# 4. Format & lint
black cli_audit tests
flake8 cli_audit tests

# 5. Commit
git add -A
git commit -m "feat: your feature description"
```

### Run Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_config.py

# With coverage
pytest --cov=cli_audit

# Parallel (fast)
pytest -n auto

# Stop on first failure
pytest -x

# Verbose
pytest -v
```

### Code Quality

```bash
# Auto-format (run first)
black cli_audit tests
isort cli_audit tests

# Lint (check errors)
flake8 cli_audit tests

# Type check
mypy cli_audit

# Security scan
bandit -r cli_audit

# All quality checks
black cli_audit tests && isort cli_audit tests && flake8 cli_audit tests && mypy cli_audit && pytest --cov=cli_audit
```

---

## 📝 Quick Testing Patterns

### Unit Test Template

```python
import pytest
from unittest.mock import patch, MagicMock

def test_your_function():
    # Arrange
    input_data = "test"
    expected = "result"

    # Act
    result = your_function(input_data)

    # Assert
    assert result == expected

@patch("cli_audit.module.subprocess.run")
def test_with_mock(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="success")
    result = function_that_calls_subprocess()
    assert result.success
    mock_run.assert_called_once()
```

### Integration Test Template

```python
from cli_audit import install_tool, Config, Environment

def test_end_to_end_install():
    config = Config()
    env = Environment.detect()

    result = install_tool(
        tool_name="test_tool",
        package_name="test_package",
        target_version="latest",
        config=config,
        env=env,
        language="python",
    )

    assert result.success
    assert result.installed_version
```

---

## 🐛 Debugging Tips

### Enable Verbose Logging

```python
from cli_audit import setup_logging, get_logger

setup_logging(level="DEBUG")
logger = get_logger(__name__)

logger.debug("Detailed debugging info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

### Debug Tests

```bash
# Run specific test with prints
pytest tests/test_config.py::test_specific_function -s

# Drop into debugger on failure
pytest --pdb

# Drop into debugger on error
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Common Issues

**Import errors:**
```bash
# Re-install in editable mode
pip install -e ".[dev]"
```

**Tests not found:**
```bash
# Check pytest.ini configuration
cat pytest.ini

# Run with discovery
pytest --collect-only
```

**Linting failures:**
```bash
# Auto-fix most issues
black cli_audit tests
isort cli_audit tests
```

---

## 📚 Quick Reference

### File Structure

```
cli_audit/
├── __init__.py        # Public API exports
├── environment.py     # Environment detection
├── config.py          # Configuration
├── package_managers.py # PM selection
├── install_plan.py    # Planning
├── installer.py       # Execution
├── bulk.py            # Parallel ops
├── upgrade.py         # Version management
├── breaking_changes.py # Breaking changes
├── reconcile.py       # Conflict resolution
├── logging_config.py  # Logging
└── common.py          # Utilities
```

### Key Commands

```bash
# Development
pytest                  # Run all tests
pytest -n auto          # Parallel tests
black cli_audit tests   # Format code
flake8 cli_audit tests  # Lint code

# Git
git checkout -b feature/name  # New branch
git add -A              # Stage all
git commit -m "msg"     # Commit
git push origin branch  # Push

# Package
pip install -e ".[dev]" # Install dev mode
pip list                # Show installed
```

### Import Patterns

```python
# Phase 2.1: Foundation
from cli_audit import Config, Environment, PackageManager

# Phase 2.2: Installation
from cli_audit import install_tool, InstallResult

# Phase 2.3: Bulk
from cli_audit import bulk_install, BulkInstallResult

# Phase 2.4: Upgrade
from cli_audit import upgrade_tool, get_upgrade_candidates

# Phase 2.5: Reconciliation
from cli_audit import reconcile_tool, detect_installations

# All exports
from cli_audit import *
```

---

## 🎯 Next Steps

After quickstart:

1. **Read Full Guide:** [CONTRIBUTING.md](CONTRIBUTING.md)
2. **Understand Architecture:** [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)
3. **Master Navigation:** [PROJECT_GUIDE.md](PROJECT_GUIDE.md)
4. **Phase Docs:** [claudedocs/phase2_*_implementation.md](claudedocs/)

---

## 💡 Pro Tips

1. **Always format first:** `black` then `flake8`
2. **Test early:** Write tests before code when possible
3. **Use fixtures:** See `tests/fixtures/` for reusable test data
4. **Mock external calls:** Patch `subprocess.run`, `shutil.which`, etc.
5. **Check coverage:** Aim for 85%+ with `pytest --cov`
6. **Run CI locally:** Run all quality checks before pushing
7. **Read existing tests:** Best learning resource for patterns

---

## 🚨 Before Committing Checklist

```bash
☐ black cli_audit tests
☐ isort cli_audit tests
☐ flake8 cli_audit tests
☐ mypy cli_audit
☐ pytest --cov=cli_audit
☐ Git commit message follows format: "type: description"
```

**Commit Message Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code restructuring
- `chore:` Maintenance

---

## 📞 Getting Help

- **Documentation:** [PROJECT_GUIDE.md](PROJECT_GUIDE.md)
- **Issues:** https://github.com/your-org/ai_cli_preparation/issues
- **Discussions:** https://github.com/your-org/ai_cli_preparation/discussions

---

**Last Updated:** 2025-10-09
**Project Version:** 2.0.0-alpha.6
