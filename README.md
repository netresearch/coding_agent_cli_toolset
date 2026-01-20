# AI CLI Preparation

A minimal utility to verify that tools used by AI coding agents are installed and up to date on your system. It audits versions of common agent toolchain CLIs against the latest upstream releases and prints a pipe-delimited report suitable for quick human scan or downstream tooling.

## Quick Start

```bash
make update    # Scan all tools, fetch latest versions, save snapshot
make upgrade   # Interactive remediation for outdated/missing tools
```

That's it. Run these periodically to keep your AI coding agent toolchain current.

## Scope: agent toolchain
- This audit targets CLIs that coding agents commonly utilize themselves if present on the machine. It is agent-focused; tools may be reported as NOT INSTALLED on your host if you don't use them.
- Upstream versions are resolved from GitHub releases, PyPI, crates.io, or the npm registry for Node CLIs.

## Primary Use Case: AI coding agent readiness

Use this tool to quickly confirm that the CLIs your AI coding agents rely on are present and current. If tools are missing or outdated, use the provided installer scripts (see Installation scripts) or your preferred package manager to remediate, then re-run the audit until everything is ready.

## Features
- Detects installed versions across PATH (and `~/.cargo/bin` for Rust tools)
- Fetches latest upstream versions from GitHub, PyPI, crates.io, and npm registry (for `npm`/`pnpm`/`yarn` and Node-only CLIs)
- Handles tools with non-standard version flags (e.g., `entr`, `sponge`)
- Short timeouts to avoid hanging
- Simple, parse-friendly output

## Output Format
The program prints a header followed by one line per tool (6 columns):

```
state|tool|installed|installed_method|latest_upstream|upstream_method
+|fd|9.0.0 (140ms)|apt/dpkg|9.0.0 (220ms)|github
...
```

- `state`: single-character/emoji indicator of status
- `tool`: logical tool name
- `installed`: local version display (may include timing)
- `installed_method`: detected installation source (e.g., `uv tool`, `npm (user)`, `apt/dpkg`)
- `latest_upstream`: upstream version display (may include timing)
- `upstream_method`: where the upstream version came from (`github`, `pypi`, `crates`, `npm`, `gnu-ftp`)

### JSON mode

Set `CLI_AUDIT_JSON=1` to emit a JSON array of tool objects instead of the table:

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'
```

Fields (subset):
- `tool`: logical tool name
- `installed`: formatted local version display (may include timings)
- `installed_version`: parsed semantic version of the local tool (when available)
- `latest_upstream`: formatted upstream version display (may include timings)
- `latest_version`: parsed semantic version of the upstream tool (when available)
- `installed_method`: detected installation source (e.g., "uv tool", "npm (user)")
- `installed_path_resolved`: realpath via which(1) (kept for backwards compatibility)
- `classification_reason`: reason derived from classifying the which(1) path
- `installed_path_selected`: path of the executable actually selected by the audit run
- `classification_reason_selected`: reason string for the selected path's classification
- `upstream_method`: source used for latest lookup (e.g., "github", "uv tool")
- `status`: `UP-TO-DATE`, `OUTDATED`, `NOT INSTALLED`, or `UNKNOWN`

Example (abridged):

```json
{
  "tool": "eslint",
  "installed": "9.35.0 (340ms)",
  "installed_version": "9.35.0",
  "installed_method": "npm (user)",
  "installed_path_resolved": "/home/you/.local/lib/node_modules/eslint/bin/eslint.js",
  "classification_reason": "path-under-~/.local/lib/node_modules",
  "installed_path_selected": "/home/you/.local/lib/node_modules/eslint/bin/eslint.js",
  "classification_reason_selected": "path-under-~/.local/lib/node_modules",
  "latest_upstream": "9.35.0 (800ms)",
  "latest_version": "9.35.0",
  "upstream_method": "github",
  "status": "UP-TO-DATE"
}
```

## Tool categories (agent-focused)
- Core runtimes & package managers: `python`, `pip`, `pipx`, `poetry`, `node`, `npm`, `pnpm`, `yarn`
- Search & code-aware tools: `ripgrep`, `ast-grep`, `fzf`, `fd`, `xsv`
- Editors/helpers and diffs: `ctags`, `delta`, `bat`, `just`
- JSON/YAML processors: `jq`, `yq`, `dasel`, `fx`
- HTTP/CLI clients: `httpie`, `curlie`
- Watch/run automation: `entr`, `watchexec`, `direnv`
- Security & compliance: `semgrep`, `bandit`, `gitleaks`, `trivy`
- Git helpers: `git-absorb`, `git-branchless`
- Formatters & linters: `black`, `isort`, `flake8`, `eslint`, `prettier`, `shfmt`, `shellcheck`
- VCS & platforms: `git`, `gh` (GitHub CLI), `glab` (GitLab CLI)
- Cloud & infra: `aws`, `kubectl`, `terraform`, `docker`, `dive`

Note: Not all of these are expected to be installed globally; the report simply surfaces what is present and how it compares upstream.

## Requirements
- Python 3.9+
- Network access to query GitHub/PyPI/crates.io/npm

## Quick Start

```bash
python3 cli_audit.py | column -s '|' -t
```

Tip: On systems where `column` is unavailable, just view the raw output or import into your tool of choice.

## Code Examples

### Installing a Single Tool

```python
from cli_audit import install_tool, Config, Environment

# Create configuration and detect environment
config = Config()
env = Environment.detect()

# Install a Python tool using pipx
result = install_tool(
    tool_name="black",
    package_name="black",
    target_version="latest",
    config=config,
    env=env,
    language="python",
    verbose=True,
)

if result.success:
    print(f"✓ {result.tool_name} {result.installed_version} installed via {result.package_manager_used}")
    print(f"  Binary: {result.binary_path}")
    print(f"  Duration: {result.duration_seconds:.2f}s")
else:
    print(f"✗ Installation failed: {result.error_message}")
```

### Bulk Installation

```python
from cli_audit import bulk_install, Config, Environment

config = Config()
env = Environment.detect()

# Install multiple tools in parallel
result = bulk_install(
    mode="explicit",
    tool_names=["ripgrep", "fd", "bat"],
    config=config,
    env=env,
    max_workers=3,
    verbose=True,
)

print(f"✓ Successes: {len(result.successes)}")
print(f"✗ Failures: {len(result.failures)}")
print(f"Duration: {result.duration_seconds:.2f}s")

for success in result.successes:
    print(f"  ✓ {success.tool_name} {success.installed_version}")
```

### Upgrading Tools

```python
from cli_audit import upgrade_tool, get_upgrade_candidates, Config, Environment

config = Config()
env = Environment.detect()

# Check for available upgrades
candidates = get_upgrade_candidates(
    tools=["black", "ripgrep"],
    config=config,
    env=env,
    verbose=True,
)

print(f"Found {len(candidates)} upgrade candidates:")
for candidate in candidates:
    print(f"  {candidate.tool_name}: {candidate.current_version} → {candidate.available_version}")

# Upgrade a specific tool
if candidates:
    candidate = candidates[0]
    result = upgrade_tool(
        tool_name=candidate.tool_name,
        target_version=candidate.available_version,
        current_version=candidate.current_version,
        config=config,
        env=env,
        verbose=True,
    )

    if result.success:
        print(f"✓ Upgraded {result.tool_name} to {result.installed_version}")
    else:
        print(f"✗ Upgrade failed: {result.error_message}")
```

### Using Configuration Files

Create a `.cli-audit.yml` file in your project root:

```yaml
version: 1

environment:
  mode: workstation  # auto, ci, server, or workstation

tools:
  black:
    version: "24.*"  # Pin to major version
    method: pipx
    fallback: pip

  ripgrep:
    version: latest
    method: cargo

preferences:
  reconciliation: aggressive  # or parallel
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

Load and use the configuration:

```python
from cli_audit import load_config, bulk_install, Environment

# Load configuration from standard locations
config = load_config(verbose=True)
env = Environment.from_config(config)

# Install tools from a preset
result = bulk_install(
    mode="preset",
    preset_name="dev-essentials",
    config=config,
    env=env,
)

print(f"Installed {len(result.successes)} tools from preset")
```

### Reconciling Multiple Installations

```python
from cli_audit import reconcile_tool, bulk_reconcile, Config, Environment

config = Config()
env = Environment.detect()

# Reconcile a single tool (remove duplicates)
result = reconcile_tool(
    tool_name="python",
    config=config,
    env=env,
    dry_run=False,  # Set to True to preview actions
    verbose=True,
)

if result.reconciled:
    print(f"✓ Reconciled {result.tool_name}")
    print(f"  Kept: {result.kept_installation.path} ({result.kept_installation.method})")
    print(f"  Removed: {len(result.removed_installations)} installations")
else:
    print(f"No action needed for {result.tool_name}")

# Bulk reconciliation
bulk_result = bulk_reconcile(
    tools=["python", "node", "rust"],
    config=config,
    env=env,
    max_workers=3,
)

print(f"Reconciled {len(bulk_result.reconciled)} tools")
```

### Custom Preferences

```python
from cli_audit import Config, Preferences, BulkPreferences, install_tool, Environment

# Create custom preferences
bulk_prefs = BulkPreferences(
    fail_fast=True,
    auto_rollback=True,
    generate_rollback_script=True,
)

prefs = Preferences(
    reconciliation="aggressive",
    breaking_changes="reject",  # Don't allow major version upgrades
    auto_upgrade=False,
    max_workers=4,
    cache_ttl_seconds=1800,  # 30 minutes
    bulk=bulk_prefs,
)

config = Config(preferences=prefs)
env = Environment.detect()

# Use custom preferences
result = install_tool(
    tool_name="black",
    package_name="black",
    target_version="23.12.0",  # Pin specific version
    config=config,
    env=env,
    language="python",
)
```

### Dry Run and Install Planning

```python
from cli_audit import generate_install_plan, dry_run_install, Config, Environment

config = Config()
env = Environment.detect()

# Generate installation plan
plan = generate_install_plan(
    tool_name="ripgrep",
    package_name="ripgrep",
    target_version="latest",
    config=config,
    env=env,
    language="rust",
)

print("Installation plan:")
for step in plan.steps:
    print(f"  {step.description}")
    print(f"    Command: {' '.join(step.command)}")

# Execute dry run (no actual changes)
result = dry_run_install(plan, verbose=True)
print(f"\nDry run completed in {result.duration_seconds:.2f}s")
print(f"Estimated steps: {len(result.steps_completed)}")
```

## Snapshot-based workflow (local-only friendly)

This tool now separates data collection from rendering:

- `make update`: collect-only. Fetches/upgrades the snapshot with installed/upstream info and writes a JSON snapshot (`tools_snapshot.json` by default). Verbose; helpful to identify slowness.
- `make audit`: render-only. Prints the table strictly from the snapshot (no network). Safe to run repeatedly.
- `make audit-auto`: updates the snapshot only if it is missing, then renders.
- `make upgrade`: interactive remediation (renamed from `guide`).

Advanced:
- Snapshot path can be overridden via `CLI_AUDIT_SNAPSHOT_FILE=/path/to/snapshot.json`.
- Environment toggles for scripting:
  - `CLI_AUDIT_COLLECT=1` → collect-only
  - `CLI_AUDIT_RENDER=1` → render-only
  - `CLI_AUDIT_OFFLINE=1` → force offline lookups (uses baseline methods, marks upstream as `manual`)

The snapshot (`tools_snapshot.json`) includes `__meta__` (schema version, timestamp) and a `tools` array containing fields used by the table, plus the upstream lookup method when available.

## Quick agent readiness check

- Table scan for a quick look:

```bash
python3 cli_audit.py | column -s '|' -t
```

- JSON for actionable filtering (e.g., list anything not up to date):

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py \
  | jq -r '.[] | select(.status != "UP-TO-DATE") | [.tool, .status] | @tsv'
```

- JSON by category (e.g., focus on security):

```bash
CLI_AUDIT_JSON=1 python3 cli_audit.py \
  | jq -r '.[] | select(.category=="security" and .status != "UP-TO-DATE") | [.tool, .status] | @tsv'
```

- Typical remediation workflow for agent readiness:
  1. Run the audit.
  2. Install or update missing/outdated tools using the `make install-*` targets under Installation scripts (or your package manager).
  3. Re-run the audit until only up-to-date tools remain.

## Extending the Tool List
Agent-focused tools live in the `TOOLS` tuple in `cli_audit.py`. Prefer upstreams with discoverable latest releases:

```python
Tool("fd", ("fd", "fdfind"), "gh", ("sharkdp", "fd")),
```

- `name`: logical name displayed in output
- `candidates`: executable names to search on PATH (first line of their version output is used)
- `source_kind`: one of `gh`, `pypi`, `crates`, `npm`, or `skip`
- `source_args`: parameters for the source (e.g., owner/repo for GitHub, package name for PyPI/crates/npm)

If `source_kind` is `skip`, upstream lookup is disabled for that tool.

## Notes and Caveats
- Timeouts are kept intentionally short (3s) to avoid blocking; transient network failures may mark `latest_upstream` as empty.
- When multiple candidates are installed, the highest semantic version is selected.
- For tools without a conventional version flag, the script tries a small set of common flags and a few special cases.

### Debugging

- Set `CLI_AUDIT_DEBUG=1` to print brief debug messages for suppressed exceptions and best-effort operations (e.g., uv tool enumeration). Disabled by default.

### Empty selection handling

- When selecting tools via `--only` or `CLI_AUDIT_ONLY`, unknown names now yield an empty JSON array in JSON mode and a header-only table in text mode.

## Development

- Lint (optional):
```bash
python3 -m pyflakes cli_audit.py
```

- Run tests (n/a): This repo currently ships without tests. PRs welcome.

## Installation scripts

Language-agnostic core tools and language-specific stacks are provided under `scripts/`:

```bash
make scripts-perms

# Core simple tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
make install-core

# Language stacks
make install-python
make install-node
make install-go

# Higher-level tools
make install-aws
make install-kubectl
make install-terraform
make install-ansible
make install-docker
make install-brew
make install-rust
```

These scripts prefer the most up-to-date sources (e.g., nvm for Node, vendor installers for AWS CLI and kubectl) when feasible.

### Role-focused quick checks (local-only)

Use friendly `--only` aliases to focus on a subset quickly (these expand to explicit tool lists under the hood):

```bash
# Agent-centric core tools
python3 cli_audit.py --only agent-core | python3 smart_column.py -s "|" -t --right 3,5 --header

# Python / Node / Go cores
python3 cli_audit.py --only python-core | python3 smart_column.py -s "|" -t --right 3,5 --header
python3 cli_audit.py --only node-core   | python3 smart_column.py -s "|" -t --right 3,5 --header
python3 cli_audit.py --only go-core     | python3 smart_column.py -s "|" -t --right 3,5 --header

# Infra and Security
python3 cli_audit.py --only infra-core    | python3 smart_column.py -s "|" -t --right 3,5 --header
python3 cli_audit.py --only security-core | python3 smart_column.py -s "|" -t --right 3,5 --header

# Data tooling
python3 cli_audit.py --only data-core | python3 smart_column.py -s "|" -t --right 3,5 --header
```

Notes:
- Category subheaders and a one-line "Readiness: ..." summary are printed for fast local scanning.
- Set `CLI_AUDIT_HINTS=0` to suppress brief remediation hints inline.
- When `CLI_AUDIT_OFFLINE=1`, the readiness line displays `(offline)` to indicate baseline-only latest checks.

### Install-method classification (how local tools are attributed)

The audit attempts to identify how a tool was installed by inspecting the resolved executable path and environment hints. Recognized classifications include (non-exhaustive):

- `uv tool`, `uv python`, `uv venv`
- `pipx/user`
- `npm (user)`, `npm (global)`, `corepack`, `nvm/npm`
- `asdf`, `nodenv`, `pyenv`, `rbenv`
- `homebrew` (Linuxbrew/macOS), `/usr/local/bin`, `apt/dpkg`, `snap`
- `rustup/cargo`, `go install`, `pnpm`, `yarn`, `pnpm`
- `volta`, `sdkman`, `nodist`

When ambiguous, the audit may report a generic bucket (e.g., `~/.local/bin`). The JSON output includes `installed_path_resolved` and `classification_reason` to aid debugging.

### Actions: install, update, uninstall, reconcile

All scripts accept an action argument. Defaults to `install`.

```bash
# Update existing toolchains
make update-core
make update-python
make update-node
make update-go
make update-aws

# Uninstall
make uninstall-node

# Reconcile preferred method
# Example: remove distro Node and switch to nvm-managed
make reconcile-node

# Example: remove distro Rust and switch to rustup-managed
make reconcile-rust
```

## Auto-Update: Package Manager Detection and Updates

The `auto-update` feature automatically detects all installed package managers and runs their built-in update/upgrade tools. This is a comprehensive way to keep your entire development environment up-to-date.

### Supported Package Managers

**System Package Managers:**
- apt (Debian/Ubuntu)
- Homebrew (macOS/Linux)
- Snap
- Flatpak

**Language-Specific Package Managers:**
- Cargo (Rust) + Rustup
- UV (Python)
- Pipx (Python)
- Pip (Python)
- NPM (Node.js)
- PNPM (Node.js)
- Yarn (Node.js)
- Go (binaries)
- RubyGems

### Quick Start

```bash
# Detect all installed package managers
make auto-update-detect

# Update all package managers and their packages
make auto-update

# Preview what would be updated (dry-run)
make auto-update-dry-run

# Update only system package managers (apt, brew, snap, flatpak)
make auto-update-system-only

# Update all except system package managers
make auto-update-skip-system
```

### Advanced Usage

The `scripts/auto_update.sh` script can be called directly for fine-grained control:

```bash
# Show detected package managers
./scripts/auto_update.sh detect

# Update all package managers
./scripts/auto_update.sh update

# Update specific package manager only
./scripts/auto_update.sh cargo
./scripts/auto_update.sh npm
./scripts/auto_update.sh brew

# Dry-run mode (show what would be updated)
./scripts/auto_update.sh --dry-run update

# Verbose output
./scripts/auto_update.sh --verbose update

# Skip system package managers
./scripts/auto_update.sh --skip-system update

# Environment variable control
DRY_RUN=1 ./scripts/auto_update.sh update
VERBOSE=1 ./scripts/auto_update.sh update
SKIP_SYSTEM=1 ./scripts/auto_update.sh update
```

### What Gets Updated

Each package manager updates itself and all packages it manages:

**APT:** Updates package lists and upgrades all installed packages
```bash
sudo apt-get update && sudo apt-get upgrade -y
```

**Homebrew:** Updates package index and upgrades all formulae/casks
```bash
brew update && brew upgrade && brew cleanup
```

**Cargo:** Updates Rust toolchain via rustup and upgrades all cargo-installed binaries
```bash
rustup update
cargo install-update -a  # requires cargo-update
```

**UV:** Self-updates UV and upgrades all UV-managed tools
```bash
uv self update
uv tool upgrade <each-tool>
```

**Pipx:** Updates pipx itself and all pipx-installed packages
```bash
pip3 install --user --upgrade pipx
pipx upgrade-all
```

**NPM:** Updates npm itself and all global packages
```bash
npm install -g npm@latest
npm update -g
```

**PNPM:** Updates pnpm (via corepack) and global packages
```bash
corepack prepare pnpm@latest --activate
pnpm update -g
```

**Yarn:** Updates yarn (via corepack)
```bash
corepack prepare yarn@stable --activate
```

**RubyGems:** Updates gem system and all installed gems
```bash
gem update --system
gem update
gem cleanup
```

### Workflow Recommendations

**Daily Development Workflow:**
```bash
# Quick check what's available
make auto-update-detect

# Preview updates without making changes
make auto-update-dry-run

# Apply updates to everything
make auto-update
```

**CI/CD or Scripting:**
```bash
# Silent updates with environment variables
VERBOSE=0 ./scripts/auto_update.sh update

# Update only user-level tools (skip system packages)
SKIP_SYSTEM=1 ./scripts/auto_update.sh update
```

**Selective Updates:**
```bash
# Update only Rust ecosystem
./scripts/auto_update.sh cargo

# Update only Node.js ecosystem
./scripts/auto_update.sh npm
./scripts/auto_update.sh pnpm
./scripts/auto_update.sh yarn

# Update only Python ecosystem
./scripts/auto_update.sh uv
./scripts/auto_update.sh pipx
```

### Integration with Existing Workflow

The auto-update feature complements the existing audit/upgrade workflow:

```bash
# 1. Update version snapshot from upstream sources
make update

# 2. Review what needs updating
make audit

# 3. Run interactive upgrade for specific tools
make upgrade

# 4. Auto-update all package managers and their packages
make auto-update

# 5. Verify everything is up-to-date
make audit
```

### Notes

- System package managers (apt, brew, snap, flatpak) require appropriate permissions (sudo)
- The auto-update process is designed to be safe and non-destructive
- Use `--dry-run` to preview changes before applying them
- Some package managers (like Go) don't have built-in bulk update mechanisms - manual updates are required
- The script gracefully handles missing package managers (skips them)

## Data Files

The audit system uses two JSON files:

| File | Purpose | Git Tracked |
|------|---------|-------------|
| `upstream_versions.json` | Latest available versions from upstream sources | Yes (committed) |
| `local_state.json` | Machine-specific installed tool versions | No (gitignored) |

- **Offline mode**: Set `CLI_AUDIT_OFFLINE=1` to use cached `upstream_versions.json` without network calls
- **Baseline refresh**: Run `python audit.py --update-baseline` to update upstream versions

## License
MIT
