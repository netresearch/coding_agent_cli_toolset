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
python3 cli_audit.py | column -s '|' -t

# Specific tools only
python3 cli_audit.py ripgrep fd bat

# JSON output
CLI_AUDIT_JSON=1 python3 cli_audit.py

# Offline mode
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py

# Snapshot-based workflow
make update      # Collect data (network required)
make audit       # Render table (offline)
make audit-auto  # Update if missing, then render

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
python3 cli_audit.py [OPTIONS] [TOOLS...]
```

**Positional Arguments:**
- `TOOLS`: Optional tool names to audit (default: all tools)

**Options:**
- `--only TOOL [TOOL ...]`: Select specific tools (alias: `--tool`)
- No flags for most options - controlled via environment variables

### Tool Selection

```bash
# Audit all tools (default)
python3 cli_audit.py

# Audit specific tools
python3 cli_audit.py ripgrep fd bat

# Using --only flag
python3 cli_audit.py --only ripgrep fd bat

# Preset categories
python3 cli_audit.py --only agent-core
python3 cli_audit.py --only python-core
python3 cli_audit.py --only node-core
python3 cli_audit.py --only go-core
python3 cli_audit.py --only infra-core
python3 cli_audit.py --only security-core
python3 cli_audit.py --only data-core
```

### Output Formatting

```bash
# Pipe-delimited table (default)
python3 cli_audit.py

# Formatted table with column
python3 cli_audit.py | column -s '|' -t

# Advanced formatting with smart_column
python3 cli_audit.py | python3 smart_column.py -s '|' -t --right 3,5 --header

# JSON array output
CLI_AUDIT_JSON=1 python3 cli_audit.py

# JSON with jq filtering
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.status != "UP-TO-DATE")'

# Filter by category
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.category == "security")'
```

### Snapshot Workflow

The tool separates data collection (network) from rendering (offline):

```bash
# 1. Collect data (writes tools_snapshot.json)
CLI_AUDIT_COLLECT=1 python3 cli_audit.py

# 2. Render from snapshot (no network)
CLI_AUDIT_RENDER=1 python3 cli_audit.py

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
# Use only manual cache (latest_versions.json)
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py

# Offline + render from snapshot
CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 python3 cli_audit.py
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
| `CLI_AUDIT_TRACE` | bool | `0` | Ultra-verbose tracing |
| `CLI_AUDIT_TRACE_NET` | bool | `0` | Trace network operations |

### Workflow Modes

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_COLLECT` | bool | `0` | Collect-only mode (write snapshot) |
| `CLI_AUDIT_RENDER` | bool | `0` | Render-only mode (read snapshot) |
| `CLI_AUDIT_FAST` | bool | `0` | Fast mode (skip slow checks) |
| `CLI_AUDIT_STREAM` | bool | `0` | Stream output as tools complete |

### Output Formatting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_JSON` | bool | `0` | Output JSON array instead of table |
| `CLI_AUDIT_LINKS` | bool | `1` | Enable OSC 8 hyperlinks |
| `CLI_AUDIT_EMOJI` | bool | `1` | Use emoji status indicators |
| `CLI_AUDIT_TIMINGS` | bool | `1` | Show timing information |
| `CLI_AUDIT_SORT` | string | `order` | Sort mode: `order` or `alpha` |
| `CLI_AUDIT_GROUP` | bool | `1` | Group output by category |
| `CLI_AUDIT_HINTS` | bool | `1` | Show remediation hints |

### Snapshot Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_SNAPSHOT_FILE` | path | `tools_snapshot.json` | Snapshot file path |
| `CLI_AUDIT_MANUAL_FILE` | path | `latest_versions.json` | Manual cache path |
| `CLI_AUDIT_WRITE_MANUAL` | bool | `1` | Auto-update manual cache |
| `CLI_AUDIT_MANUAL_FIRST` | bool | `0` | Try manual cache before network |

### Progress and Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_PROGRESS` | bool | `0` | Show progress messages |
| `CLI_AUDIT_SLOW_MS` | int | `2000` | Threshold for slow operation warnings |

### Rate Limiting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_HOST_CAP_GITHUB` | int | `4` | Max concurrent GitHub requests |
| `CLI_AUDIT_HOST_CAP_GITHUB_API` | int | `4` | Max concurrent GitHub API requests |
| `CLI_AUDIT_HOST_CAP_NPM` | int | `4` | Max concurrent npm registry requests |
| `CLI_AUDIT_HOST_CAP_CRATES` | int | `4` | Max concurrent crates.io requests |
| `CLI_AUDIT_HOST_CAP_GNU` | int | `2` | Max concurrent GNU FTP requests |

### HTTP Behavior

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_HTTP_RETRIES` | int | `2` | Number of HTTP retry attempts |
| `CLI_AUDIT_BACKOFF_BASE` | float | `0.2` | Base delay for exponential backoff (seconds) |
| `CLI_AUDIT_BACKOFF_JITTER` | float | `0.1` | Jitter for backoff randomization (seconds) |

### Feature Toggles

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_DOCKER_INFO` | bool | `1` | Check Docker version (may hang in some environments) |
| `CLI_AUDIT_VALIDATE_MANUAL` | bool | `1` | Validate manual cache entries |
| `CLI_AUDIT_DPKG_CACHE_LIMIT` | int | `1024` | Max entries in dpkg cache |

### Tool Selection

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLI_AUDIT_ONLY` | string | `` | Comma-separated tool names to audit |

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
make update-core
make update-python
make update-node
make update-go
make update-aws
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
3. **installed**: Local version (with timing if `CLI_AUDIT_TIMINGS=1`)
4. **installed_method**: Installation source
   - `uv tool`, `pipx/user`, `cargo`, `npm (user)`, `apt/dpkg`, etc.
5. **latest_upstream**: Latest version upstream
6. **upstream_method**: Source of latest version
   - `github`, `pypi`, `crates`, `npm`, `gnu-ftp`, `manual`

### JSON Format

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py
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
python3 cli_audit.py | column -s '|' -t

# Filter outdated tools
CLI_AUDIT_JSON=1 python3 cli_audit.py \
  | jq -r '.[] | select(.status != "UP-TO-DATE") | [.tool, .status] | @tsv'

# Security tools only
CLI_AUDIT_JSON=1 python3 cli_audit.py \
  | jq '.[] | select(.category == "security")'
```

### Offline Development

```bash
# Before going offline: collect snapshot
make update

# Offline: render from snapshot
CLI_AUDIT_OFFLINE=1 make audit

# Or combined
CLI_AUDIT_OFFLINE=1 make audit-auto
```

### CI/CD Integration

```bash
# Fast audit in CI (no timing info, fail on outdated)
CLI_AUDIT_TIMINGS=0 CLI_AUDIT_FAST=1 python3 cli_audit.py > audit.txt

# JSON for automation
CLI_AUDIT_JSON=1 python3 cli_audit.py > audit.json

# Parse results
OUTDATED=$(jq -r '.[] | select(.status == "OUTDATED") | .tool' audit.json)
if [ -n "$OUTDATED" ]; then
    echo "Outdated tools: $OUTDATED"
    exit 1
fi
```

### Custom Tool Selection

```bash
# Python ecosystem only
python3 cli_audit.py --only python-core

# Multiple categories
python3 cli_audit.py --only agent-core security-core

# Specific tools
python3 cli_audit.py ripgrep fd bat delta

# Using environment variable
CLI_AUDIT_ONLY="ripgrep,fd,bat" python3 cli_audit.py
```

### Performance Optimization

```bash
# Fast mode (skip slow checks)
CLI_AUDIT_FAST=1 python3 cli_audit.py

# Reduce workers for slow network
CLI_AUDIT_MAX_WORKERS=4 python3 cli_audit.py

# Increase timeout for slow hosts
CLI_AUDIT_TIMEOUT_SECONDS=10 python3 cli_audit.py

# Use manual cache first (faster)
CLI_AUDIT_MANUAL_FIRST=1 python3 cli_audit.py
```

### Debugging

```bash
# Basic debug output
CLI_AUDIT_DEBUG=1 python3 cli_audit.py 2> debug.log

# Verbose tracing
CLI_AUDIT_TRACE=1 python3 cli_audit.py 2> trace.log

# Network tracing
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py 2> network.log

# Progress messages
CLI_AUDIT_PROGRESS=1 python3 cli_audit.py
```

---

## Troubleshooting

### Network Issues

**Problem:** Timeouts or slow responses

```bash
# Increase timeout
CLI_AUDIT_TIMEOUT_SECONDS=10 python3 cli_audit.py

# Reduce concurrency
CLI_AUDIT_MAX_WORKERS=4 python3 cli_audit.py

# Cap per-host requests
CLI_AUDIT_HOST_CAP_GITHUB=2 CLI_AUDIT_HOST_CAP_NPM=2 python3 cli_audit.py
```

**Problem:** GitHub rate limits

```bash
# Use personal access token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
python3 cli_audit.py

# Use offline mode
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

### Missing Tools

**Problem:** Tool shows as "NOT INSTALLED" but is actually installed

```bash
# Check PATH
echo $PATH

# Check extra search paths
CLI_AUDIT_DEBUG=1 python3 cli_audit.py 2>&1 | grep -i "search"

# Tool-specific paths (edit cli_audit.py)
TOOL_SPECIFIC_PATHS = {
    "mytool": ["/custom/path/to/tool"],
}
```

### Version Detection

**Problem:** Installed version shows as "X" or "unknown"

```bash
# Debug version detection
CLI_AUDIT_DEBUG=1 python3 cli_audit.py mytool 2> debug.log

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
CLI_AUDIT_COLLECT=1 python3 cli_audit.py
```

**Problem:** Corrupted snapshot

```bash
# Validate JSON
jq '.' tools_snapshot.json

# Rebuild from scratch
rm tools_snapshot.json latest_versions.json
make update
```

### Performance

**Problem:** Slow audit execution

```bash
# Check slow operations
CLI_AUDIT_TRACE=1 python3 cli_audit.py 2>&1 | grep "slow"

# Use fast mode
CLI_AUDIT_FAST=1 python3 cli_audit.py

# Use snapshot workflow
make update  # Once, when needed
make audit   # Fast, offline rendering
```

### Docker Hangs

**Problem:** Docker version check hangs

```bash
# Disable Docker info
CLI_AUDIT_DOCKER_INFO=0 python3 cli_audit.py
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
