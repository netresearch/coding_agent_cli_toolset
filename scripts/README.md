# Installation Scripts Documentation

## Overview

The AI CLI Preparation project uses a **catalog-based installation system** that provides consistent, declarative management of 65+ developer tools. All tools are defined in individual catalog entries (`catalog/<tool>.json`) with installation delegated to generic, reusable installers.

## Key Concepts

### Catalog System
- **Single Source of Truth**: Every tool has a `catalog/<tool>.json` entry with metadata
- **Generic Installers**: One installer script per method handles all tools of that type
- **Tag-Based Grouping**: Tools tagged for logical grouping (`core`, `runtime`, `security`, etc.)
- **No Duplication**: Tool-specific code eliminated in favor of data-driven configuration

### Installation Strategy
Configurable via `INSTALL_STRATEGY` in `.env`:
- **USER** (default): Install to `~/.local/bin` (no sudo required)
- **GLOBAL**: Install to `/usr/local/bin` (requires sudo)
- **CURRENT**: Keep tool where currently installed
- **PROJECT**: Install to `./.local/bin` (project-local)

## Core Scripts

| Script | Purpose |
|--------|---------|
| `install_tool.sh` | **Main orchestrator** - reads catalog, delegates to installers |
| `install_group.sh` | **Group installer** - installs all tools with a specific tag |
| `installers/*.sh` | **Generic installers** - one per installation method |

## Usage Examples

### Install Single Tool
```bash
./scripts/install_tool.sh ripgrep
./scripts/install_tool.sh kubectl
./scripts/install_tool.sh python
```

### Install by Group/Tag
```bash
# Install all core tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
./scripts/install_group.sh core

# List available tags
./scripts/install_group.sh
```

### Configure Installation Location
```bash
# Install to user directory (default)
INSTALL_STRATEGY=USER ./scripts/install_tool.sh fd

# Install to system directory (requires sudo)
INSTALL_STRATEGY=GLOBAL ./scripts/install_tool.sh fd

# Keep where currently installed
INSTALL_STRATEGY=CURRENT ./scripts/install_tool.sh fd
```

## Catalog Entry Format

Each tool has a JSON catalog entry with:

```json
{
  "name": "tool-name",
  "install_method": "github_release_binary",
  "description": "Tool description",
  "homepage": "https://...",
  "binary_name": "tool",
  "download_url_template": "https://.../download/{version}/{os}-{arch}",
  "arch_map": {
    "x86_64": "amd64",
    "aarch64": "arm64"
  },
  "tags": ["core", "search"]
}
```

## Installation Methods

The system supports 9 installation methods:

| Method | Tools | Example |
|--------|-------|---------|
| `github_release_binary` | 30+ tools | fd, fzf, ripgrep, kubectl, terraform |
| `dedicated_script` | 10 tools | go, rust, python, node, docker |
| `package_manager` | 10 tools | pip, npm, yarn, gem, composer |
| `uv_tool` | 10 tools | black, ruff, bandit, isort |
| `hashicorp_zip` | 1 tool | terraform (alternative method) |
| `aws_installer` | 1 tool | aws (official AWS CLI installer) |
| `npm_global` | 1 tool | prettier |
| `script` | 1 tool | parallel (GNU) |
| `pipx_tool` | 1 tool | ansible (via pipx) |

### github_release_binary
Downloads pre-compiled binaries from GitHub releases. Handles:
- Architecture mapping (x86_64 → amd64, aarch64 → arm64)
- Archive extraction (.tar.gz, .zip)
- Binary renaming and permission setting
- Version detection from GitHub API

**Installer:** `scripts/installers/github_release_binary.sh`

### dedicated_script
For complex tools with existing installation scripts:
- Runtime environments (go, rust, python, node)
- Docker (official install script)
- System tools (git, ctags, gam)

**Installer:** `scripts/installers/dedicated_script.sh` (delegates to existing scripts)

### package_manager
Installs via system package managers (apt/brew/dnf/pacman):
- Package managers themselves (pip, npm, yarn, gem, composer)
- System utilities (sponge from moreutils)

**Installer:** `scripts/installers/package_manager.sh`

### uv_tool
Python CLI tools installed via `uv tool install`:
- Python formatters/linters (black, ruff, isort, flake8)
- Security scanners (bandit)
- Build tools (poetry)

**Installer:** `scripts/installers/uv_tool.sh`

## Tool Tags

Tools are tagged for logical grouping:

| Tag | Tools |
|-----|-------|
| `core` | fd, fzf, ripgrep, jq, yq, bat, delta, just |
| `runtime` | go, rust, python, node |
| `security` | trivy, gitleaks, bandit, semgrep, tfsec |
| `git` | git, gh, glab, git-lfs, git-absorb, git-branchless |
| `cloud` | aws, kubectl, terraform, docker |
| `text-utils` | bat, yq, jq, fx, dasel |
| `search` | fd, ripgrep, rga, ast-grep |

## Migration Guide

### From Old install_core.sh
```bash
# Old way
./scripts/install_core.sh install

# New way (install by tag)
./scripts/install_group.sh core

# Or individual tools
./scripts/install_tool.sh fd
./scripts/install_tool.sh ripgrep
```

### From Dedicated Scripts
```bash
# Old way
./scripts/install_kubectl.sh
./scripts/install_terraform.sh

# New way
./scripts/install_tool.sh kubectl
./scripts/install_tool.sh terraform
```

## Adding New Tools

1. Create catalog entry `catalog/newtool.json`:
```json
{
  "name": "newtool",
  "install_method": "github_release_binary",
  "description": "Description",
  "homepage": "https://...",
  "github_repo": "owner/repo",
  "binary_name": "newtool",
  "download_url_template": "https://github.com/owner/repo/releases/download/{version}/newtool-{os}-{arch}",
  "tags": ["category"]
}
```

2. Install:
```bash
./scripts/install_tool.sh newtool
```

That's it! No code changes needed.

## Architecture Benefits

✅ **Single Source of Truth**: All tool metadata in catalog
✅ **95% Code Reduction**: Eliminated 1150+ lines of duplicated code
✅ **Easy to Add Tools**: Just add catalog entry, no code changes
✅ **Consistent Interface**: `install_tool.sh TOOL` for everything
✅ **Tag-Based Grouping**: No hard-coded tool lists
✅ **Configurable Locations**: INSTALL_STRATEGY controls install paths
✅ **Generic Installers**: Reusable logic for common patterns

## Troubleshooting

### Tool Not Found
```bash
./scripts/install_tool.sh unknown
# Error: No catalog entry found
# Available tools: fd fzf ripgrep kubectl ...
```

### List Available Tags
```bash
./scripts/install_group.sh
# Available tags:
#   - core
#   - runtime
#   - security
#   - git
```

### Installation Fails
```bash
# Check catalog entry
cat catalog/toolname.json

# Verify installer exists
ls scripts/installers/github_release_binary.sh
```

## See Also

- **[catalog/README.md](../catalog/README.md)** - Catalog format and conventions
- **[catalog/COVERAGE.md](../catalog/COVERAGE.md)** - Complete tool inventory
- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System design details
