<!-- Managed by agent: keep sections and order; edit content, not structure. Last updated: 2026-02-06 -->

# AGENTS.md (root)

**Precedence:** The **closest AGENTS.md** to changed files wins. Root holds global defaults only.

## Global rules

- Keep PRs small (~≤300 net LOC)
- Conventional Commits: `type(scope): description`
  - Types: feat, fix, docs, chore, test, refactor, perf, style
  - Scopes: audit, catalog, scripts, docs, tests
- Ask before: heavy deps, full rewrites, breaking changes
- Never commit secrets, PII, or credentials

## Package management (uv)

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

## Minimal pre-commit checks

```bash
uv run python -m pytest          # All tests (required)
uv run python -m flake8 cli_audit tests  # flake8 (required)
uv run python -m mypy cli_audit  # mypy (optional)
./scripts/test_smoke.sh          # Smoke tests (required)
uv run python audit.py --help    # Verify CLI works
```

## Index of scoped AGENTS.md

- [cli_audit/AGENTS.md](./cli_audit/AGENTS.md) — Python package (21 modules)
- [scripts/AGENTS.md](./scripts/AGENTS.md) — Installation scripts (Bash, 30 scripts)
- [tests/AGENTS.md](./tests/AGENTS.md) — Test suite (pytest, 14 test files)

## Quick reference

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

## Project overview

**AI CLI Preparation v2.0** — Tool version auditing and installation management for AI coding agents.

- **Architecture:** 21 Python modules, 79 JSON tool catalogs
- **Phase 1:** Detection & auditing (complete)
- **Phase 2:** Installation & upgrade management (complete)
- **Entry point:** `audit.py` → `cli_audit` package

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
