# Contributing to AI CLI Preparation

This repository, [netresearch/coding_agent_cli_toolset](https://github.com/netresearch/coding_agent_cli_toolset), holds the `cli_audit` Python package, the `audit.py` entry point, the Bash installers under `scripts/`, the tool catalog under `catalog/` and the `cli-tools` skill under `skills/`. This document describes how to set up a development environment, which checks a change has to pass, and where the project's governance and security policies are.

## Development Setup

### Prerequisites

- Python 3.14 or higher (`requires-python = ">=3.14"` in `pyproject.toml`, `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Git
- A POSIX shell with Bash (the installers and shell tests are Bash)
- Make (optional, for the convenience targets in `Makefile.d/`)

### Setting Up Your Environment

```bash
git clone https://github.com/netresearch/coding_agent_cli_toolset.git
cd coding_agent_cli_toolset
uv sync --extra dev            # creates .venv from uv.lock, including the dev extra
uv run pre-commit install      # optional: run the hooks in .pre-commit-config.yaml on commit
```

Run Python commands through `uv run` (for example `uv run pytest`). Each git worktree has its own `.venv`, so run `uv sync --extra dev` in every new worktree.

## Dependencies

- **Selection:** the runtime depends on two libraries, `packaging` and `PyYAML` (`[project] dependencies` in `pyproject.toml`). Development tools are in the `dev` extra. A new dependency needs a reason in the pull request; ask before adding a heavy one (see `AGENTS.md`).
- **Declaration:** `pyproject.toml` declares every direct dependency. `requirements-dev.txt` lists the development tools for the pip-based CI jobs.
- **Locking:** `uv.lock` pins the resolved versions for local development. After changing `pyproject.toml`, run `uv lock` and commit both files.
- **Tracking:** Renovate (`renovate.json`) opens update pull requests. `.github/workflows/auto-merge-deps.yml` calls the organisation's auto-merge workflow on pull requests.
- **Updating this repository's dependencies:** `uv lock --upgrade && uv sync --extra dev && uv run pytest`. `make upgrade` and `make upgrade-all` are features of the tool for the user's system; they do not touch this repository's dependencies.

## Tests

### Running the tests locally

```bash
uv run pytest tests/ --ignore=tests/integration   # unit tests
uv run pytest tests/integration                   # integration tests
uv run pytest --cov=cli_audit --cov-report=term   # all tests with coverage
bash tests/test_guide_multi_install.sh            # shell test suites
bash tests/test_reconcile_dryrun.sh
./scripts/test_smoke.sh                           # smoke test of the CLI
```

`make test`, `make test-unit`, `make test-integration` and `make test-coverage` wrap the pytest commands (`Makefile.d/dev.mk`).

### What the tests cover

- `tests/test_*.py`: unit tests for the modules in `cli_audit/`, for `audit.py` and for the Bash installers and helpers under `scripts/`. Tests that run Bash are marked `skip_on_windows` (see `tests/AGENTS.md`).
- `tests/integration/`: end-to-end tests of the installation workflow.
- `tests/test_guide_multi_install.sh`, `tests/test_reconcile_dryrun.sh`: shell-level tests of the upgrade guide and the reconcile dry run.
- `tests/test_claude_plugin.py`: checks that the skill under `skills/cli-tools/` refers only to scripts and catalog entries that exist.

### Where CI runs them

`.github/workflows/ci.yml` runs on every push and pull request to `main` and `develop`:

| Job | What it runs |
| --- | --- |
| App CI / CI | flake8, mypy, and the unit and integration tests with coverage (uploaded to Codecov), on Python 3.14 on Ubuntu, macOS and Windows |
| App CI / Build | `python -m build` and `twine check dist/*` |
| App CI / Audit | pip-audit, bandit and a CycloneDX SBOM (see "Security checks on pull requests") |
| App CI / Secret Scanning | Betterleaks |
| Shell Tests | the two shell test suites |
| Documentation Check | parses `README.md` |
| End-to-End Integration | runs `audit.py --help` and `audit.py --update-local`, audits `python` with `CLI_AUDIT_JSON=1` and checks the JSON with `jq`, and imports the public API |

### Reading a failure

- A pytest failure prints the test id (`tests/test_x.py::TestClass::test_name`) and a short traceback (`--tb=short` in `pytest.ini`). Re-run that one test locally with `uv run pytest <test id> -vv`.
- A lint or type failure prints `file:line: code message`. Run the same command locally (see "Code quality checks").
- A failure only on the Windows leg usually means a test runs Bash without the `skip_on_windows` marker.

### Tests for new functionality

Every new feature and every bug fix comes with tests that fail without the change. A bug fix starts with a test that reproduces the bug. Use pytest fixtures, `tmp_path` for files, and mock network and subprocess calls in unit tests (`tests/AGENTS.md`). A pull request that adds behaviour without tests is not complete.

## Code quality checks

CI runs these commands (`.github/workflows/ci.yml`, job App CI / CI). Run them before pushing:

```bash
uv run flake8 cli_audit tests --count --show-source --statistics
uv run black --check --diff cli_audit tests audit.py
uv run isort --check-only --diff cli_audit tests audit.py
uv run mypy cli_audit --ignore-missing-imports
```

- **flake8** (`.flake8`, maximum line length 127) fails CI on any finding.
- **McCabe complexity** is the documented exception: CI reports functions above complexity 10 (`flake8 --select=C901 --max-complexity=10 --exit-zero`) without failing. 23 existing functions in ten modules of `cli_audit/` exceed the threshold, seven of them in `reconcile.py`; reducing them is a refactor of that logic. New code should stay below 10.
- **mypy** (`[tool.mypy]` in `pyproject.toml`) fails CI on any finding.
- **black** and **isort** (`[tool.black]`, `[tool.isort]` in `pyproject.toml`) run as pre-commit hooks for `cli_audit/`, `tests/` and `audit.py`, and CI fails when a file there is not formatted (`black --check --diff cli_audit tests audit.py`, `isort --check-only --diff cli_audit tests audit.py`). `uv run black cli_audit tests audit.py` and `uv run isort cli_audit tests audit.py` format them.
- **ShellCheck** runs as a pre-commit hook for the shell scripts under `scripts/` at severity `warning`. CI does not run it.

## Governance and policies

This repository follows the Netresearch organisation policies:

- [Governance](https://github.com/netresearch/.github/blob/main/GOVERNANCE.md): how decisions are made and disputes are settled, and the roles of organisation owners, repository admins, maintainers and contributors.
- [Access roster](https://github.com/netresearch/.github/blob/main/docs/access-roster.md): the accounts that hold admin, maintain and write access to this repository and to the organisation.
- [Roadmap](https://github.com/netresearch/.github/blob/main/ROADMAP.md): the maintenance work planned for the coming year and the work that is excluded.
- [Handling of dependency and code analysis findings](https://github.com/netresearch/.github/blob/main/SECURITY.md#handling-of-dependency-and-code-analysis-findings): which dependency and static-analysis findings block a change, the time limits for fixing the others, and how exceptions are recorded.
- [Secret management](https://github.com/netresearch/.github/blob/main/SECURITY.md#secret-management): how CI and release secrets are stored, who can access them, and when they are rotated.
- [Security policy](https://github.com/netresearch/.github/blob/main/SECURITY.md): how to report a vulnerability privately.

`.github/CODEOWNERS` names the teams that review changes to this repository.

### Security checks on pull requests

These checks run on every pull request to `main`:

- **Dependency review** (`.github/workflows/dependency-review.yml`): fails when the pull request adds or changes a dependency with a known vulnerability of severity moderate or higher. App CI runs the organisation's dependency review a second time with its default threshold, high.
- **pip-audit** (App CI / Audit): audits the packages in `requirements-dev.txt` and their dependencies, resolved at run time, and fails on any known vulnerability.
- **bandit** (App CI / Audit): static security analysis of the Python code; fails on findings of severity medium or higher. The skipped rules and the reason for each are in `[tool.bandit]` in `pyproject.toml`.
- **Betterleaks** (App CI / Secret Scanning): fails when a secret is committed.
- **CodeQL**: GitHub's default code-scanning setup analyses Python and GitHub Actions with the extended query suite and reports alerts to the repository's Security tab.

The only secret the workflows use is `CODECOV_TOKEN`, passed explicitly to the coverage upload in `.github/workflows/ci.yml`. The release workflow uses the job's `GITHUB_TOKEN` and does not publish to PyPI (`.github/workflows/release.yml`).

The security design of the tool itself is described in [docs/SECURITY-ASSURANCE.md](docs/SECURITY-ASSURANCE.md).

## Pull Request Process

1. Create a branch named after the change (`feat/…`, `fix/…`, `chore/…`).
2. Make the change, with tests (see "Tests for new functionality") and documentation updates. Keep pull requests small (about 300 changed lines at most).
3. Run the tests and the code quality checks above.
4. Commit with [Conventional Commits](https://www.conventionalcommits.org/) (`type(scope): description`), signed and with a sign-off: `git commit -S --signoff`.
5. Open a pull request against `main` and fill in `.github/PULL_REQUEST_TEMPLATE.md`. All CI checks must pass.

## Code Style Guidelines

- Follow PEP 8; flake8 enforces it (see "Code quality checks").
- Use type hints; mypy checks them.
- Maximum line length: 127 characters.
- Add docstrings to public functions and classes, in Google style:

  ```python
  def example_function(param1: str, param2: int) -> bool:
      """
      Brief description of function.

      Args:
          param1: Description of param1
          param2: Description of param2

      Returns:
          Description of return value
      """
  ```

- New source files start with an SPDX header: `SPDX-License-Identifier: MIT` (`CC-BY-SA-4.0` under `skills/`) and `SPDX-FileCopyrightText: Netresearch DTT GmbH`.

## Project Structure

```
coding_agent_cli_toolset/
├── audit.py               # CLI entry point
├── cli_audit/             # Python package (see cli_audit/AGENTS.md)
├── catalog/               # One JSON definition per tool
├── scripts/               # Bash installers and helpers (see scripts/AGENTS.md)
├── skills/cli-tools/      # Claude Code skill (CC-BY-SA-4.0)
├── tests/                 # pytest and shell tests (see tests/AGENTS.md)
├── docs/                  # Documentation and ADRs (docs/adr/)
├── Makefile, Makefile.d/  # Task runner
├── .github/workflows/     # CI, release, dependency review
├── pyproject.toml         # Package metadata and tool configuration
├── uv.lock                # Locked dependency versions
├── pytest.ini             # Pytest configuration
└── .flake8                # Flake8 configuration
```

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Creating a Release

1. Update the version in `pyproject.toml` (`version`) and `cli_audit/__init__.py` (`__version__`).
2. Update `CHANGELOG.md`.
3. Commit the changes: `git commit -S --signoff -m "chore: bump version to X.Y.Z"`.
4. Create and push a tag: `git tag -a vX.Y.Z -m "Release version X.Y.Z" && git push origin vX.Y.Z`.
5. `.github/workflows/release.yml` builds the sdist and wheel, checks them with twine and attaches them to a GitHub Release. A tag with a prerelease suffix creates a prerelease. The workflow does not publish to PyPI.

## Getting Help

- Open an issue for bug reports or feature requests.
- Report security vulnerabilities privately, as described in the [security policy](https://github.com/netresearch/.github/blob/main/SECURITY.md).

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming environment for all contributors

## License

Code (scripts, the Python package, workflows and configuration) is licensed under the [MIT License](LICENSE-MIT); the skill under `skills/` is licensed under [CC-BY-SA-4.0](LICENSE-CC-BY-SA-4.0). By contributing, you agree that your contributions are licensed under these terms.
