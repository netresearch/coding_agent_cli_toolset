# Contributing to AI CLI Preparation

Thank you for your interest in contributing to AI CLI Preparation! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Make (optional, for convenience targets)

### Setting Up Your Environment

1. Fork and clone the repository:
```bash
git clone https://github.com/your-username/ai_cli_preparation.git
cd ai_cli_preparation
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
# OR
pip install -r requirements-dev.txt
```

## Development Workflow

### Running Tests

Run the full test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=cli_audit --cov-report=term --cov-report=html
```

Run specific test files:
```bash
pytest tests/unit/test_config.py
pytest tests/integration/test_e2e_install.py
```

Run tests in parallel:
```bash
pytest -n auto
```

### Code Quality

Run linting:
```bash
flake8 cli_audit tests
```

Run type checking:
```bash
mypy cli_audit
```

Format code with black:
```bash
black cli_audit tests
```

Sort imports with isort:
```bash
isort cli_audit tests
```

Run security checks:
```bash
bandit -r cli_audit
safety check
```

### All Quality Checks at Once

Run all quality checks before committing:
```bash
# Formatting
black cli_audit tests
isort cli_audit tests

# Linting
flake8 cli_audit tests
mypy cli_audit

# Tests
pytest --cov=cli_audit

# Security
bandit -r cli_audit
safety check
```

## Continuous Integration

### GitHub Actions Workflows

We use GitHub Actions for CI/CD. The following workflows are configured:

#### CI Workflow (`.github/workflows/ci.yml`)

Runs on every push and pull request to `main` and `develop` branches:

- **Lint and Type Check**: Runs flake8 and mypy
- **Test Suite**: Runs pytest on multiple OS (Ubuntu, macOS, Windows) and Python versions (3.9-3.12)
- **Security Scan**: Runs bandit and safety checks
- **Build**: Builds distribution packages
- **Documentation**: Validates README and config files
- **Integration E2E**: Tests CLI execution and programmatic API

#### Release Workflow (`.github/workflows/release.yml`)

Triggers on version tags (e.g., `v2.0.0`):

- Builds distribution packages
- Creates GitHub release with changelog
- Publishes to PyPI (if configured)
- Publishes to Test PyPI (manual trigger)

#### Dependabot (`.github/dependabot.yml`)

Automatically creates PRs for:
- Python dependency updates (weekly)
- GitHub Actions updates (weekly)

### Required Secrets

For full CI/CD functionality, configure these GitHub secrets:

- `PYPI_API_TOKEN`: PyPI API token for publishing releases
- `TEST_PYPI_API_TOKEN`: Test PyPI token for testing releases
- `CODECOV_TOKEN`: Codecov token for coverage reports (optional)

## Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clear, concise commit messages
   - Add tests for new functionality
   - Update documentation as needed
   - Follow the existing code style

3. **Run quality checks**:
   ```bash
   black cli_audit tests
   isort cli_audit tests
   flake8 cli_audit tests
   pytest --cov=cli_audit
   ```

4. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**:
   - Provide a clear description of your changes
   - Reference any related issues
   - Ensure all CI checks pass
   - Request review from maintainers

## Code Style Guidelines

### Python Style

- Follow PEP 8 guidelines (enforced by flake8)
- Use type hints where possible
- Maximum line length: 127 characters
- Use black for formatting
- Use isort for import sorting

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings:
  ```python
  def example_function(param1: str, param2: int) -> bool:
      """
      Brief description of function.

      Args:
          param1: Description of param1
          param2: Description of param2

      Returns:
          Description of return value

      Raises:
          ValueError: Description of when this is raised
      """
  ```

### Testing

- Write tests for all new functionality
- Aim for >80% code coverage
- Use descriptive test names: `test_install_python_tool_with_pipx`
- Use fixtures for common setup
- Mock external dependencies (network, filesystem)

## Project Structure

```
ai_cli_preparation/
├── cli_audit/              # Main package
│   ├── __init__.py        # Public API exports
│   ├── config.py          # Configuration management
│   ├── environment.py     # Environment detection
│   ├── installer.py       # Installation logic
│   ├── bulk.py            # Bulk operations
│   ├── upgrade.py         # Upgrade management
│   ├── reconcile.py       # Reconciliation
│   └── breaking_changes.py # Breaking change detection
├── tests/
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── scripts/               # Installation scripts
├── claudedocs/            # Claude-specific documentation
├── .github/
│   └── workflows/         # CI/CD workflows
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml         # Package configuration
├── pytest.ini             # Pytest configuration
├── mypy.ini              # Mypy configuration
└── .flake8               # Flake8 configuration
```

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Creating a Release

1. Update version in:
   - `cli_audit/__init__.py` (`__version__`)
   - `pyproject.toml` (`version`)

2. Update CHANGELOG.md (if exists)

3. Commit changes:
   ```bash
   git commit -am "chore: bump version to X.Y.Z"
   ```

4. Create and push tag:
   ```bash
   git tag -a vX.Y.Z -m "Release version X.Y.Z"
   git push origin vX.Y.Z
   ```

5. GitHub Actions will automatically:
   - Run CI checks
   - Build distribution packages
   - Create GitHub release
   - Publish to PyPI (if configured)

## Getting Help

- Open an issue for bug reports or feature requests
- Check existing issues and PRs before creating new ones
- Join discussions in GitHub Discussions (if enabled)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming environment for all contributors

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
