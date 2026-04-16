<!-- Managed by agent: keep sections and order; edit content, not structure. Last updated: 2026-04-16 -->

# AGENTS.md (root)

**Precedence:** The **closest AGENTS.md** to changed files wins. Root holds global defaults only.

## Global rules

- Keep PRs small (~≤300 net LOC)
- Conventional Commits: `type(scope): description`
  - Types: feat, fix, docs, chore, test, refactor, perf, style
  - Scopes: audit, catalog, scripts, docs, tests
- Ask before: heavy deps, full rewrites, breaking changes
- Never commit secrets, PII, or credentials

## Setup

**This project uses [uv](https://docs.astral.sh/uv/) for package management.** Always use `uv run` to execute Python commands.

```bash
# Sync dependencies (run after clone or when pyproject.toml changes)
uv sync --extra dev

# Run any Python command
uv run python -m pytest          # Run tests
uv run python audit.py ripgrep   # Run audit script
uv run python -m flake8          # Run linter
```

**Why uv?** Fast dependency resolution, proper lockfile support, and isolated environments without manual venv activation.

**Prerequisites:** Python ≥ 3.14, `uv`, and a POSIX shell (most installer scripts are Bash).

## Development

Minimal pre-commit checks (also enforced by `.pre-commit-config.yaml`):

```bash
uv run python -m pytest          # All tests (required)
uv run python -m flake8 cli_audit tests  # flake8 (required)
uv run python -m mypy cli_audit  # mypy (optional)
./scripts/test_smoke.sh          # Smoke tests (required)
uv run python audit.py --help    # Verify CLI works
```

Install the git hooks once per checkout: `uv run pre-commit install`.
New features and bug fixes go on a feature branch (`fix/…`, `feat/…`, `chore/…`) → PR against `main` → signed commits (`git commit -S --signoff`).
See [`SECURITY.md`](./SECURITY.md) for vulnerability reporting and [`CHANGELOG.md`](./CHANGELOG.md) for release history.

## Testing

```bash
uv run pytest                    # Full suite (546 tests)
uv run pytest -x -q              # Fail-fast, quiet
uv run pytest tests/test_upgrade.py -k multi_version  # Focused run
uv run pytest --cov=cli_audit --cov-report=term  # With coverage
```

Test layout and conventions: see [`tests/AGENTS.md`](./tests/AGENTS.md). Integration suite under `tests/integration/` is collected separately — CI runs it as its own step.

## Project maintenance vs. tool feature

This repo **is** a CLI tool manager, so the word "upgrade" is overloaded:

| You want to… | Run |
|--------------|-----|
| Maintain **this repo's** Python deps (pyproject.toml / uv.lock) | `uv lock --upgrade && uv sync --all-extras --dev && pytest` |
| Run the **tool's feature** that upgrades the user's system-wide CLI tooling | `make upgrade-all` |
| Run only the **interactive** per-tool upgrade guide | `make upgrade` |

`make upgrade-project-deps` targets `pip install -r requirements.txt` which does not match this repo's uv layout — use uv directly.

## Index of scoped AGENTS.md

- [cli_audit/AGENTS.md](./cli_audit/AGENTS.md) — Python package (21 modules)
- [scripts/AGENTS.md](./scripts/AGENTS.md) — Installation scripts (Bash, 33 scripts)
- [tests/AGENTS.md](./tests/AGENTS.md) — Test suite (pytest, 14 test files)

## Commands (verified 2026-04-16)

| Command | Purpose |
|---------|---------|
| `uv run python -m pytest` | Run all tests |
| `uv run python -m pytest -x` | Run tests, stop on first failure |
| `uv run python audit.py ripgrep` | Single tool audit |
| `uv run python audit.py --help` | Show CLI options |
| `make audit` | Render from snapshot (fast, no network) |
| `make audit-offline` | Offline audit with hints |
| `make outdated` | Show only missing/outdated tools |
| `make update` | Collect fresh versions (~10s) |
| `make update-local` | Update only local state (no network) |
| `make update-baseline` | Update upstream baseline for commit |
| `make install-<tool>` | Install any cataloged tool (e.g., `make install-jq`) |
| `make upgrade-<tool>` | Upgrade any tool (e.g., `make upgrade-ripgrep`) |
| `make uninstall-<tool>` | Uninstall any tool (e.g., `make uninstall-jq`) |
| `make reconcile-<tool>` | Reconcile install method (e.g., `make reconcile-node`) |
| `make upgrade` | Interactive upgrade guide |
| `make cleanup` | Interactive tool removal |
| `make upgrade-managed` | Upgrade all package managers |
| `make upgrade-dry-run` | Preview upgrades without changes |
| `make upgrade-ignore-pins` | Upgrade guide ignoring version pins |
| `make reset-pins` | Remove all version pins |
| `make upgrade-all` | Full system upgrade (data + managers + tools) |
| `./scripts/set_auto_update.sh <tool>` | Enable auto-update for a tool |
| `uv run python audit.py --versions` | Show multi-version runtime status |
| `uv run python audit.py --versions php` | Show specific runtime versions |

## Data files

**2-file data model** (Phase 2.1):
- `upstream_versions.json` — Latest upstream versions (committed, shared baseline)
- `local_state.json` — Machine-specific installation state (gitignored)

**User configuration:**
- `~/.config/cli-audit/config.yml` — User preferences (auto_update, tool overrides)
  - Multi-version tools (python, node, php, ruby, go) store `auto_update` per cycle (e.g. `python@3.13`), not per base tool.

**Caches:**
- `~/.cache/cli-audit/endoflife.json` — endoflife.date response cache, used as fallback on transient HTTP failures (override path via `CLI_AUDIT_ENDOFLIFE_CACHE`).

## Architecture

**AI CLI Preparation v2.0** — Tool version auditing and installation management for AI coding agents.

- **Modules:** 21 Python modules under `cli_audit/` (see [`cli_audit/AGENTS.md`](./cli_audit/AGENTS.md))
- **Catalog:** 89 JSON tool definitions under `catalog/`
- **Installers:** 33 Bash scripts under `scripts/` (see [`scripts/AGENTS.md`](./scripts/AGENTS.md))
- **Phase 1:** Detection & auditing (complete)
- **Phase 2:** Installation & upgrade management (complete)
- **Entry point:** `audit.py` → `cli_audit` package

### Project structure

```
audit.py               # CLI dispatcher (cmd_audit, cmd_update, cmd_install, …)
cli_audit/             # Core library (detection, collectors, snapshot, installer, …)
catalog/               # Per-tool JSON definitions (binary_name, version_command, multi_version)
scripts/               # Installer / upgrade / reconcile shell scripts + scripts/lib helpers
tests/                 # pytest suite (unit + integration)
Makefile / Makefile.d/ # Task runner: `make audit`, `make upgrade`, `make upgrade-all`
```

## Multi-version runtimes

Runtimes supporting multiple concurrent versions (PHP, Python, Node.js, Ruby, Go) use dynamic detection from [endoflife.date](https://endoflife.date/) API.

```bash
# Show all runtime versions
uv run python audit.py --versions

# JSON output for scripting
CLI_AUDIT_JSON=1 uv run python audit.py --versions
```

**Catalog config:** Tools with `multi_version.enabled: true` in their JSON catalog define detection strategies (binary patterns or version manager directories).

## When instructions conflict

Nearest AGENTS.md wins. User prompts override all files.

---

*Last verified: 2026-04-16 (against `main` at HEAD).*
