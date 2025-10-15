# Installation Scripts Documentation

## Overview

The AI CLI Preparation project includes 14 automated installation scripts for setting up developer tools and language environments. Each script supports four standard actions: `install`, `update`, `uninstall`, and `reconcile`.

### Script Inventory

| Script | Category | Purpose |
|--------|----------|---------|
| `install_ansible.sh` | Infrastructure | Ansible automation platform |
| `install_aws.sh` | Cloud CLI | AWS command-line interface |
| `install_brew.sh` | Package Manager | Homebrew (macOS/Linux) |
| `install_core.sh` | Developer Tools | Core CLI tools (fd, fzf, ripgrep, jq, yq, bat, delta, just) |
| `install_docker.sh` | Containers | Docker engine and docker-compose |
| `install_go.sh` | Language Runtime | Go programming language |
| `install_kubectl.sh` | Cloud CLI | Kubernetes command-line tool |
| `install_node.sh` | Language Runtime | Node.js via nvm (Node Version Manager) |
| `install_python.sh` | Language Runtime | Python runtime and package managers |
| `install_rust.sh` | Language Runtime | Rust via rustup |
| `install_terraform.sh` | Infrastructure | Terraform infrastructure-as-code |
| `install_uv.sh` | Package Manager | uv Python package manager |

Plus 2 shared library scripts:
- `lib/common.sh` - Shared utilities and helper functions
- `lib/distro.sh` - Distribution detection and package manager wrappers

## Actions Supported

All installation scripts support four standard actions:

### 1. Install

Installs tools from the latest upstream sources when available, falling back to package managers.

```bash
./scripts/install_core.sh install
./scripts/install_python.sh install
./scripts/install_rust.sh install
```

**Behavior:**
- Checks if tool already exists (idempotent)
- Prefers vendor-specific installers (rustup, nvm) over package managers
- Downloads latest releases from GitHub/official sources when possible
- Falls back to apt/brew if vendor installer unavailable
- Creates necessary directories (`~/.local/bin`, etc.)

### 2. Update

Updates tools to latest versions using their native update mechanisms.

```bash
./scripts/install_core.sh update
./scripts/install_python.sh update
./scripts/install_rust.sh update
```

**Behavior:**
- Uses tool-specific update commands (`rustup update`, `brew upgrade`)
- For apt-installed tools, runs `apt-get install --only-upgrade`
- No-op if tool not installed
- Preserves existing configuration

### 3. Uninstall

Removes tools and cleans up installation artifacts.

```bash
./scripts/install_core.sh uninstall
./scripts/install_python.sh uninstall
./scripts/install_rust.sh uninstall
```

**Behavior:**
- Removes binaries from standard locations (`~/.local/bin`, `/usr/local/bin`)
- Uses tool-specific uninstallers when available (`rustup self uninstall`)
- Removes package manager installations (`apt-get remove`)
- Does not remove user configuration files

### 4. Reconcile

Ensures tools are installed using preferred methods, migrating from package managers to upstream installers.

```bash
./scripts/install_core.sh reconcile
./scripts/install_core.sh reconcile ripgrep  # Single tool
./scripts/install_python.sh reconcile
```

**Behavior:**
- Removes package manager versions (apt, snap)
- Reinstalls using preferred upstream method
- Useful for migrating from distro packages to vendor installers
- Reports before/after versions and paths

## Installation Methods

### Vendor Installers (Preferred)

Scripts prefer official vendor installers for better version control and updates:

| Tool | Installer | Method |
|------|-----------|--------|
| Rust | rustup | `curl https://sh.rustup.rs \| sh` |
| Node | nvm | `curl https://raw.githubusercontent.com/nvm-sh/nvm/...` |
| Python | deadsnakes PPA | `add-apt-repository ppa:deadsnakes/ppa` |
| Go | Official tarball | `wget https://go.dev/dl/go*.tar.gz` |
| uv | Official installer | `curl -LsSf https://astral.sh/uv/install.sh` |

### GitHub Releases

For tools without vendor installers, scripts download from GitHub releases:

- **Binary assets:** Direct download (fd, ripgrep, fzf, gh, shellcheck)
- **Source builds:** Clone → build → install (entr, parallel, ctags)
- **Fallback to distro packages** when GitHub unavailable

### Package Managers

Used as fallback when upstream sources unavailable:

- **apt/dpkg:** Debian/Ubuntu systems
- **Homebrew:** macOS and Linuxbrew
- **snap:** Containerized packages (discouraged, removed during reconcile)

## Script-Specific Documentation

### install_core.sh

Manages essential developer CLI tools.

**Tools Installed:**
- **fd** - Fast find replacement
- **fzf** - Fuzzy finder
- **ripgrep** - Fast grep replacement
- **jq** - JSON processor
- **yq** - YAML processor
- **bat** - Cat with syntax highlighting
- **delta** - Git diff viewer
- **just** - Command runner

**Additional Tools (via dedicated functions):**
- git, gh (GitHub CLI), glab (GitLab CLI)
- ctags (universal-ctags from source)
- entr (file watcher)
- parallel (GNU parallel)
- shellcheck, shfmt (shell linters/formatters)
- eslint, prettier (JS linters/formatters)
- trivy, gitleaks (security scanners)
- dive (Docker image analyzer)
- direnv, ast-grep, fx, curlie

**Special Handling:**

1. **ctags**: Built from source via checkinstall for clean uninstall
   ```bash
   # Reads target version from latest_versions.json
   # Builds universal-ctags with autoconf
   # Registers with update-alternatives
   ```

2. **entr**: Builds from GitHub source tarball
   ```bash
   # Discovers latest via redirect
   # Downloads release tarball
   # Compiles with make
   ```

3. **parallel**: Downloads from GNU FTP mirror
   ```bash
   # Supports tar.bz2, tar.xz, tar.gz
   # Configures with --prefix
   # Fallback to apt if build fails
   ```

### install_rust.sh

Installs Rust via rustup with all components.

**Components:**
- rustc (compiler)
- cargo (package manager)
- rust-std (standard library)
- rust-docs (offline documentation)
- rustfmt, clippy (formatters/linters)

**Actions:**
```bash
install_rust    # Runs rustup installer
update_rust     # Runs rustup update
uninstall_rust  # Runs rustup self uninstall
reconcile_rust  # Removes apt rustc/cargo, installs via rustup
```

**Detection:**
- Checks `cargo` command availability
- Sources `~/.cargo/env` after installation
- Prefers rustup over apt packages

### install_python.sh

Manages Python runtimes and package managers.

**Components:**
- Python 3.x (via deadsnakes PPA on Ubuntu)
- pip (Python package installer)
- pipx (isolated CLI tools)
- poetry (dependency management)
- uv (fast Python package manager)

**Actions:**
```bash
install_python    # Installs Python + pip + pipx + poetry
update_python     # Updates all Python tools
uninstall_python  # Removes Python environments
reconcile_python  # Migrates to preferred methods
```

**Version Selection:**
- Prioritizes Python 3.12+
- Uses deadsnakes PPA for latest versions on Ubuntu
- Installs python3-venv for virtual environments

### install_node.sh

Installs Node.js via nvm for version management.

**Components:**
- nvm (Node Version Manager)
- Node.js LTS (via nvm)
- npm (bundled with Node)
- yarn, pnpm (alternative package managers)

**Actions:**
```bash
install_node    # Installs nvm + Node LTS
update_node     # Updates nvm + Node to latest LTS
uninstall_node  # Removes nvm and Node
reconcile_node  # Migrates to nvm-managed installation
```

**Features:**
- Installs latest LTS version by default
- Configures shell initialization (`~/.bashrc`, `~/.zshrc`)
- Supports multiple Node versions via nvm

### install_go.sh

Installs Go from official tarballs.

**Installation Path:** `/usr/local/go` (system) or `~/.local/go` (user)

**Actions:**
```bash
install_go    # Downloads + extracts Go tarball
update_go     # Removes old + installs latest
uninstall_go  # Removes Go installation
reconcile_go  # Migrates from package manager to tarball
```

**Version Discovery:**
- Queries https://go.dev/dl/?mode=json
- Selects latest stable release
- Validates SHA256 checksums

### install_docker.sh

Installs Docker Engine and docker-compose.

**Components:**
- Docker Engine (CE)
- docker-compose v2 (plugin)
- Docker Buildx (plugin)

**Installation Methods:**
1. **Docker Desktop** (WSL detection)
2. **Docker APT repository** (official)
3. **Convenience script** (fallback)

**Actions:**
```bash
install_docker    # Installs Docker + compose
update_docker     # Updates Docker packages
uninstall_docker  # Removes Docker completely
reconcile_docker  # Migrates to preferred method
```

**Post-Install:**
- Adds user to `docker` group
- Enables Docker service
- Validates installation with `docker run hello-world`

### install_terraform.sh

Installs Terraform from HashiCorp releases.

**Installation Method:**
- Downloads official ZIP from releases.hashicorp.com
- Extracts to `/usr/local/bin` or `~/.local/bin`
- Validates binary hash

**Actions:**
```bash
install_terraform    # Downloads + installs latest
update_terraform     # Removes old + installs latest
uninstall_terraform  # Removes binary
reconcile_terraform  # Migrates from package manager
```

### install_kubectl.sh

Installs kubectl from Kubernetes releases.

**Installation Method:**
- Downloads from https://dl.k8s.io/release/
- Validates with SHA256 checksum
- Installs to `/usr/local/bin` or `~/.local/bin`

**Actions:**
```bash
install_kubectl    # Downloads + installs latest stable
update_kubectl     # Removes old + installs latest
uninstall_kubectl  # Removes binary
reconcile_kubectl  # Migrates from package manager
```

**Version Discovery:**
- Queries https://dl.k8s.io/release/stable.txt
- Supports specific version pins via environment variable

### install_aws.sh

Installs AWS CLI v2.

**Installation Method:**
- Downloads official installer from awscli.amazonaws.com
- Runs bundled install script
- Installs to `/usr/local/aws-cli` by default

**Actions:**
```bash
install_aws    # Downloads + runs AWS installer
update_aws     # Runs installer with --update flag
uninstall_aws  # Removes AWS CLI installation
reconcile_aws  # Migrates from v1 or package manager to v2
```

### install_ansible.sh

Installs Ansible via pipx for isolated environment.

**Installation Method:**
- Uses pipx to install ansible-core
- Ensures Python 3.x available
- Installs to `~/.local/bin` via pipx

**Actions:**
```bash
install_ansible    # pipx install ansible-core
update_ansible     # pipx upgrade ansible-core
uninstall_ansible  # pipx uninstall ansible-core
reconcile_ansible  # Migrates from pip/apt to pipx
```

### install_brew.sh

Installs Homebrew package manager.

**Installation Method:**
- Runs official Homebrew installer script
- Supports macOS and Linux
- Configures shell initialization

**Actions:**
```bash
install_brew    # Installs Homebrew
update_brew     # brew update && brew upgrade
uninstall_brew  # Runs Homebrew uninstaller
reconcile_brew  # Re-installs to fix issues
```

**Post-Install:**
- Adds Homebrew to PATH in shell profile
- Runs `brew doctor` to validate installation

### install_uv.sh

Installs uv Python package manager.

**Installation Method:**
- Uses official installer: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Installs to `~/.local/bin/uv`
- Much faster than pip/pipx

**Actions:**
```bash
install_uv    # Runs official installer
update_uv     # uv self update
uninstall_uv  # Removes uv binary
reconcile_uv  # Migrates from pipx to official installer
```

## Common Workflows

### Initial Environment Setup

```bash
# Install core developer tools
./scripts/install_core.sh install

# Install language runtimes
./scripts/install_python.sh install
./scripts/install_rust.sh install
./scripts/install_node.sh install
./scripts/install_go.sh install

# Install cloud tools
./scripts/install_docker.sh install
./scripts/install_kubectl.sh install
./scripts/install_terraform.sh install
./scripts/install_aws.sh install
```

### Keep Tools Updated

```bash
# Update all tools
for script in scripts/install_*.sh; do
  "$script" update
done

# Or selectively update
./scripts/install_core.sh update
./scripts/install_python.sh update
./scripts/install_rust.sh update
```

### Migrate from Package Managers to Vendor Installers

```bash
# Reconcile removes package manager versions and installs from upstream
./scripts/install_core.sh reconcile
./scripts/install_python.sh reconcile
./scripts/install_rust.sh reconcile
./scripts/install_node.sh reconcile

# Reconcile single tool
./scripts/install_core.sh reconcile ripgrep
```

### Clean Uninstall

```bash
# Remove all tools
for script in scripts/install_*.sh; do
  "$script" uninstall
done

# Or selectively uninstall
./scripts/install_docker.sh uninstall
./scripts/install_terraform.sh uninstall
```

## Environment Variables

Installation scripts respect these environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `PREFIX` | Installation prefix | `PREFIX=$HOME/.local` |
| `BIN_DIR` | Binary directory | `BIN_DIR=/usr/local/bin` |
| `GITHUB_TOKEN` | GitHub API token for rate limits | `export GITHUB_TOKEN=ghp_xxx` |
| `FORCE` | Force reinstallation | `FORCE=1 ./install_core.sh install` |
| `*_VERSION` | Pin specific version | `GO_VERSION=1.22.0` |

## Best Practices

### 1. Use Vendor Installers When Available

Vendor installers provide better update mechanisms and version management:

✅ **Preferred:**
- Rust via rustup
- Node via nvm
- Python via deadsnakes PPA + uv
- uv via official installer

❌ **Avoid:**
- Distro-packaged Rust (often outdated)
- System Node (use nvm for version control)
- pip install --user (use pipx or uv)

### 2. Run Reconcile to Migrate

After initial setup with package managers, run `reconcile` to migrate:

```bash
# Check current installation
./scripts/../cli_audit.py | grep ripgrep
# ripgrep|14.0.0|apt/dpkg|14.1.1|github|OUTDATED

# Reconcile to vendor method
./scripts/install_core.sh reconcile ripgrep

# Verify upgrade
./scripts/../cli_audit.py | grep ripgrep
# ripgrep|14.1.1|rustup/cargo|14.1.1|github|UP-TO-DATE
```

### 3. Regularly Run Updates

Keep tools current to avoid security vulnerabilities:

```bash
# Weekly update routine
./scripts/install_python.sh update
./scripts/install_rust.sh update
./scripts/install_node.sh update
./scripts/install_core.sh update
```

### 4. Use GitHub Token for Rate Limits

Avoid GitHub API rate limiting during installations:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
./scripts/install_core.sh install
```

### 5. Test in Disposable Environments

Test installation scripts in containers before running on host:

```bash
docker run -it --rm ubuntu:24.04 bash
# Inside container:
apt-get update && apt-get install -y curl git
curl -fsSL https://raw.githubusercontent.com/.../install_core.sh | bash -s install
```

## Troubleshooting

### Script Fails with "Permission Denied"

**Cause:** Script trying to write to protected directory

**Solution:**
```bash
# Option 1: Allow passwordless sudo
sudo visudo
# Add: youruser ALL=(ALL) NOPASSWD: ALL

# Option 2: Use user prefix
PREFIX=$HOME/.local ./scripts/install_core.sh install
```

### GitHub Download Fails (403/429)

**Cause:** GitHub API rate limiting

**Solution:**
```bash
# Create personal access token at https://github.com/settings/tokens
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
./scripts/install_core.sh install
```

### Tool Not Found After Installation

**Cause:** Binary directory not in PATH

**Solution:**
```bash
# Check installation location
./scripts/install_core.sh install 2>&1 | grep "may need to add"

# Add to PATH (example for ~/.local/bin)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Build Fails for entr/parallel/ctags

**Cause:** Missing build dependencies

**Solution:**
```bash
# Install build essentials
sudo apt-get update
sudo apt-get install -y build-essential autoconf automake libtool pkg-config git
```

### Rust/Node Not Available After Install

**Cause:** Shell environment not reloaded

**Solution:**
```bash
# For Rust
source "$HOME/.cargo/env"

# For Node (nvm)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Or restart shell
exec $SHELL -l
```

### Docker Permission Denied

**Cause:** User not in docker group

**Solution:**
```bash
sudo usermod -aG docker $USER
newgrp docker  # Refresh groups without logout
docker run hello-world
```

## Integration with cli_audit.py

Installation scripts are designed to work with `cli_audit.py` for version tracking:

```bash
# Before installation
python3 cli_audit.py | grep ripgrep
# ripgrep|X|NOT INSTALLED|14.1.1|github|NOT INSTALLED

# Install
./scripts/install_core.sh install

# After installation
python3 cli_audit.py | grep ripgrep
# ripgrep|14.1.1 (150ms)|rustup/cargo|14.1.1 (220ms)|github|UP-TO-DATE
```

**Version Discovery:**
- `cli_audit.py` detects installation methods (rustup/cargo, nvm/npm, etc.)
- Scripts install to locations `cli_audit.py` expects
- Both use same upstream sources (GitHub, PyPI, crates.io)

**Reconcile Workflow:**
1. Run `cli_audit.py` to identify outdated/mismatched tools
2. Run script with `reconcile` action to fix
3. Run `cli_audit.py` again to verify

## See Also

- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System design and data flow
- **[API_REFERENCE.md](../docs/API_REFERENCE.md)** - Function signatures
- **[DEVELOPER_GUIDE.md](../docs/DEVELOPER_GUIDE.md)** - Development practices
- **[TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)** - Debugging guide
