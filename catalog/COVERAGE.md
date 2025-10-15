# Catalog Coverage

This file documents which tools have catalog entries and which use dedicated install scripts.

## Tools with Catalog Entries (45)

These tools use the catalog-based installation system with generic installers:

- ansible, ast-grep, aws, bandit, bat, black, codex, curlie, dasel, delta
- direnv, dive, entr, fd, flake8, fx, fzf, gh, git-absorb, git-branchless
- git-lfs, gitleaks, glab, golangci-lint, httpie, isort, just, kubectl
- ninja, parallel, pre-commit, prettier, rga, ripgrep, ruff, sd, semgrep
- shellcheck, shfmt, terraform, tfsec, trivy, watchexec, xsv, yq

## Tools with Dedicated Install Scripts

### Runtime Environments
These have their own complex installers in `scripts/`:
- **go** - `install_go.sh`
- **rust** - `install_rust.sh`
- **python** - `install_python.sh`
- **node** - `install_node.sh`

### Package Managers
These are either installed with runtimes or have dedicated scripts:
- **pip** - Installed with Python
- **pipx** - Python tool
- **uv** - `install_uv.sh`
- **npm** - Installed with Node.js
- **pnpm** - Node.js package manager
- **yarn** - Node.js package manager
- **gem** - Installed with Ruby
- **composer** - PHP package manager
- **poetry** - Python package manager

### Docker Tools
- **docker** - `install_docker.sh` (uses official Docker install script)
- **docker-compose** - Typically installed with Docker

### System Tools
- **git** - System package (apt/dnf/brew)
- **ctags** - System package
- **sponge** - Part of moreutils package
- **prename** - System package (Perl rename)
- **rename.ul** - System package (util-linux rename)

### Other
- **gam** - Google Apps Manager (special installation)
- **claude** - Claude CLI (special installation)
- **ansible-core** - Subset of ansible package
- **eslint** - Node.js package (installed via npm)

## Installation Method Distribution

- **github_release_binary**: 31 tools
- **uv_tool**: 8 tools (Python CLI tools)
- **hashicorp_zip**: 1 tool (terraform)
- **aws_installer**: 1 tool (aws)
- **npm_global**: 1 tool (prettier)
- **script**: 1 tool (parallel)
- **package_manager**: 1 tool (entr)
- **dedicated_script**: 14 tools (runtimes, package managers, docker, etc.)
- **system_package**: 5 tools (git, ctags, sponge, rename variants)

## Total: 69 tools tracked

All installable tools either have catalog entries or use appropriate dedicated scripts.
