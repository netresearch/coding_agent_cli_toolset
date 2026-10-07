<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<!-- SPDX-FileCopyrightText: Netresearch DTT GmbH -->

# CLI Reference

**Version:** 2.0.0-alpha.6
**Last Updated:** 2025-10-13

Complete command-line reference for CLI Audit tool, covering Phase 1 audit commands, Phase 2 installation workflows, and Makefile automation.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Phase 1: Audit Commands](#phase-1-audit-commands)
- [Environment Variables](#environment-variables)
- [Makefile Targets](#makefile-targets)
- [Phase 2: Python API](#phase-2-python-api)
- [Configuration Files](#configuration-files)
- [Output Formats](#output-formats)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Quick Reference

```bash
# Basic audit
uv run python audit.py | column -s '|' -t

# Specific tools only
uv run python audit.py ripgrep fd bat

# JSON output
CLI_AUDIT_JSON=1 uv run python audit.py

# Offline mode
CLI_AUDIT_OFFLINE=1 uv run python audit.py

# Snapshot-based workflow
make update      # Collect data (network required)
make audit       # Render table (offline)
make audit-auto  # Update if missing, then render

# System-wide upgrade
make upgrade-all         # Complete 5-stage system upgrade
make upgrade-all-dry-run # Preview without making changes
make check-path          # Validate PATH configuration

# Installation (Makefile)
make install-core
make install-python
make install-node

# Phase 2 API (Python)
from cli_audit import install_tool, bulk_install, upgrade_tool
```

---

## Phase 1: Audit Commands

### Basic Usage

```bash
uv run python audit.py [OPTIONS] [TOOLS...]
```

**Positional Arguments:**
- `TOOLS`: Optional tool names to audit (default: all tools)

**Options** (see `uv run python audit.py --help`):
- `--update`, `--update-local`, `--update-baseline`: Refresh the snapshot, local state, or upstream baseline
- `--versions`: Show multi-version runtime status
- `--reconcile` (with `--all`, `--apply`, `--yes`): Report or remove duplicate installations
- `--install`, `--upgrade`: Placeholders that print a message and exit 1; use the `make install-<tool>` / `make upgrade-<tool>` targets
- `--verbose`, `-v`: Verbose output
- Output and workflow behaviour is controlled via environment variables

### Tool Selection

```bash
# Audit all tools (default)
uv run python audit.py

# Audit specific tools (positional names)
uv run python audit.py ripgrep fd bat
```

### Output Formatting

```bash
# Pipe-delimited table (default)
uv run python audit.py

# Formatted table with column
uv run python audit.py | column -s '|' -t

# Advanced formatting with smart_column
uv run python audit.py | python3 smart_column.py -s '|' -t --right 3,4 --header

# JSON array output
CLI_AUDIT_JSON=1 uv run python audit.py

# JSON with jq filtering
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.status != "UP-TO-DATE")'

# Filter by category
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "security")'
```

### Snapshot Workflow

The tool separates data collection (network) from rendering (offline):

```bash
# 1. Collect data (writes tools_snapshot.json)
CLI_AUDIT_COLLECT=1 uv run python audit.py

# 2. Render from snapshot (no network)
CLI_AUDIT_RENDER=1 uv run python audit.py

# Combined: update if missing, then render
make audit-auto

# Manual workflow
make update  # Collect only
make audit   # Render only
```

**Snapshot File:**
- Default: `tools_snapshot.json` in project root
- Override: `CLI_AUDIT_SNAPSHOT_FILE=/path/to/snapshot.json`

### Offline Mode

```bash
# Use only manual cache (upstream_versions.json)
CLI_AUDIT_OFFLINE=1 uv run python audit.py

# Offline + render from snapshot
CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 uv run python audit.py
```

---

## Environment Variables

### Core Behavior

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_TIMEOUT_SECONDS` | int | `3` | Network timeout for version checks |
| `CLI_AUDIT_MAX_WORKERS` | int | `16` | Parallel worker threads |
| `CLI_AUDIT_OFFLINE` | bool | `0` | Use only manual cache (no network) |
| `CLI_AUDIT_DEBUG` | bool | `0` | Print debug messages to stderr |

### Workflow Modes

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_COLLECT` | bool | `0` | Collect-only mode (write snapshot) |
| `CLI_AUDIT_RENDER` | bool | `0` | Render-only mode (read snapshot) |

### Output Formatting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_JSON` | bool | `0` | Output JSON array instead of table |
| `CLI_AUDIT_LINKS` | bool | `1` | Enable OSC 8 hyperlinks |
| `CLI_AUDIT_EMOJI` | bool | `1` | Use emoji status indicators |
| `CLI_AUDIT_GROUP` | bool | `1` | Group output by category |

### Snapshot Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_SNAPSHOT_FILE` | path | `tools_snapshot.json` | Snapshot file path |
| `CLI_AUDIT_UPSTREAM_FILE` | path | `upstream_versions.json` | Upstream baseline path |

### Tool Selection

There is no environment variable for tool selection; pass tool names as positional arguments (`uv run python audit.py ripgrep fd`).

### Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GITHUB_TOKEN` | string | `` | GitHub personal access token (increases rate limits) |

---

## Makefile Targets

### Audit Workflows

```bash
# Update snapshot (collect-only, network required)
make update

# Render from snapshot (offline)
make audit

# Update if snapshot missing, then render
make audit-auto

# Interactive upgrade guide
make upgrade
```

### System-Wide Upgrade

```bash
# Complete system upgrade (5 stages: data → managers → runtimes → user managers → tools)
make upgrade-all

# Preview upgrade without making changes (dry-run)
make upgrade-all-dry-run

# Check PATH configuration before upgrading
make check-path
```

**5-Stage Workflow:**
1. Refresh version data from upstream
2. Upgrade system package managers (apt, brew, snap, flatpak)
3. Upgrade language runtimes (Python, Node.js, Go, Ruby, Rust)
4. Upgrade user package managers (uv, pipx, npm, pnpm, yarn, cargo, composer, poetry)
5. Upgrade all CLI tools managed by each package manager

**Features:**
- UV migration (auto-migrates pip/pipx packages to uv tools)
- System package detection (skips system-managed tools)
- Comprehensive logging to `logs/upgrade-YYYYMMDD-HHMMSS.log`
- Colored output with statistics summary

**Environment Variables:**
- `DRY_RUN=1` - Preview mode

### Installation Scripts

**Core Tools:**
```bash
make install-core      # fd, fzf, ripgrep, jq, yq, bat, delta, just
```

**Language Stacks:**
```bash
make install-python    # Python toolchain (uv, pipx, poetry)
make install-node      # Node toolchain (nvm, node, npm)
make install-go        # Go toolchain
make install-rust      # Rust toolchain (rustup, cargo)
```

**Infrastructure:**
```bash
make install-aws       # AWS CLI
make install-kubectl   # Kubernetes CLI
make install-terraform # Terraform
make install-ansible   # Ansible
make install-docker    # Docker
make install-brew      # Homebrew (macOS/Linux)
```

### Update Scripts

```bash
./scripts/install_group.sh core update
make upgrade-python
make upgrade-node
make upgrade-go
make upgrade-aws
```

### Uninstall Scripts

```bash
make uninstall-node
make uninstall-rust
```

### Reconciliation

```bash
# Remove duplicate installations, keep preferred
make reconcile-node    # Remove distro Node, keep nvm-managed
make reconcile-rust    # Remove distro Rust, keep rustup-managed
```

### Permissions

```bash
# Make scripts executable
make scripts-perms
```

---

## Phase 2: Python API

Phase 2 provides programmatic installation, upgrade, and reconciliation APIs.

**Quick Start:**

```python
from cli_audit import install_tool, Config, Environment

config = Config()
env = Environment.detect()

result = install_tool(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,
    language="rust",
)
```

**See Also:**
- [PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md) - Complete Phase 2 API documentation
- [README.md](../README.md) - Code examples for installation, upgrades, and reconciliation

---

## Configuration Files

### YAML Configuration

Create `.cli-audit.yml` in your project root, `~/.config/cli-audit/config.yml`, or `/etc/cli-audit/config.yml`.

**Precedence:** Project → User → System → Defaults

**Example:**

```yaml
version: 1

environment:
  mode: workstation  # auto, ci, server, or workstation

tools:
  black:
    version: "24.*"  # Pin to major version
    method: pipx     # Preferred package manager
    fallback: pip    # Fallback if primary fails

  ripgrep:
    version: latest
    method: cargo

preferences:
  reconciliation: aggressive  # parallel or aggressive
  breaking_changes: warn      # accept, warn, or reject
  auto_upgrade: true
  timeout_seconds: 10
  max_workers: 8
  cache_ttl_seconds: 3600     # 1 hour version cache

  bulk:
    fail_fast: false
    auto_rollback: true
    generate_rollback_script: true

  package_managers:
    python:
      - uv
      - pipx
      - pip
    rust:
      - cargo

presets:
  dev-essentials:
    - black
    - ripgrep
    - fd
    - bat
```

**Configuration Validation:**

```python
from cli_audit import load_config, validate_config

config = load_config(custom_path=".my-config.yml")
warnings = validate_config(config)

for warning in warnings:
    print(f"⚠️  {warning}")
```

---

## Output Formats

### Table Format (Default)

```
state|tool|installed|installed_method|latest_upstream|upstream_method
+|fd|9.0.0 (140ms)|apt/dpkg|9.0.0 (220ms)|github
⚠|ripgrep|13.0.0 (120ms)|cargo|14.1.1 (180ms)|github
✗|bat|X|N/A|0.24.0 (200ms)|github
```

**Fields:**
1. **state**: Status indicator
   - `+` or `✓`: Up-to-date
   - `⚠`: Outdated
   - `✗` or `-`: Not installed
   - `?`: Unknown (check failed)

2. **tool**: Tool name
3. **installed**: Local version
4. **installed_method**: Installation source
   - `uv tool`, `pipx/user`, `cargo`, `npm (user)`, `apt/dpkg`, etc.
5. **latest_upstream**: Latest version upstream
6. **upstream_method**: Source of latest version
   - `github`, `pypi`, `crates`, `npm`, `gnu-ftp`, `manual`

### JSON Format

```bash
CLI_AUDIT_JSON=1 uv run python audit.py
```

**Schema:**

```json
{
  "tool": "ripgrep",
  "installed": "13.0.0 (120ms)",
  "installed_version": "13.0.0",
  "installed_method": "cargo",
  "installed_path_resolved": "/home/user/.cargo/bin/rg",
  "classification_reason": "path-under-~/.cargo/bin",
  "installed_path_selected": "/home/user/.cargo/bin/rg",
  "classification_reason_selected": "path-under-~/.cargo/bin",
  "latest_upstream": "14.1.1 (180ms)",
  "latest_version": "14.1.1",
  "upstream_method": "github",
  "status": "OUTDATED",
  "category": "core",
  "description": "Fast search tool"
}
```

**Status Values:**
- `UP-TO-DATE`: Installed version matches latest
- `OUTDATED`: Newer version available
- `NOT INSTALLED`: Tool not found
- `UNKNOWN`: Version check failed

### Snapshot Format

**File:** `tools_snapshot.json`

```json
{
  "__meta__": {
    "schema_version": 1,
    "created_at": "2025-10-13T10:30:00Z",
    "offline": false,
    "count": 50,
    "partial_failures": 2
  },
  "tools": [
    {
      "tool": "ripgrep",
      "installed": "13.0.0",
      "latest_upstream": "14.1.1",
      "status": "OUTDATED",
      ...
    }
  ]
}
```

---

## Common Workflows

### Quick Agent Readiness Check

```bash
# Table scan
uv run python audit.py | column -s '|' -t

# Filter outdated tools
CLI_AUDIT_JSON=1 uv run python audit.py \
  | jq -r '.[] | select(.status != "UP-TO-DATE") | [.tool, .status] | @tsv'

# Security tools only
CLI_AUDIT_JSON=1 uv run python audit.py \
  | jq '.[] | select(.category == "security")'
```

### Offline Development

```bash
# Before going offline: collect snapshot
make update

# Offline: render from snapshot
make audit CLI_AUDIT_OFFLINE=1

# Or combined
make audit-auto CLI_AUDIT_OFFLINE=1
```

### CI/CD Integration

```bash
# Collect fresh data in CI, then render the table
uv run python audit.py --update
uv run python audit.py > audit.txt

# JSON for automation
CLI_AUDIT_JSON=1 uv run python audit.py > audit.json

# Parse results
OUTDATED=$(jq -r '.[] | select(.status == "OUTDATED") | .tool' audit.json)
if [ -n "$OUTDATED" ]; then
    echo "Outdated tools: $OUTDATED"
    exit 1
fi
```

### Custom Tool Selection

```bash
# Python ecosystem only (filter by catalog category)
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "python")'

# Specific tools
uv run python audit.py ripgrep fd bat delta
```

### Performance Optimization

```bash
# Reduce workers for slow network
CLI_AUDIT_MAX_WORKERS=4 uv run python audit.py --update

# Increase the version-probe timeout for slow tools
CLI_AUDIT_TIMEOUT_SECONDS=10 uv run python audit.py --update

# Skip the network entirely: refresh only local state
uv run python audit.py --update-local
```

### Debugging

```bash
# Basic debug output
CLI_AUDIT_DEBUG=1 uv run python audit.py --verbose 2> debug.log

# Debug output while collecting (shows network calls)
make update-debug
```

---

## Troubleshooting

### Network Issues

**Problem:** Timeouts or slow responses

```bash
# Increase timeout
CLI_AUDIT_TIMEOUT_SECONDS=10 uv run python audit.py --update

# Reduce concurrency
CLI_AUDIT_MAX_WORKERS=4 uv run python audit.py --update
```

**Problem:** GitHub rate limits

```bash
# Use personal access token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
uv run python audit.py --update

# Use offline mode
CLI_AUDIT_OFFLINE=1 uv run python audit.py
```

### Missing Tools

**Problem:** Tool shows as "NOT INSTALLED" but is actually installed

```bash
# Check PATH
echo $PATH

# Check whether the shell finds the tool on PATH
command -v mytool

# The audit searches PATH, skipping virtualenv and conda bin directories,
# and also checks ~/.cargo/bin: add the tool's directory to PATH
export PATH="/custom/path/to/tool:$PATH"
```

### Version Detection

**Problem:** Installed version shows as "X" or "unknown"

```bash
# Fresh detection for one tool: the JSON shows installed_version,
# installed_path_selected and installed_method
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 uv run python audit.py mytool

# Check tool's version flag manually
mytool --version
mytool -v
mytool version
```

### Snapshot Issues

**Problem:** Stale snapshot data

```bash
# Force snapshot update
rm tools_snapshot.json
make update

# Or use CLI flags
CLI_AUDIT_COLLECT=1 uv run python audit.py
```

**Problem:** Corrupted snapshot

```bash
# Validate JSON
jq '.' tools_snapshot.json

# Rebuild from scratch
rm tools_snapshot.json upstream_versions.json
make update
```

### Performance

**Problem:** Slow audit execution

```bash
# Debug log of a collection run (it records no per-tool timing)
make update-debug

# Use snapshot workflow
make update  # Once, when needed
make audit   # Fast, offline rendering
```

### Docker Hangs

**Problem:** Docker version check hangs

Each version probe is stopped after `CLI_AUDIT_TIMEOUT_SECONDS` (default `3`):

```bash
CLI_AUDIT_TIMEOUT_SECONDS=3 uv run python audit.py --update
```

---

## Related Documentation

- **[README.md](../README.md)** - Project overview and quick start
- **[PHASE2_API_REFERENCE.md](PHASE2_API_REFERENCE.md)** - Complete Phase 2 API documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing and development guide
- **[INDEX.md](INDEX.md)** - Complete documentation index

---

**Last Updated:** 2025-10-13
**Maintainers:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
