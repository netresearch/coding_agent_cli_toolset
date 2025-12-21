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
python3 cli_audit.py --only ripgrep | python3 smart_column.py -s "|" -t
```

### Role-Based Audits

```bash
# AI agent essentials
make audit-offline-agent-core

# Python development
make audit-offline-python-core

# Node.js development
make audit-offline-node-core

# Security tools
make audit-offline-security-core

# Infrastructure/DevOps
make audit-offline-infra-core
```

### JSON Output

```bash
# All tools as JSON
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'

# Filter outdated tools
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.status == "OUTDATED")'

# Count by status
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq 'group_by(.status) | map({status: .[0].status, count: length})'

# Tools by installation method
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq 'group_by(.installed_method) | map({method: .[0].installed_method, count: length})'
```

## Environment Variables Cheat Sheet

### Mode Control

```bash
# Collect-only (write snapshot, no output)
CLI_AUDIT_COLLECT=1 python3 cli_audit.py

# Render-only (read snapshot, no network)
CLI_AUDIT_RENDER=1 python3 cli_audit.py

# Offline mode (manual cache only)
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py

# Fast mode (skip slow operations)
CLI_AUDIT_FAST=1 python3 cli_audit.py
```

### Debug & Trace

```bash
# Basic debug output
CLI_AUDIT_DEBUG=1 python3 cli_audit.py

# Detailed trace
CLI_AUDIT_TRACE=1 python3 cli_audit.py

# Network trace
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py

# Progress messages
CLI_AUDIT_PROGRESS=1 python3 cli_audit.py

# All debugging
CLI_AUDIT_DEBUG=1 CLI_AUDIT_TRACE=1 CLI_AUDIT_TRACE_NET=1 CLI_AUDIT_PROGRESS=1 python3 cli_audit.py
```

### Performance Tuning

```bash
# Increase workers (default: 16)
CLI_AUDIT_MAX_WORKERS=32 python3 cli_audit.py

# Adjust timeout (default: 3s)
CLI_AUDIT_TIMEOUT_SECONDS=5 python3 cli_audit.py

# More HTTP retries (default: 2)
CLI_AUDIT_HTTP_RETRIES=5 python3 cli_audit.py
```

### Output Format

```bash
# JSON output
CLI_AUDIT_JSON=1 python3 cli_audit.py

# Disable emoji icons
CLI_AUDIT_EMOJI=0 python3 cli_audit.py

# Disable hyperlinks
CLI_AUDIT_LINKS=0 python3 cli_audit.py

# Hide timing info
CLI_AUDIT_TIMINGS=0 python3 cli_audit.py

# Disable hints
CLI_AUDIT_HINTS=0 python3 cli_audit.py
```

## Common Workflows

### First-Time Setup

```bash
# 1. Check current state
python3 cli_audit.py | python3 smart_column.py -s "|" -t --right 3,5 --header

# 2. Review outdated/missing tools
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.status != "UP-TO-DATE")'

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
python3 cli_audit.py --only new-tool
```

### CI/CD Pipeline

```bash
# Collect snapshot (verbose for logs)
CLI_AUDIT_COLLECT=1 CLI_AUDIT_PROGRESS=1 python3 cli_audit.py

# Cache snapshot artifact
# (upload tools_snapshot.json)

# Render in subsequent jobs
CLI_AUDIT_RENDER=1 python3 cli_audit.py
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
# Debug single tool
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only problematic-tool

# Check version detection
CLI_AUDIT_TRACE=1 python3 cli_audit.py --only problematic-tool 2>&1 | grep "version"

# Test upstream fetch
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only problematic-tool 2>&1 | grep -A5 "http_fetch"
```

## File Locations

```bash
# Main audit script
cli_audit.py                    # 2,375 lines, audit engine

# Helper scripts
smart_column.py                 # Column formatting with emoji support
scripts/install_*.sh           # Installation scripts (13 files)

# Cache files
upstream_versions.json           # Manual cache + hints
tools_snapshot.json            # Audit results snapshot

# Build system
Makefile                       # Make targets
package.json                   # Claude Code dependency

# Documentation
README.md                      # User guide
docs/                          # Technical documentation (7 files)
claudedocs/                    # AI agent context (2 files)
```

## Makefile Targets Quick Reference

```bash
# Auditing
make audit                     # Render from snapshot
make audit-offline             # Offline render with hints
make audit-auto                # Auto-update if snapshot missing
make update                    # Collect fresh data

# Role-specific
make audit-offline-agent-core  # AI agent essentials
make audit-offline-python-core # Python tools
make audit-offline-node-core   # Node.js tools
make audit-offline-go-core     # Go tools
make audit-offline-security-core # Security tools

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
make update-python             # Update Python toolchain
make update-node               # Update Node.js
make update-go                 # Update Go
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
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[].tool'

# Outdated tools with versions
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.status == "OUTDATED") | {tool, installed: .installed_version, latest: .latest_version}'

# Tools by category
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq 'group_by(.category) | map({category: .[0].category, tools: map(.tool)})'

# Installation methods used
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '[.[].installed_method] | unique'

# Count by installation method
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq 'group_by(.installed_method) | map({method: .[0].installed_method, count: length})'

# Security tools only
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.category == "security")'
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

# Test single upstream fetch
CLI_AUDIT_TRACE_NET=1 python3 cli_audit.py --only ripgrep 2>&1 | grep "github"

# Check classification
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only python 2>&1 | grep "classify"
```

## Performance Benchmarks

```bash
# Measure collection time
time CLI_AUDIT_COLLECT=1 python3 cli_audit.py

# Measure render time
time CLI_AUDIT_RENDER=1 python3 cli_audit.py

# Profile single tool
time python3 cli_audit.py --only ripgrep
```

## Quick Fixes

### Network Timeout Issues

```bash
# Increase timeout
CLI_AUDIT_TIMEOUT_SECONDS=10 python3 cli_audit.py

# More retries
CLI_AUDIT_HTTP_RETRIES=5 python3 cli_audit.py

# Use offline mode
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

### GitHub Rate Limiting

```bash
# Set GitHub token
export GITHUB_TOKEN=ghp_your_token_here
python3 cli_audit.py
```

### Version Detection Failures

```bash
# Debug detection
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only tool-name

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
