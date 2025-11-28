# AI CLI Preparation - Project Context (AI Agent Reference)

**Last Updated:** 2025-10-18
**Version:** 2.0.0-alpha.6
**For:** AI Coding Agents (Claude Code, etc.)

## Quick Reference

**Purpose:** Environment audit and tool management system ensuring AI coding agents have all necessary CLI tools installed, current, and properly configured

**Repository:** github.com/netresearch/coding_agent_cli_toolset
**Primary Language:** Python 3.9+ (dev: 3.14.0rc2)
**Architecture:** Offline-first, parallel, resilient tool version auditing with comprehensive upgrade orchestration
**Tool Coverage:** 64 tools across 10 categories
**Phase Status:** Phase 1 (Audit) Complete | Phase 2 (Install/Upgrade) Alpha

## Core Capabilities

- Multi-source version resolution (GitHub, PyPI, crates.io, npm, GNU FTP)
- Installation method detection (uv, pipx, npm, cargo, apt, homebrew, etc.)
- Offline operation via committed cache (latest_versions.json)
- Snapshot-based workflow (separate collection from rendering)
- Parallel execution (16 workers default, configurable via CLI_AUDIT_MAX_WORKERS)
- Enhanced tool detection (searches PATH + common directories + tool-specific locations)
- Role-based presets (agent-core, python-core, security-core, etc.)
- Environment variable configuration via .env file (exported to subprocesses)

## File Structure

```
ai_cli_preparation/
├── cli_audit.py (2375 lines)    # Main audit engine
├── smart_column.py (222 lines)  # ANSI/emoji-aware formatter
├── latest_versions.json          # Manual cache + hints
├── tools_snapshot.json           # Audit results snapshot
├── Makefile                      # Build targets
├── scripts/                      # Installation scripts
│   ├── install_core.sh
│   ├── install_python.sh
│   ├── install_node.sh
│   ├── install_go.sh
│   └── ... (9 more)
├── docs/                         # Human-focused technical docs
│   ├── Phase 1: Detection & Auditing
│   │   ├── INDEX.md
│   │   ├── ARCHITECTURE.md (updated with Phase 2)
│   │   ├── API_REFERENCE.md
│   │   ├── FUNCTION_REFERENCE.md
│   │   ├── QUICK_REFERENCE.md
│   │   ├── DEVELOPER_GUIDE.md
│   │   ├── TOOL_ECOSYSTEM.md
│   │   ├── DEPLOYMENT.md
│   │   └── TROUBLESHOOTING.md
│   ├── Phase 2: Installation & Upgrade
│   │   ├── PHASE2_API_REFERENCE.md
│   │   ├── CLI_REFERENCE.md
│   │   ├── TESTING.md
│   │   ├── ERROR_CATALOG.md
│   │   └── INTEGRATION_EXAMPLES.md
│   ├── Planning & Specifications
│   │   ├── PRD.md
│   │   ├── PHASE2_IMPLEMENTATION.md
│   │   ├── CONFIGURATION_SPEC.md
│   │   └── adr/ (6 ADRs)
└── claudedocs/                   # AI agent context (this directory)
    ├── project_context.md
    ├── session_summary.md
    └── session_initialization.md
```

## Key Components

### Tool Dataclass (cli_audit.py:729)
```python
@dataclass(frozen=True)
class Tool:
    name: str                    # Display name
    candidates: tuple[str, ...]  # Executable names
    source_kind: str            # gh|pypi|crates|npm|gnu|skip
    source_args: tuple[str, ...] # Source-specific params
```

### TOOLS Registry (cli_audit.py:738)
Ordered tuple of 64 Tool definitions, categorized:
1. Runtimes (go, python, rust, node) + package managers
2. Core dev tools (ripgrep, ast-grep, fzf, fd, jq, etc.)
3. Security (semgrep, bandit, gitleaks, trivy)
4. Formatters (black, eslint, prettier, shellcheck)
5. Git tools (git, gh, glab, git-absorb)
6. Cloud/infra (aws, kubectl, terraform, docker)
7. AI agent tools (claude, codex, gam)

**Enhanced Detection (2025-10-13):**
- Searches beyond PATH for tools in non-standard locations
- Tool-specific paths: gam in ~/bin/gam7/, claude in ~/.claude/local/
- Common search paths: ~/bin, ~/.local/bin, /usr/local/bin
- Cargo bin fallback for Rust tools

### Architecture Pattern
```
CLI Entry → Mode Router → Parallel Collection (ThreadPoolExecutor)
          ↓                        ↓
    COLLECT/RENDER/NORMAL    audit_tool() × 50+
                                  ↓
                        Local Discovery + Upstream APIs
                                  ↓
                        Cache Layer (hints → manual → upstream)
                                  ↓
                        Snapshot Write / Render
```

## Common Operations

### Quick Audit
```bash
# Render from snapshot (no network, <100ms)
make audit

# Update snapshot with fresh data (~10s)
make update

# Interactive upgrade guide
make upgrade

# Complete system upgrade (5 stages)
make upgrade-all

# Preview system upgrade (dry-run)
make upgrade-all-dry-run

# Offline audit with hints
make audit-offline
```

### System-Wide Upgrade (New in alpha.6)
```bash
# 5-Stage orchestrated upgrade workflow
make upgrade-all
# Stage 1: Refresh version data
# Stage 2: Upgrade package managers (apt, brew, snap, flatpak)
# Stage 3: Upgrade runtimes (Python, Node.js, Go, Ruby, Rust)
# Stage 4: Upgrade user package managers (uv, pipx, npm, pnpm, yarn, cargo, etc.)
# Stage 5: Upgrade all CLI tools

# Features:
# - UV migration (auto-migrates pip/pipx to uv tools)
# - System package detection (skips apt/brew managed)
# - Comprehensive logging (logs/upgrade-YYYYMMDD-HHMMSS.log)
# - Dry-run mode available

# Preview without making changes
make upgrade-all-dry-run

# Check PATH configuration
make check-path
```

### Role-Based Audits
```bash
make audit-offline-agent-core    # AI agent essentials
make audit-offline-python-core   # Python development
make audit-offline-security-core # Security tools
```

### Debug Mode
```bash
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only ripgrep
CLI_AUDIT_TRACE=1 python3 cli_audit.py
```

## Environment Variables (Key)

**Mode Control:**
- `CLI_AUDIT_COLLECT=1` - Collect-only (no rendering)
- `CLI_AUDIT_RENDER=1` - Render-only (no network)
- `CLI_AUDIT_OFFLINE=1` - Force offline (manual cache only)

**Performance:**
- `CLI_AUDIT_MAX_WORKERS=16` - Concurrency (default 16, loaded from .env if present)
- `CLI_AUDIT_TIMEOUT_SECONDS=3` - Per-tool timeout

**Note (2025-10-13):** Environment variables are now properly exported from Makefile to Python subprocesses. Set in .env file to configure globally.

**Output:**
- `CLI_AUDIT_JSON=1` - JSON output
- `CLI_AUDIT_LINKS=1` - OSC 8 hyperlinks
- `CLI_AUDIT_EMOJI=1` - Emoji status icons

**Debug:**
- `CLI_AUDIT_DEBUG=1` - Debug messages
- `CLI_AUDIT_TRACE=1` - Detailed trace
- `CLI_AUDIT_PROGRESS=1` - Progress output

## Integration Points

**Claude Code:** Tracked via catalog/claude.json (not as npm dependency)

**Use Case:** Ensures Claude Code and other AI agents have access to all necessary developer tools (ripgrep for code search, ast-grep for semantic search, jq for JSON parsing, git/gh for version control, etc.)

**Workflow:**
1. AI agent environment needs verification
2. Run `make audit` to check tool availability
3. If tools missing/outdated, run `make upgrade` for guided installation
4. Re-audit until environment ready
5. AI agent has full tooling access

## Cache Files

### latest_versions.json
```json
{
  "__hints__": {
    "gh:owner/repo": "latest_redirect",  // API method cache
    "local_flag:tool": "--version"        // Version flag cache
  },
  "__methods__": {
    "tool": "source_kind"  // Override upstream source
  },
  "tool-name": "1.2.3"     // Latest version cache
}
```

### tools_snapshot.json
```json
{
  "__meta__": {
    "schema_version": 1,
    "created_at": "2025-10-09T...",
    "count": 50
  },
  "tools": [
    {
      "tool": "ripgrep",
      "installed": "14.1.1 (150ms)",
      "installed_method": "rustup/cargo",
      "latest_upstream": "14.1.1 (220ms)",
      "upstream_method": "github",
      "status": "UP-TO-DATE"
    }
  ]
}
```

## Current Git State

**Branch:** main
**Working Tree:** Modified (documentation updates in progress)
**Modified:** latest_versions.json, tools_snapshot.json, docs/
**Remote:** git@github.com:netresearch/coding_agent_cli_toolset.git

**Recent commits (2025-10-18 - upgrade-all feature):**
- 9b784ed - chore: update version snapshots
- 22c1603 - feat(upgrade-all): add UV migration for pip/pipx packages
- 1b71b71 - feat(upgrade-all): skip pip/pipx when uv is managing Python packages
- cceed18 - fix(upgrade-all): detect pipx packages with missing metadata and provide fix
- 7d691cb - feat(upgrade-all): add comprehensive version and location info to all upgrade stages

**Recent commits (2025-10-13 - environment fixes):**
- 34fa37f - chore(snapshot): update tool audit cache with improved detection
- 80abd30 - fix(guide): clarify Docker CLI vs Docker Engine terminology
- aa57210 - fix(cli_audit): resolve three critical issues in environment and detection

**Recent commits (2025-10-09 - documentation):**
- 0c7ade3 - Snapshot-based collect/render modes
- 3dd5082 - Lock ordering fixes (thread safety)
- c160361 - Classification improvements (shebang detection)

## Key Design Patterns

1. **Offline-First:** Works without network via committed cache
2. **Parallel Execution:** 16 concurrent workers, 3s timeout per tool
3. **Graceful Degradation:** Timeouts, retries, fallbacks at every layer
4. **Immutable Data:** Frozen dataclasses, atomic file writes
5. **Lock Ordering:** MANUAL_LOCK → HINTS_LOCK (enforced)
6. **Cache Hierarchy:** hints → manual → upstream (fastest to slowest)

## Threading Model

- **ThreadPoolExecutor:** Parallel tool audits
- **MANUAL_LOCK:** For latest_versions.json updates
- **HINTS_LOCK:** For __hints__ updates (nested in MANUAL_LOCK)
- **Lock Order Rule:** Always acquire MANUAL_LOCK before HINTS_LOCK

## Performance Characteristics

| Scenario | Time | Notes |
|----------|------|-------|
| Collection (online) | ~10s | 50 tools, 16 workers |
| Collection (offline) | ~3s | Cache hits only |
| Render from snapshot | <100ms | No network, pure JSON read |
| Single tool audit | ~300ms | Version check + upstream |

## Extension Points

**Adding new tools:**
1. Add Tool() to TOOLS registry in cli_audit.py
2. Place in appropriate category
3. Add to latest_versions.json for offline fallback
4. Update TOOL_ECOSYSTEM.md documentation

**Adding new upstream sources:**
1. Implement latest_<source>() function
2. Update get_latest() dispatcher
3. Add source_kind to Tool options

## Documentation Map

**For Humans (docs/):**

**Phase 1 (Detection & Auditing):**
- INDEX.md - Documentation navigation hub
- ARCHITECTURE.md - System design, data flows (updated with Phase 2)
- API_REFERENCE.md - Phase 1 audit functions, environment variables
- FUNCTION_REFERENCE.md - Function quick lookup
- QUICK_REFERENCE.md - Command cheat sheet
- DEVELOPER_GUIDE.md - Contributing, adding tools
- TOOL_ECOSYSTEM.md - Complete 50+ tool catalog
- DEPLOYMENT.md - Makefile targets, CI/CD
- TROUBLESHOOTING.md - Common issues, debugging

**Phase 2 (Installation & Upgrade):**
- PHASE2_API_REFERENCE.md - Complete Phase 2 API (78 symbols across 11 modules)
- CLI_REFERENCE.md - Command-line reference with 60+ environment variables
- TESTING.md - Comprehensive testing guide for contributors
- ERROR_CATALOG.md - Error categorization with troubleshooting (26 error codes)
- INTEGRATION_EXAMPLES.md - Real-world CI/CD and workflow patterns

**Planning & Specifications:**
- PRD.md - Product requirements document
- PHASE2_IMPLEMENTATION.md - Implementation roadmap
- CONFIGURATION_SPEC.md - .cli-audit.yml schema
- adr/ - Architecture Decision Records (6 ADRs)

**For AI Agents (claudedocs/):**
- project_context.md (this file) - Quick reference
- session_summary.md - Session history
- session_initialization.md - Session context

## Quick Troubleshooting

**Network timeouts:**
```bash
CLI_AUDIT_TIMEOUT_SECONDS=10 python3 cli_audit.py
CLI_AUDIT_HTTP_RETRIES=5 python3 cli_audit.py
```

**GitHub rate limiting:**
```bash
export GITHUB_TOKEN=ghp_...
python3 cli_audit.py
```

**Version detection issues:**
```bash
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only tool-name
```

**Cache corruption:**
```bash
rm latest_versions.json tools_snapshot.json
make update
```

## AI Agent Best Practices

1. **Check tool availability** before attempting to use CLI tools
2. **Use offline mode** for repeated audits (faster)
3. **Reference tool catalog** in TOOL_ECOSYSTEM.md for capabilities
4. **Leverage parallel execution** for efficiency
5. **Handle graceful failures** - tool may be unavailable

## See Also

- Main README: ../README.md (user-focused documentation)
- Technical docs: ../docs/ (comprehensive developer documentation)
- Installation scripts: ../scripts/ (automated tool installation)
