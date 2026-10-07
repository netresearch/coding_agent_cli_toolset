<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
<!-- SPDX-FileCopyrightText: Netresearch DTT GmbH -->

# Quick Reference Guide

Fast lookup for common AI CLI Preparation operations.

## One-Liners

### Basic Operations

```bash
# Fast audit from snapshot (no network, <100ms)
make audit

# Full audit with fresh data (~10s)
make update && make audit

# Offline audit
make audit-offline

# Interactive upgrade guide
make upgrade

# Complete system upgrade (5 stages: data → managers → runtimes → user managers → tools)
make upgrade-all

# Preview system upgrade (dry-run)
make upgrade-all-dry-run

# Check PATH configuration
make check-path

# Single tool check
uv run python audit.py ripgrep | python3 smart_column.py -s "|" -t
```

### Role-Based Audits

There are no role presets; filter the JSON output by catalog category:

```bash
# Python development
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "python")'

# Node.js development
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "node")'

# Security tools
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "security")'

# Infrastructure/DevOps
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "devops")'
```

### JSON Output

```bash
# All tools as JSON
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.'

# Filter outdated tools
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.status == "OUTDATED")'

# Count by status
CLI_AUDIT_JSON=1 uv run python audit.py | jq 'group_by(.status) | map({status: .[0].status, count: length})'

# Tools by installation method
CLI_AUDIT_JSON=1 uv run python audit.py | jq 'group_by(.installed_method) | map({method: .[0].installed_method, count: length})'
```

## Environment Variables Cheat Sheet

### Mode Control

```bash
# Collect-only (write snapshot, no output)
CLI_AUDIT_COLLECT=1 uv run python audit.py

# Render-only (read snapshot, no network)
CLI_AUDIT_RENDER=1 uv run python audit.py

# Offline mode (manual cache only)
CLI_AUDIT_OFFLINE=1 uv run python audit.py
```

### Debug & Trace

```bash
# Basic debug output
CLI_AUDIT_DEBUG=1 uv run python audit.py --verbose

# Debug output while collecting (shows network calls)
CLI_AUDIT_DEBUG=1 uv run python audit.py --update --verbose
```

### Performance Tuning

```bash
# Increase workers (default: 16)
CLI_AUDIT_MAX_WORKERS=32 uv run python audit.py --update

# Adjust version-probe timeout (default: 3s)
CLI_AUDIT_TIMEOUT_SECONDS=5 uv run python audit.py --update
```

### Output Format

```bash
# JSON output
CLI_AUDIT_JSON=1 uv run python audit.py

# Disable emoji icons
CLI_AUDIT_EMOJI=0 uv run python audit.py

# Disable hyperlinks
CLI_AUDIT_LINKS=0 uv run python audit.py
```

## Common Workflows

### First-Time Setup

```bash
# 1. Check current state
uv run python audit.py | python3 smart_column.py -s "|" -t --right 3,4 --header

# 2. Review outdated/missing tools
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.status != "UP-TO-DATE")'

# 3. Use interactive upgrade guide
make upgrade

# 4. Install tools via scripts
make install-python
make install-node
make install-core

# 5. Re-audit until satisfied
make update && make audit
```

### Daily Development

```bash
# Quick check (uses snapshot)
make audit

# Update snapshot weekly
make update

# Check single tool after install
uv run python audit.py new-tool
```

### CI/CD Pipeline

```bash
# Collect snapshot (verbose for logs)
uv run python audit.py --update --verbose

# Cache snapshot artifact
# (upload tools_snapshot.json)

# Render in subsequent jobs
CLI_AUDIT_RENDER=1 uv run python audit.py
```

### Offline Environment Preparation

```bash
# 1. Online machine: Update cache
make update
git add upstream_versions.json tools_snapshot.json
git commit -m "chore: update tool version cache"

# 2. Transfer repository to offline machine

# 3. Offline machine: Use cached data
make audit-offline
```

### Troubleshooting a Tool

```bash
# Debug single tool (fresh local and upstream check, JSON output, snapshot unchanged)
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py --verbose problematic-tool
```

## File Locations

```bash
# Main audit script
audit.py                        # CLI entry point
cli_audit/                      # Audit engine package

# Helper scripts
smart_column.py                 # Column formatting with emoji support
scripts/install_*.sh           # Installation scripts (13 files)

# Cache files
upstream_versions.json           # Manual cache + hints
tools_snapshot.json            # Audit results snapshot

# Build system
Makefile                       # Make targets

# Documentation
README.md                      # User guide
docs/                          # Technical documentation (7 files)
```

## Makefile Targets Quick Reference

```bash
# Auditing
make audit                     # Render from snapshot
make audit-offline             # Offline render with hints
make audit-auto                # Auto-update if snapshot missing
make update                    # Collect fresh data

# Single tool
make audit-ripgrep             # Audit specific tool

# Installation
make install-core              # fd, fzf, ripgrep, jq, yq, bat, delta, just
make install-python            # Python toolchain (via uv)
make install-node              # Node.js (via nvm)
make install-go                # Go runtime
make install-rust              # Rust (via rustup)
make install-aws               # AWS CLI
make install-kubectl           # Kubernetes CLI
make install-terraform         # Terraform
make install-docker            # Docker
make install-ansible           # Ansible

# Upgrades
make upgrade-python            # Update Python toolchain
make upgrade-node              # Update Node.js
make upgrade-go                # Update Go
make upgrade                   # Interactive upgrade guide

# Reconciliation
make reconcile-node            # Switch to nvm-managed Node
make reconcile-rust            # Switch to rustup-managed Rust

# Utilities
make lint                      # Run pyflakes
make scripts-perms             # Fix script permissions
```

## Data File Schemas

### upstream_versions.json (committed)

```json
{
  "__meta__": {
    "schema_version": 2,
    "baseline_updated_at": "2025-12-21T12:00:00Z",
    "source": "github/pypi/npm/crates API"
  },
  "versions": {
    "ripgrep": {
      "latest_version": "14.1.1",
      "latest_url": "https://github.com/BurntSushi/ripgrep/releases/tag/14.1.1",
      "upstream_method": "gh"
    }
  }
}
```

### local_state.json (gitignored)

```json
{
  "__meta__": {
    "schema_version": 2,
    "collected_at": "2025-12-21T12:00:00Z",
    "hostname": "myhost"
  },
  "tools": {
    "ripgrep": {
      "installed_version": "14.1.1",
      "installed_method": "cargo",
      "installed_path": "/home/user/.cargo/bin/rg"
    }
  }
}
```

## Status Icons

| Icon | Status | Meaning |
|------|--------|---------|
| ✓ / ✅ | UP-TO-DATE | Installed version matches latest |
| ↑ / ⬆️ | OUTDATED | Newer version available |
| ✗ / ❌ | NOT INSTALLED | Tool not found on PATH |
| ? / ❓ | UNKNOWN | Version detection failed |

## Common jq Queries

```bash
# List all tools
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[].tool'

# Outdated tools with versions
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.status == "OUTDATED") | {tool, installed: .installed_version, latest: .latest_version}'

# Tools by category
CLI_AUDIT_JSON=1 uv run python audit.py | jq 'group_by(.category) | map({category: .[0].category, tools: map(.tool)})'

# Installation methods used
CLI_AUDIT_JSON=1 uv run python audit.py | jq '[.[].installed_method] | unique'

# Count by installation method
CLI_AUDIT_JSON=1 uv run python audit.py | jq 'group_by(.installed_method) | map({method: .[0].installed_method, count: length})'

# Security tools only
CLI_AUDIT_JSON=1 uv run python audit.py | jq '.[] | select(.category == "security")'
```

## Debugging Commands

```bash
# Check Python version
python3 --version

# Verify snapshot exists
ls -lh tools_snapshot.json

# Validate JSON files
jq '.' upstream_versions.json
jq '.__meta__' tools_snapshot.json

# Check git status
git status
git log --oneline -5

# Test single upstream fetch and classification (JSON output, snapshot unchanged)
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py --verbose ripgrep
```

## Performance Benchmarks

```bash
# Measure collection time
time CLI_AUDIT_COLLECT=1 uv run python audit.py

# Measure render time
time CLI_AUDIT_RENDER=1 uv run python audit.py

# Profile single tool
time CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 uv run python audit.py ripgrep
```

## Quick Fixes

### Network Timeout Issues

```bash
# Increase timeout
CLI_AUDIT_TIMEOUT_SECONDS=10 uv run python audit.py --update

# Use offline mode
CLI_AUDIT_OFFLINE=1 uv run python audit.py
```

### GitHub Rate Limiting

```bash
# Set GitHub token
export GITHUB_TOKEN=ghp_your_token_here
uv run python audit.py --update
```

### Version Detection Failures

```bash
# Debug detection
CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 uv run python audit.py --verbose tool-name

# Check PATH
echo $PATH | tr ':' '\n'
which tool-name
```

### Cache Corruption

```bash
# Remove corrupted caches
rm upstream_versions.json tools_snapshot.json

# Regenerate
make update
```

## See Also

- **[INDEX.md](INDEX.md)** - Full documentation index
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Detailed Makefile target reference
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Comprehensive problem solving
- **[API_REFERENCE.md](API_REFERENCE.md)** - Environment variables and functions
