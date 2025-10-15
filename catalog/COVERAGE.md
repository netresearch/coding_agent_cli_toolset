# Catalog Coverage

This file documents which tools have catalog entries and which use dedicated install scripts.

## Tools with Catalog Entries (54)

These tools use the catalog-based installation system with generic installers:

- ansible, ast-grep, aws, bandit, bat, black, codex, composer, curlie, dasel
- delta, direnv, dive, entr, fd, flake8, fx, fzf, gem, gh, git-absorb
- git-branchless, git-lfs, gitleaks, glab, golangci-lint, httpie, isort, just
- kubectl, ninja, npm, parallel, pip, pipx, pnpm, poetry, pre-commit, prettier
- rga, ripgrep, ruff, sd, semgrep, shellcheck, shfmt, sponge, terraform, tfsec
- trivy, watchexec, xsv, yarn, yq

## Tools with Dedicated Install Scripts

### Runtime Environments
These have their own complex installers in `scripts/`:
- **go** - `install_go.sh`
- **rust** - `install_rust.sh`
- **python** - `install_python.sh`
- **node** - `install_node.sh`

### Package Managers
Most now in catalog, one dedicated script:
- **uv** - `install_uv.sh` (special bootstrap installer)
- All others (pip, pipx, npm, pnpm, yarn, gem, composer, poetry, sponge) - Now in catalog!

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
- **package_manager**: 10 tools (pip, pipx, poetry, npm, pnpm, yarn, gem, composer, sponge, entr)
- **hashicorp_zip**: 1 tool (terraform)
- **aws_installer**: 1 tool (aws)
- **npm_global**: 1 tool (prettier)
- **script**: 1 tool (parallel)
- **dedicated_script**: 10 tools (runtimes: go, rust, python, node; special: uv, docker, git, ctags, gam)
- **system_package**: 2 tools (cscope, rename variants)

## Total: 69 tools tracked

- **54 tools** have catalog entries
- **10 tools** use dedicated scripts (runtimes + special cases)
- **5 tools** are system packages only

All installable tools either have catalog entries or use appropriate dedicated scripts.
