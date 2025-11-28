<!-- Managed by agent: keep sections & order; edit content, not structure. Last updated: 2025-11-29 -->

# AGENTS.md (root)

**Precedence:** The **closest AGENTS.md** to changed files wins. Root holds global defaults only.

## Global rules

- Keep PRs small (~≤300 net LOC changed)
- Conventional Commits: `type(scope): description`
  - Types: feat, fix, docs, chore, test, refactor, perf, style
  - Scopes: audit, catalog, scripts, docs, tests
- Ask before: heavy dependencies, full rewrites, breaking changes
- Never commit secrets, PII, or credentials

## Project overview

**AI CLI Preparation v2.0** - Tool version auditing and installation management for AI coding agents.

**Architecture:** Modular design with 18 specialized Python modules, 74 JSON tool catalogs, and comprehensive testing.

- **Phase 1 (Complete):** Detection & auditing with modular refactoring
- **Phase 2 (Complete):** Installation & upgrade management
- **Entry Point:** `audit.py` (50 lines) → cli_audit package

## Minimal pre-commit checks

```bash
# Linting
make lint                    # flake8 (required)

# Type checking (optional)
make lint-types              # mypy

# Testing
./scripts/test_smoke.sh      # Smoke tests (required)

# Audit validation
make audit                   # Verify core workflows
```

## Index of scoped AGENTS.md

- **[cli_audit/AGENTS.md](cli_audit/AGENTS.md)** — Python package (18 modules, Phase 1 + Phase 2)
- **[tests/AGENTS.md](tests/AGENTS.md)** — Test suite (unit, integration, E2E)
- **[scripts/AGENTS.md](scripts/AGENTS.md)** — Installation scripts (Bash, 25+ scripts)

## Quick reference

**Common commands:**
```bash
make audit               # Render from snapshot (<100ms)
make update              # Collect fresh versions (~7s)
make upgrade             # Interactive upgrade guide
make upgrade-all         # Complete 5-stage system upgrade

python3 audit.py         # Direct invocation
python3 audit.py ripgrep # Single tool audit
python3 audit.py --update ripgrep  # Update single tool
```

**Key files:**
- `audit.py` — Entry point
- `cli_audit/` — 18 Python modules (~7K lines)
- `catalog/` — 74 JSON tool definitions
- `latest_versions.json` — Version cache
- `tools_snapshot.json` — Snapshot data

**Documentation:**
- `docs/INDEX.md` — Documentation navigation
- `docs/MIGRATION_GUIDE.md` — v1.x → v2.0 transition
- `docs/CATALOG_GUIDE.md` — JSON catalog system
- `docs/ARCHITECTURE.md` — Modular design

## When instructions conflict

Nearest AGENTS.md wins. User prompts override all files.
