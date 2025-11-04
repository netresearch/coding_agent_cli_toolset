# Project Overview

## Project Purpose
AI CLI Preparation is a tool version auditing and installation management utility specifically designed for AI coding agents (like Claude Code). It ensures AI agents have access to 50+ essential developer CLI tools with up-to-date versions.

**Core Functionality:**
- Detects installed versions of developer tools across PATH
- Compares local versions against latest upstream releases (GitHub, PyPI, crates.io, npm)
- Reports version status with actionable remediation hints
- Provides installation/upgrade scripts for missing or outdated tools
- Supports offline-first operation with committed version caches

**Architecture Phases:**
- **Phase 1 (Complete)**: Tool detection, version auditing, offline-first caching, snapshot-based workflows
- **Phase 2 (Complete)**: Context-aware installation/upgrade management, breaking change detection, reconciliation
- **Phase 3 (Future)**: Advanced dependency resolution, rollback mechanisms

## Key Characteristics
- **Agent-focused**: Tool selection optimized for AI coding agent needs (ripgrep, fd, jq, ast-grep, etc.)
- **Offline-capable**: Committed cache (`latest_versions.json`) enables offline audits
- **Snapshot-based**: Separate collect (`make update`) and render (`make audit`) phases
- **Parallel execution**: ThreadPoolExecutor with 16 workers for fast collection (~3-10s for 50+ tools)
- **Zero dependencies**: Core audit uses Python standard library only (no pip install needed)
- **Comprehensive**: Covers 50+ tools across multiple categories (runtimes, search, security, formatters, cloud/infra)

## Primary Use Cases
1. **AI agent readiness verification**: Confirm coding agents have necessary tools before starting work
2. **Development environment setup**: Bootstrap new machines with agent-optimized toolchains
3. **Version compliance checking**: Ensure tools meet minimum version requirements
4. **Automated toolchain updates**: Keep development tools current via upgrade workflows
5. **Installation method reconciliation**: Identify and resolve duplicate tool installations

## Tech Stack
- **Language**: Python 3.9+ (primary language, standard library only for core)
- **Task Automation**: GNU Make (Makefile + modular includes in Makefile.d/)
- **Installation Scripts**: Bash (with set -euo pipefail, shellcheck-compliant)
- **Data Formats**: JSON for caching (latest_versions.json, tools_snapshot.json)
- **Dependencies**: 
  - Core: Python standard library only
  - Optional: packaging, PyYAML (for Phase 2 config support)
  - Dev: pytest, flake8, mypy, black, isort (listed in pyproject.toml)

## Project Status
- **Production-ready**: Phase 1 detection/audit fully functional and tested in production
- **Beta**: Phase 2 installation management (2.0.0-alpha.6)
- **Documentation**: Comprehensive (12 docs files, 189KB, including architecture, API reference, troubleshooting)
- **Testing**: Smoke tests exist (test_smoke.sh), formal test suite acknowledged as needed in README