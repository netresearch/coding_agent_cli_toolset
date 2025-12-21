# Deployment Guide

## Overview

This guide covers operational aspects of AI CLI Preparation: Makefile targets, installation scripts, snapshot workflows, offline mode configuration, environment variables, CI/CD integration, and performance tuning.

## Quick Start

```bash
# Render audit from snapshot (no network, fast)
make audit

# Update snapshot with latest data (verbose)
make update

# Auto-update if snapshot missing, then render
make audit-auto

# Run interactive upgrade guide
make upgrade
```

## Makefile Targets Reference

### Core Audit Targets

#### `make audit`
Render audit table from snapshot (render-only mode, no network).

**Environment:**
- `CLI_AUDIT_RENDER=1` - Render-only mode
- `CLI_AUDIT_GROUP=0` - No category grouping
- `CLI_AUDIT_HINTS=1` - Show remediation hints
- `CLI_AUDIT_LINKS=1` - Enable hyperlinks
- `CLI_AUDIT_EMOJI=1` - Use emoji status icons

**Use Case:** Fast local audit from cached snapshot, safe to run repeatedly.

**Speed:** <100ms (pure JSON read + format)

```bash
make audit
```

#### `make audit-offline`
Offline audit with cache-only mode (no upstream queries).

**Environment:**
- All settings from `make audit`
- `CLI_AUDIT_OFFLINE=1` - Force offline mode

**Use Case:** Disconnected environments, air-gapped systems, CI cache validation.

```bash
make audit-offline
```

#### `make audit-auto`
Conditionally update snapshot if missing/stale, then render.

**Logic:**
1. Check if `tools_snapshot.json` exists
2. If missing: Run `CLI_AUDIT_COLLECT=1` to fetch data
3. Render audit table from snapshot

**Use Case:** First-run scenarios, post-checkout, automated pipelines.

```bash
make audit-auto
```

#### `make update`
Collect-only mode: fetch upstream data, write snapshot, no output rendering.

**Environment:**
- `CLI_AUDIT_COLLECT=1` - Collect-only mode
- `CLI_AUDIT_DEBUG=1` - Debug messages
- `CLI_AUDIT_PROGRESS=1` - Progress updates

**Use Case:** Refresh snapshot with latest data, troubleshoot network issues.

**Output:** Writes `tools_snapshot.json`, prints verbose progress to stderr.

```bash
make update
```

#### `make upgrade`
Interactive remediation guide (renamed from `guide`).

**Behavior:**
1. Runs full audit
2. Identifies outdated/missing tools
3. Prompts for installation/update actions
4. Executes selected remediation steps

**Use Case:** One-stop tool for bringing system up to date.

```bash
make upgrade
```

### System-Wide Upgrade Targets

#### `make upgrade-all`
Complete system upgrade in 5 orchestrated stages.

**Workflow:**
1. **Stage 1: Refresh Data** - Update version snapshot from upstream sources
2. **Stage 2: Upgrade Package Managers** - Self-update system package managers (apt, brew, snap, flatpak)
3. **Stage 3: Upgrade Language Runtimes** - Update core runtimes (Python, Node.js, Go, Ruby, Rust)
4. **Stage 4: Upgrade User Package Managers** - Update language-specific managers (uv, pipx, npm, pnpm, yarn, cargo, composer, poetry)
5. **Stage 5: Upgrade Tools** - Upgrade all CLI tools managed by each package manager

**Features:**
- Comprehensive logging to `logs/upgrade-YYYYMMDD-HHMMSS.log`
- Colored terminal output with progress tracking
- Version and location info for successful upgrades
- UV migration support (auto-migrates pip/pipx packages to uv tools)
- System package detection (skips system-managed tools, suggests reconcile)
- Statistics summary (upgraded/failed/skipped counts)
- Dry-run mode available

**Use Case:** Complete development environment upgrade, ensuring all tools across all package managers are current.

**Duration:** 5-15 minutes depending on number of outdated packages.

```bash
# Full system upgrade
make upgrade-all

# Preview what would be upgraded (dry-run)
make upgrade-all-dry-run
```

**Output Example:**
```
[1/5] Stage 1: Refresh version data
  ✓ Updated snapshot (64 tools checked)

[2/5] Stage 2: Upgrade package managers
  ✓ apt (upgraded 12 packages)
  ⏭ homebrew (not installed)
  ✓ snap (2.63 at /usr/bin/snap)

[3/5] Stage 3: Upgrade language runtimes
  ✓ python (3.12.7 → 3.12.8)
  ✓ node (20.10.0 → 20.11.0)
  ⏭ go (already latest: 1.22.0)

[4/5] Stage 4: Upgrade user package managers
  ✓ uv (0.4.30 → 0.5.0)
  ✓ pipx (1.7.1 → 1.8.0)
  → Migrating pip packages to uv...
    ✓ black migrated to uv tool
    ✓ ruff migrated to uv tool

[5/5] Stage 5: Upgrade CLI tools
  ✓ Upgraded 8 uv tools
  ✓ Upgraded 15 npm packages
  ✓ Upgraded 3 cargo binaries

Summary: 45 upgraded, 12 skipped, 2 failed
Duration: 8m 32s
Log: logs/upgrade-20251018-073045.log
```

**Environment Variables:**
- `DRY_RUN=1` - Preview mode without making changes
- `SKIP_SYSTEM=1` - Skip system package managers (apt, brew, snap, flatpak)
- `VERBOSE=1` - Detailed output for debugging

**Advanced:**
```bash
# Direct script execution with options
DRY_RUN=1 VERBOSE=1 bash scripts/upgrade_all.sh

# Skip system package managers
SKIP_SYSTEM=1 make upgrade-all

# Check PATH configuration before upgrading
make check-path
```

#### `make check-path`
Validate PATH configuration for all package managers.

**Behavior:**
- Checks if package manager binaries are in PATH
- Validates PATH ordering (user bins before system bins)
- Identifies potential shadowing issues
- Provides remediation suggestions

**Use Case:** Diagnose PATH issues before or after system upgrade.

```bash
make check-path
```

### Tool-Specific Audit Targets

#### `make audit-TOOLNAME`
Audit single tool from snapshot.

```bash
# Examples
make audit-python
make audit-ripgrep
make audit-docker
```

#### `make audit-offline-CATEGORY`
Audit category subset in offline mode.

**Available Categories:**
- `agent-core` - Core tools for AI agents
- `python-core` - Python runtime and package managers
- `node-core` - Node.js runtime and package managers
- `go-core` - Go runtime and tools
- `infra-core` - Cloud/infrastructure tools
- `security-core` - Security scanning tools
- `data-core` - Data processing tools

```bash
# Examples
make audit-offline-python-core
make audit-offline-security-core
make audit-offline-infra-core
```

### Installation Script Targets

#### Core Language Toolchains

```bash
# Set script permissions (run once)
make scripts-perms

# Install core tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
make install-core

# Install language stacks
make install-python  # pip, pipx, poetry, uv
make install-node    # nvm, npm, pnpm, yarn
make install-go      # Go toolchain
make install-rust    # Rust via rustup

# Install cloud/infra tools
make install-aws        # AWS CLI v2
make install-kubectl    # Kubernetes CLI
make install-terraform  # Terraform
make install-ansible    # Ansible
make install-docker     # Docker Engine
make install-brew       # Homebrew (Linux/macOS)
```

#### Update Existing Tools

All install scripts support `update` action:

```bash
make update-core
make update-python
make update-node
make update-go
make update-aws
make update-rust
```

#### Uninstall Tools

```bash
make uninstall-node
make uninstall-rust
make uninstall-docker
```

#### Reconcile Installation Method

Switch from system package to preferred method:

```bash
# Example: Remove distro Node, switch to nvm-managed
make reconcile-node

# Example: Remove distro Rust, switch to rustup
make reconcile-rust
```

### Utility Targets

#### `make lint`
Run basic lint checks with pyflakes (optional).

```bash
make lint
```

#### `make fmt`
Placeholder for formatting (no-op currently).

```bash
make fmt
```

#### `make help`
Display available targets and descriptions.

```bash
make help
```

## Installation Script Usage

### Script Structure

All scripts under `scripts/` follow consistent patterns:

```bash
./scripts/install_COMPONENT.sh [ACTION] [TOOL]
```

**Actions:**
- `install` (default) - Install new tools
- `update` - Update existing tools
- `uninstall` - Remove tools
- `reconcile` - Switch installation methods

**Tool:** Optional, install/update specific tool only

### Script Behavior

#### Install Action

**What it does:**
1. Detects OS and architecture
2. Downloads latest upstream releases
3. Installs to `~/.local/bin` or `/usr/local/bin`
4. Updates PATH if needed
5. Verifies installation

**Example:**
```bash
./scripts/install_core.sh install
# Installs all core tools

./scripts/install_core.sh install fd
# Installs only fd
```

#### Update Action

**What it does:**
1. Checks current installed version
2. Fetches latest upstream version
3. Skips if already up-to-date
4. Downloads and replaces if outdated
5. Preserves configuration

**Example:**
```bash
./scripts/install_python.sh update
# Updates pip, pipx, poetry, uv if outdated
```

#### Uninstall Action

**What it does:**
1. Removes binaries from install directories
2. Optionally removes config/data directories
3. Cleans up PATH modifications
4. Preserves user data by default

**Example:**
```bash
./scripts/install_node.sh uninstall
# Removes nvm, node, npm, pnpm, yarn
```

#### Reconcile Action

**What it does:**
1. Identifies installation method conflicts
2. Removes system/distro packages
3. Installs via preferred method
4. Validates final state

**Example:**
```bash
./scripts/install_rust.sh reconcile
# Removes apt-installed rust, installs via rustup
```

## Snapshot Workflow Patterns

The tool separates data collection (network) from rendering (local) for efficiency and offline support.

### Workflow Modes

#### Normal Mode (Default)
Full audit: collect + render in single command.

```bash
python3 cli_audit.py
```

#### Collect-Only Mode
Fetch data, write snapshot, no output.

```bash
CLI_AUDIT_COLLECT=1 python3 cli_audit.py
```

**Output:** Writes `tools_snapshot.json`

**Use Case:** CI cache updates, scheduled data refresh, troubleshooting.

#### Render-Only Mode
Read snapshot, format output, no network.

```bash
CLI_AUDIT_RENDER=1 python3 cli_audit.py
```

**Use Case:** Repeated local checks, offline environments, fast queries.

### Snapshot File Structure

**Default Path:** `tools_snapshot.json` (override with `CLI_AUDIT_SNAPSHOT_FILE`)

**Schema:**
```json
{
  "__meta__": {
    "schema_version": 1,
    "created_at": "2025-10-09T12:34:56Z",
    "offline": false,
    "count": 50,
    "partial_failures": 2
  },
  "tools": [
    {
      "tool": "ripgrep",
      "installed": "14.1.1 (150ms)",
      "installed_version": "14.1.1",
      "installed_method": "rustup/cargo",
      "installed_path_resolved": "/home/user/.cargo/bin/rg",
      "installed_path_selected": "/home/user/.cargo/bin/rg",
      "classification_reason": "path-under-~/.cargo/bin",
      "classification_reason_selected": "path-under-~/.cargo/bin",
      "latest_upstream": "14.1.1 (220ms)",
      "latest_version": "14.1.1",
      "upstream_method": "github",
      "status": "UP-TO-DATE",
      "tool_url": "https://github.com/BurntSushi/ripgrep",
      "latest_url": "https://github.com/BurntSushi/ripgrep/releases/tag/14.1.1"
    }
  ]
}
```

### Snapshot Update Strategies

#### Manual Update
Run periodically or when tools change.

```bash
make update
```

#### Automatic Update (Makefile)
Use `audit-auto` target to update only when missing.

```bash
make audit-auto
```

#### Scheduled Update (Cron)
Update snapshot nightly for fresh data.

```bash
# Crontab entry
0 2 * * * cd /path/to/project && make update
```

#### CI Cache Strategy
Store snapshot as CI artifact, update weekly.

```yaml
# GitHub Actions example
- name: Restore snapshot cache
  uses: actions/cache@v3
  with:
    path: tools_snapshot.json
    key: tools-snapshot-${{ runner.os }}-${{ github.run_number }}
    restore-keys: tools-snapshot-${{ runner.os }}-

- name: Update snapshot
  run: make update
```

## Offline Mode Configuration

### Enabling Offline Mode

**Environment Variable:**
```bash
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py
```

**Makefile:**
```bash
make audit-offline
```

### Offline Mode Behavior

**What Changes:**
- No upstream API calls (GitHub, PyPI, crates.io, npm)
- Uses `upstream_versions.json` exclusively for version data
- Marks upstream method as `manual`
- Displays `(offline)` in readiness summary

**What Still Works:**
- Local version detection
- Installation method classification
- Status comparison (installed vs cached upstream)
- Full audit table/JSON output

### Preparing for Offline Use

1. **Update manual cache online:**
```bash
make update
# Populates upstream_versions.json with current data
```

2. **Commit manual cache:**
```bash
git add upstream_versions.json
git commit -m "chore: update manual version cache"
```

3. **Verify offline operation:**
```bash
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py --only python
```

### Offline Cache Management

**Data Files:**
- `upstream_versions.json` - Latest available versions (committed)
- `local_state.json` - Machine-specific state (gitignored)

**Update Commands:**
- `python audit.py --update-baseline` - Refresh upstream versions
- `python audit.py --update-local` - Refresh local state

## Environment Variable Configuration

### Production Environment Template

**File:** `.env` (gitignored)

```bash
# Mode Control
CLI_AUDIT_OFFLINE=0
CLI_AUDIT_COLLECT=0
CLI_AUDIT_RENDER=0

# Output
CLI_AUDIT_JSON=0
CLI_AUDIT_LINKS=1
CLI_AUDIT_EMOJI=1
CLI_AUDIT_TIMINGS=1
CLI_AUDIT_GROUP=1
CLI_AUDIT_HINTS=1

# Performance
CLI_AUDIT_MAX_WORKERS=16
CLI_AUDIT_TIMEOUT_SECONDS=3
CLI_AUDIT_FAST=0

# Network
CLI_AUDIT_HTTP_RETRIES=2
CLI_AUDIT_BACKOFF_BASE=0.2
CLI_AUDIT_BACKOFF_JITTER=0.1
GITHUB_TOKEN=ghp_your_token_here

# Debugging (disable in production)
CLI_AUDIT_DEBUG=0
CLI_AUDIT_TRACE=0
CLI_AUDIT_TRACE_NET=0
CLI_AUDIT_PROGRESS=0

# Paths
CLI_AUDIT_SNAPSHOT_FILE=tools_snapshot.json
CLI_AUDIT_MANUAL_FILE=upstream_versions.json

# Cache
CLI_AUDIT_WRITE_MANUAL=1
CLI_AUDIT_MANUAL_FIRST=0
```

### Environment Profiles

#### Development Profile

**File:** `.env.development`

```bash
CLI_AUDIT_DEBUG=1
CLI_AUDIT_PROGRESS=1
CLI_AUDIT_TRACE=1
CLI_AUDIT_MAX_WORKERS=8
CLI_AUDIT_TIMEOUT_SECONDS=5
```

**Usage:**
```bash
set -a; source .env.development; set +a
make audit
```

#### CI Profile

**File:** `.env.ci`

```bash
CLI_AUDIT_OFFLINE=0
CLI_AUDIT_JSON=1
CLI_AUDIT_TIMINGS=0
CLI_AUDIT_EMOJI=0
CLI_AUDIT_LINKS=0
CLI_AUDIT_MAX_WORKERS=4
CLI_AUDIT_TIMEOUT_SECONDS=10
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}
```

#### Production Profile

**File:** `.env.production`

```bash
CLI_AUDIT_RENDER=1
CLI_AUDIT_OFFLINE=1
CLI_AUDIT_JSON=1
CLI_AUDIT_DEBUG=0
CLI_AUDIT_FAST=1
```

## CI/CD Integration

### GitHub Actions

#### Basic Audit Workflow

```yaml
name: Tool Audit

on:
  schedule:
    - cron: '0 8 * * 1'  # Weekly on Monday
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Run audit
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CLI_AUDIT_JSON: 1
        run: |
          python3 cli_audit.py > audit_results.json

      - name: Check for outdated tools
        run: |
          jq -r '.[] | select(.status == "OUTDATED") | "\(.tool): \(.installed_version) → \(.latest_version)"' audit_results.json

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: audit-results
          path: audit_results.json
```

#### Snapshot Caching Workflow

```yaml
name: Tool Audit with Cache

on:
  push:
    branches: [main]
  pull_request:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Restore snapshot cache
        id: cache-snapshot
        uses: actions/cache@v3
        with:
          path: tools_snapshot.json
          key: tools-snapshot-${{ runner.os }}-${{ hashFiles('upstream_versions.json') }}
          restore-keys: |
            tools-snapshot-${{ runner.os }}-

      - name: Update snapshot if cache miss
        if: steps.cache-snapshot.outputs.cache-hit != 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: make update

      - name: Render audit
        run: make audit

      - name: Save snapshot
        uses: actions/cache/save@v3
        if: always()
        with:
          path: tools_snapshot.json
          key: tools-snapshot-${{ runner.os }}-${{ hashFiles('upstream_versions.json') }}
```

#### PR Comment Workflow

```yaml
name: Audit PR Comment

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run audit
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CLI_AUDIT_JSON: 1
        run: python3 cli_audit.py > audit.json

      - name: Generate summary
        id: summary
        run: |
          echo "outdated=$(jq -r '[.[] | select(.status == "OUTDATED")] | length' audit.json)" >> $GITHUB_OUTPUT
          echo "missing=$(jq -r '[.[] | select(.status == "NOT INSTALLED")] | length' audit.json)" >> $GITHUB_OUTPUT

      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            const outdated = ${{ steps.summary.outputs.outdated }};
            const missing = ${{ steps.summary.outputs.missing }};
            const body = `## Tool Audit Results\n\n- 🔄 Outdated: ${outdated}\n- ❌ Missing: ${missing}\n\nRun \`make upgrade\` to remediate.`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            })
```

### GitLab CI

```yaml
tool_audit:
  stage: test
  image: python:3.11
  script:
    - python3 cli_audit.py --only agent-core | python3 smart_column.py -s "|" -t
  only:
    - main
    - merge_requests

tool_audit_json:
  stage: test
  image: python:3.11
  script:
    - CLI_AUDIT_JSON=1 python3 cli_audit.py > audit.json
    - jq '.[] | select(.status != "UP-TO-DATE")' audit.json
  artifacts:
    paths:
      - audit.json
    expire_in: 1 week
  only:
    - schedules
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    environment {
        GITHUB_TOKEN = credentials('github-token')
    }
    stages {
        stage('Audit Tools') {
            steps {
                sh '''
                    CLI_AUDIT_JSON=1 python3 cli_audit.py > audit.json
                    jq -r '.[] | select(.status == "OUTDATED") | .tool' audit.json > outdated.txt
                '''
                archiveArtifacts artifacts: 'audit.json,outdated.txt', fingerprint: true
            }
        }
        stage('Report') {
            steps {
                script {
                    def outdated = readFile('outdated.txt').trim()
                    if (outdated) {
                        currentBuild.result = 'UNSTABLE'
                        echo "Outdated tools: ${outdated}"
                    }
                }
            }
        }
    }
}
```

## Performance Tuning

### Benchmarking

```bash
# Measure collection time
time make update

# Measure render time
time make audit

# Identify slow tools
CLI_AUDIT_TRACE=1 CLI_AUDIT_SLOW_MS=1000 make update 2>&1 | grep "slow"
```

### Optimization Strategies

#### 1. Increase Concurrency

**Default:** 16 workers

```bash
# For powerful machines
CLI_AUDIT_MAX_WORKERS=32 make update

# For resource-constrained environments
CLI_AUDIT_MAX_WORKERS=4 make update
```

**Recommendation:** 16-20 workers optimal, diminishing returns above.

#### 2. Reduce Timeout

**Default:** 3 seconds per operation

```bash
# Faster but may miss slow tools
CLI_AUDIT_TIMEOUT_SECONDS=1 make update

# More patient for slow networks
CLI_AUDIT_TIMEOUT_SECONDS=10 make update
```

#### 3. HTTP Retry Tuning

**Default:** 2 retries with exponential backoff

```bash
# Aggressive (faster failure)
CLI_AUDIT_HTTP_RETRIES=1 CLI_AUDIT_BACKOFF_BASE=0.1 make update

# Conservative (better success rate)
CLI_AUDIT_HTTP_RETRIES=5 CLI_AUDIT_BACKOFF_BASE=0.5 make update
```

#### 4. Manual-First Mode

Try cache before network (cache-first strategy):

```bash
CLI_AUDIT_MANUAL_FIRST=1 make update
```

**Effect:** Reduces API calls, faster when cache is current.

#### 5. Fast Mode

Skip expensive operations:

```bash
CLI_AUDIT_FAST=1 make update
```

**Skips:**
- Docker image inspection (if enabled)
- Slow upstream APIs (GNU FTP)
- Deep path searches

#### 6. Host Concurrency Caps

Prevent rate limiting by limiting per-host requests:

```bash
# Default: 4 concurrent GitHub API requests
CLI_AUDIT_HOST_CAP_GITHUB_API=2 make update

# Default: 4 concurrent npm registry requests
CLI_AUDIT_HOST_CAP_NPM=8 make update
```

**Available Caps:**
- `CLI_AUDIT_HOST_CAP_GITHUB` - github.com (releases)
- `CLI_AUDIT_HOST_CAP_GITHUB_API` - api.github.com
- `CLI_AUDIT_HOST_CAP_NPM` - registry.npmjs.org
- `CLI_AUDIT_HOST_CAP_CRATES` - crates.io
- `CLI_AUDIT_HOST_CAP_GNU` - GNU FTP mirrors

#### 7. Snapshot-Based Rendering

**Fastest:** Render from snapshot (no collection)

```bash
make audit  # <100ms
```

**Use Case:** Repeated local checks, CI status gates.

### Performance Metrics

#### Expected Timings (50 tools)

| Scenario | Time | Workers | Network |
|----------|------|---------|---------|
| Full audit (online) | ~10s | 16 | Yes |
| Full audit (cache-first) | ~5s | 16 | Partial |
| Full audit (offline) | ~3s | 16 | No |
| Render-only | <100ms | - | No |
| Single tool audit | ~300ms | 1 | Yes |

#### Performance Bottlenecks

1. **GitHub API Rate Limiting:** 60 req/hour without token
   - **Fix:** Set `GITHUB_TOKEN` environment variable
   - **Effect:** 5000 req/hour authenticated

2. **Network Latency:** Upstream APIs may be slow
   - **Fix:** Use manual-first mode, increase timeout
   - **Effect:** Better success rate, slightly slower

3. **Subprocess Execution:** 50+ version checks add up
   - **Fix:** Increase workers, reduce timeout
   - **Effect:** Faster completion, potential misses

4. **Docker Inspection:** Slow if many images
   - **Fix:** `CLI_AUDIT_DOCKER_INFO=0`
   - **Effect:** Skip docker image details

### Production Tuning Recommendations

**High-Reliability (CI/CD):**
```bash
CLI_AUDIT_MAX_WORKERS=8
CLI_AUDIT_TIMEOUT_SECONDS=10
CLI_AUDIT_HTTP_RETRIES=5
GITHUB_TOKEN=<token>
```

**High-Performance (Local Dev):**
```bash
CLI_AUDIT_MAX_WORKERS=20
CLI_AUDIT_TIMEOUT_SECONDS=2
CLI_AUDIT_HTTP_RETRIES=1
CLI_AUDIT_MANUAL_FIRST=1
```

**Offline/Air-Gapped:**
```bash
CLI_AUDIT_OFFLINE=1
CLI_AUDIT_RENDER=1
CLI_AUDIT_MANUAL_FIRST=1
```

## Monitoring and Alerting

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

set -euo pipefail

OUTDATED_COUNT=$(CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '[.[] | select(.status == "OUTDATED")] | length')
MISSING_COUNT=$(CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '[.[] | select(.status == "NOT INSTALLED")] | length')

if [ "$OUTDATED_COUNT" -gt 5 ] || [ "$MISSING_COUNT" -gt 2 ]; then
  echo "WARN: $OUTDATED_COUNT outdated, $MISSING_COUNT missing tools"
  exit 1
fi

echo "OK: System up to date"
exit 0
```

### Prometheus Metrics Export

```bash
#!/bin/bash
# metrics.sh

set -euo pipefail

CLI_AUDIT_JSON=1 python3 cli_audit.py > audit.json

cat <<EOF
# HELP cli_audit_tools_total Total number of tools audited
# TYPE cli_audit_tools_total gauge
cli_audit_tools_total $(jq 'length' audit.json)

# HELP cli_audit_outdated_total Number of outdated tools
# TYPE cli_audit_outdated_total gauge
cli_audit_outdated_total $(jq '[.[] | select(.status == "OUTDATED")] | length' audit.json)

# HELP cli_audit_missing_total Number of missing tools
# TYPE cli_audit_missing_total gauge
cli_audit_missing_total $(jq '[.[] | select(.status == "NOT INSTALLED")] | length' audit.json)
EOF
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed debugging information.

## See Also

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and data flow
- **[API_REFERENCE.md](API_REFERENCE.md)** - Function signatures and environment variables
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Contributing and development
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[TOOL_ECOSYSTEM.md](TOOL_ECOSYSTEM.md)** - Tool catalog and classifications
