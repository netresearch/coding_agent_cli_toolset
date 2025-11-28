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

## Minimal pre-commit checks

```bash
make lint                    # flake8 (required)
make lint-types              # mypy (optional)
./scripts/test_smoke.sh      # Smoke tests (required)
make audit                   # Verify core workflows
```

## Index of scoped AGENTS.md

- [cli_audit/AGENTS.md](./cli_audit/AGENTS.md) — Python package (18 modules)
- [scripts/AGENTS.md](./scripts/AGENTS.md) — Installation scripts (Bash)
- [tests/AGENTS.md](./tests/AGENTS.md) — Test suite (pytest)

## Quick reference

| Command | Purpose |
|---------|---------|
| `make audit` | Render from snapshot (<100ms) |
| `make update` | Collect fresh versions (~7s) |
| `make upgrade` | Interactive upgrade guide |
| `make upgrade-all` | Complete 5-stage system upgrade |
| `python3 audit.py ripgrep` | Single tool audit |

## Project overview

**AI CLI Preparation v2.0** — Tool version auditing and installation management for AI coding agents.

- **Architecture:** 18 Python modules, 74 JSON tool catalogs
- **Phase 1:** Detection & auditing (complete)
- **Phase 2:** Installation & upgrade management (complete)
- **Entry point:** `audit.py` → `cli_audit` package

## When instructions conflict

Nearest AGENTS.md wins. User prompts override all files.
