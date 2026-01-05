<!-- Managed by agent: keep sections and order; edit content, not structure. Last updated: 2025-11-29 -->

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

- [cli_audit/AGENTS.md](./cli_audit/AGENTS.md) — Python package (18 modules)
- [scripts/AGENTS.md](./scripts/AGENTS.md) — Installation scripts (Bash)
- [tests/AGENTS.md](./tests/AGENTS.md) — Test suite (pytest)

## Quick reference

| Command | Purpose |
|---------|---------|
| `uv run python -m pytest` | Run all tests |
| `uv run python -m pytest -x` | Run tests, stop on first failure |
| `uv run python audit.py ripgrep` | Single tool audit |
| `uv run python audit.py --help` | Show CLI options |
| `make audit` | Render from snapshot (<100ms) |
| `make update` | Collect fresh versions (~7s) |
| `make upgrade` | Interactive upgrade guide |

## Project overview

**AI CLI Preparation v2.0** — Tool version auditing and installation management for AI coding agents.

- **Architecture:** 18 Python modules, 74 JSON tool catalogs
- **Phase 1:** Detection & auditing (complete)
- **Phase 2:** Installation & upgrade management (complete)
- **Entry point:** `audit.py` → `cli_audit` package

## When instructions conflict

Nearest AGENTS.md wins. User prompts override all files.
