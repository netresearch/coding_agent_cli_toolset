# Tool Ecosystem

Complete catalog of all tools tracked by AI CLI Preparation, organized by category with purpose, installation methods, and upgrade strategies.

## Overview

AI CLI Preparation tracks **50+ developer tools** across 10 categories, optimized for AI coding agent environments. Each tool is classified by installation method and tracked against upstream releases.

## Categories

- [Runtimes & Package Managers](#runtimes--package-managers) - Language runtimes and package managers (11 tools)
- [Search & Code Analysis](#search--code-analysis) - Code search and analysis tools (5 tools)
- [Editors & Utilities](#editors--utilities) - Editing helpers and diffs (8 tools)
- [JSON/YAML Processors](#jsonyaml-processors) - Data format tools (4 tools)
- [HTTP Clients](#http-clients) - HTTP/API testing tools (2 tools)
- [Automation & Watch](#automation--watch) - File watching and automation (4 tools)
- [Security & Compliance](#security--compliance) - Security scanning tools (4 tools)
- [Git Tools](#git-tools) - Version control and Git helpers (5 tools)
- [Formatters & Linters](#formatters--linters) - Code formatting and linting (7 tools)
- [Cloud & Infrastructure](#cloud--infrastructure) - Cloud and container tools (5 tools)

## Role-Based Presets

Quick audit subsets for specific roles:

```bash
# AI agent essentials
make audit-offline-agent-core

# Python development
make audit-offline-python-core

# Node.js development
make audit-offline-node-core

# Go development
make audit-offline-go-core

# Infrastructure/DevOps
make audit-offline-infra-core

# Security auditing
make audit-offline-security-core

# Data processing
make audit-offline-data-core
```

---

## Runtimes & Package Managers

### go
- **Purpose:** Go programming language compiler and runtime
- **Executable:** `go`
- **Upstream:** GitHub (golang/go)
- **Use Case:** Building Go applications, AI agents written in Go
- **Install:** `scripts/install_go.sh` or https://go.dev/dl/
- **Upgrade:** `scripts/install_go.sh update` or download new release

### uv
- **Purpose:** Ultra-fast Python package installer and resolver
- **Executable:** `uv`
- **Upstream:** GitHub (astral-sh/uv)
- **Use Case:** Modern Python package management, 10-100x faster than pip
- **Install:** `scripts/install_uv.sh` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Upgrade:** `uv self update` or `scripts/install_uv.sh update`

### python
- **Purpose:** Python programming language interpreter
- **Executable:** `python3`, `python`
- **Upstream:** GitHub (python/cpython)
- **Use Case:** Running Python scripts, AI agents, data processing
- **Install:** `scripts/install_python.sh` or system package manager
- **Upgrade:** `uv python install 3.14` or `scripts/install_python.sh update`

### pip
- **Purpose:** Python package installer
- **Executable:** `pip3`, `pip`
- **Upstream:** PyPI (pip)
- **Use Case:** Installing Python packages
- **Install:** Included with Python
- **Upgrade:** `python3 -m pip install --upgrade pip`

### pipx
- **Purpose:** Install and run Python applications in isolated environments
- **Executable:** `pipx`
- **Upstream:** PyPI (pipx)
- **Use Case:** Installing Python CLI tools without conflicts
- **Install:** `pip install --user pipx`
- **Upgrade:** `pipx upgrade-all`

### poetry
- **Purpose:** Python dependency management and packaging
- **Executable:** `poetry`
- **Upstream:** PyPI (poetry)
- **Use Case:** Managing Python project dependencies
- **Install:** `curl -sSL https://install.python-poetry.org | python3 -`
- **Upgrade:** `poetry self update`

### rust
- **Purpose:** Rust programming language compiler
- **Executable:** `rustc`
- **Upstream:** GitHub (rust-lang/rust)
- **Use Case:** Building Rust applications, fast CLI tools
- **Install:** `scripts/install_rust.sh` or `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Upgrade:** `rustup update` or `scripts/install_rust.sh update`

### node
- **Purpose:** Node.js JavaScript runtime
- **Executable:** `node`
- **Upstream:** GitHub (nodejs/node)
- **Use Case:** Running JavaScript/TypeScript, AI agent tooling
- **Install:** `scripts/install_node.sh` (via nvm)
- **Upgrade:** `nvm install node --latest-npm` or `scripts/install_node.sh update`

### npm
- **Purpose:** Node Package Manager
- **Executable:** `npm`
- **Upstream:** npm registry (npm)
- **Use Case:** Installing Node.js packages
- **Install:** Included with Node.js
- **Upgrade:** `npm install -g npm`

### pnpm
- **Purpose:** Fast, disk-space-efficient package manager
- **Executable:** `pnpm`
- **Upstream:** npm registry (pnpm)
- **Use Case:** Alternative to npm with better performance
- **Install:** `npm install -g pnpm`
- **Upgrade:** `pnpm self-update`

### yarn
- **Purpose:** Fast, reliable Node.js package manager
- **Executable:** `yarn`
- **Upstream:** npm registry (yarn)
- **Use Case:** Alternative to npm with workspace support
- **Install:** `npm install -g yarn`
- **Upgrade:** `yarn set version stable`

---

## Search & Code Analysis

### ripgrep
- **Purpose:** Extremely fast grep alternative with regex support
- **Executable:** `rg`
- **Upstream:** GitHub (BurntSushi/ripgrep)
- **Use Case:** Code search, AI agent file content scanning
- **Install:** `cargo install ripgrep` or system package manager
- **Upgrade:** `cargo install --force ripgrep`

### ast-grep
- **Purpose:** AST-based code search and refactoring tool
- **Executable:** `ast-grep`, `sg`
- **Upstream:** GitHub (ast-grep/ast-grep)
- **Use Case:** Semantic code search, structural find-and-replace
- **Install:** `cargo install ast-grep`
- **Upgrade:** `cargo install --force ast-grep`

### fzf
- **Purpose:** Command-line fuzzy finder
- **Executable:** `fzf`
- **Upstream:** GitHub (junegunn/fzf)
- **Use Case:** Interactive filtering, AI agent selection menus
- **Install:** `git clone https://github.com/junegunn/fzf.git ~/.fzf && ~/.fzf/install`
- **Upgrade:** `cd ~/.fzf && git pull && ./install`

### fd
- **Purpose:** Fast find alternative with better UX
- **Executable:** `fd`, `fdfind` (Debian)
- **Upstream:** GitHub (sharkdp/fd)
- **Use Case:** File search, faster than `find`
- **Install:** `cargo install fd-find` or `apt install fd-find`
- **Upgrade:** `cargo install --force fd-find`

### rga (ripgrep-all)
- **Purpose:** Search in PDFs, archives, documents
- **Executable:** `rga`
- **Upstream:** GitHub (phiresky/ripgrep-all)
- **Use Case:** Searching non-text files
- **Install:** `cargo install ripgrep_all`
- **Upgrade:** `cargo install --force ripgrep_all`

---

## Editors & Utilities

### ctags
- **Purpose:** Generate tag files for source code navigation
- **Executable:** `ctags`
- **Upstream:** GitHub (universal-ctags/ctags)
- **Use Case:** Code navigation, symbol indexing
- **Install:** Build from source or system package manager
- **Upgrade:** Update system package or rebuild

### delta
- **Purpose:** Syntax-highlighting pager for git diff output
- **Executable:** `delta`
- **Upstream:** GitHub (dandavison/delta)
- **Use Case:** Better git diffs with syntax highlighting
- **Install:** `cargo install git-delta`
- **Upgrade:** `cargo install --force git-delta`

### bat
- **Purpose:** cat clone with syntax highlighting and git integration
- **Executable:** `bat`, `batcat` (Debian)
- **Upstream:** GitHub (sharkdp/bat)
- **Use Case:** File viewing with syntax highlighting
- **Install:** `cargo install bat` or `apt install bat`
- **Upgrade:** `cargo install --force bat`

### sd
- **Purpose:** Intuitive find-and-replace CLI (sed alternative)
- **Executable:** `sd`
- **Upstream:** crates.io (sd)
- **Use Case:** Text replacement, simpler than sed
- **Install:** `cargo install sd`
- **Upgrade:** `cargo install --force sd`

### prename
- **Purpose:** Perl-based file renaming utility
- **Executable:** `file-rename`, `rename`
- **Upstream:** N/A (manual only)
- **Use Case:** Batch file renaming with regex
- **Install:** `apt install rename` or `cpan File::Rename`
- **Upgrade:** Update system package

### rename.ul
- **Purpose:** util-linux rename utility
- **Executable:** `rename.ul`
- **Upstream:** N/A (manual only)
- **Use Case:** Simple file renaming
- **Install:** Part of util-linux package
- **Upgrade:** Update system package

### sponge
- **Purpose:** Soak up stdin and write to file (from moreutils)
- **Executable:** `sponge`
- **Upstream:** N/A (manual only)
- **Use Case:** In-place file editing
- **Install:** `apt install moreutils`
- **Upgrade:** Update system package

### xsv
- **Purpose:** Fast CSV command line toolkit
- **Executable:** `xsv`
- **Upstream:** crates.io (xsv)
- **Use Case:** CSV data processing
- **Install:** `cargo install xsv`
- **Upgrade:** `cargo install --force xsv`

---

## JSON/YAML Processors

### jq
- **Purpose:** Command-line JSON processor
- **Executable:** `jq`
- **Upstream:** GitHub (jqlang/jq)
- **Use Case:** JSON parsing, filtering, transformation - essential for AI agents
- **Install:** `apt install jq` or build from source
- **Upgrade:** Update system package or rebuild

### yq
- **Purpose:** YAML processor (jq for YAML)
- **Executable:** `yq`
- **Upstream:** GitHub (mikefarah/yq)
- **Use Case:** YAML parsing and manipulation
- **Install:** `wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && chmod +x /usr/local/bin/yq`
- **Upgrade:** Re-download latest release

### dasel
- **Purpose:** Query and modify JSON, YAML, TOML, XML
- **Executable:** `dasel`
- **Upstream:** GitHub (TomWright/dasel)
- **Use Case:** Universal data format manipulation
- **Install:** `go install github.com/tomwright/dasel/v2/cmd/dasel@latest`
- **Upgrade:** `go install github.com/tomwright/dasel/v2/cmd/dasel@latest`

### fx
- **Purpose:** Interactive JSON viewer
- **Executable:** `fx`
- **Upstream:** GitHub (antonmedv/fx)
- **Use Case:** Browsing and exploring JSON data
- **Install:** `npm install -g fx`
- **Upgrade:** `npm update -g fx`

---

## HTTP Clients

### httpie
- **Purpose:** User-friendly HTTP CLI client
- **Executable:** `http`
- **Upstream:** PyPI (httpie)
- **Use Case:** API testing, HTTP debugging
- **Install:** `pipx install httpie`
- **Upgrade:** `pipx upgrade httpie`

### curlie
- **Purpose:** curl with httpie-like syntax
- **Executable:** `curlie`
- **Upstream:** GitHub (rs/curlie)
- **Use Case:** Quick HTTP requests with better UX
- **Install:** `go install github.com/rs/curlie@latest`
- **Upgrade:** `go install github.com/rs/curlie@latest`

---

## Automation & Watch

### entr
- **Purpose:** Run commands when files change
- **Executable:** `entr`
- **Upstream:** GitHub (eradman/entr)
- **Use Case:** File watching, auto-reloading
- **Install:** `apt install entr` or build from source
- **Upgrade:** Update system package

### watchexec
- **Purpose:** Execute commands in response to file modifications
- **Executable:** `watchexec`, `watchexec-cli`
- **Upstream:** GitHub (watchexec/watchexec)
- **Use Case:** Modern file watching with filters
- **Install:** `cargo install watchexec-cli`
- **Upgrade:** `cargo install --force watchexec-cli`

### direnv
- **Purpose:** Load/unload environment variables based on directory
- **Executable:** `direnv`
- **Upstream:** GitHub (direnv/direnv)
- **Use Case:** Per-project environment configuration
- **Install:** `apt install direnv` or build from source
- **Upgrade:** Update system package

### parallel
- **Purpose:** GNU parallel - execute jobs in parallel
- **Executable:** `parallel`
- **Upstream:** GNU FTP (parallel)
- **Use Case:** Parallel command execution
- **Install:** `apt install parallel`
- **Upgrade:** Update system package

### ansible
- **Purpose:** IT automation and configuration management
- **Executable:** `ansible`, `ansible-community`
- **Upstream:** PyPI (ansible)
- **Use Case:** Infrastructure automation
- **Install:** `pipx install ansible`
- **Upgrade:** `pipx upgrade ansible`

### ansible-core
- **Purpose:** Ansible core engine without collections
- **Executable:** `ansible`, `ansible-core`
- **Upstream:** PyPI (ansible-core)
- **Use Case:** Minimal Ansible installation
- **Install:** `pipx install ansible-core`
- **Upgrade:** `pipx upgrade ansible-core`

---

## Security & Compliance

### semgrep
- **Purpose:** Fast static analysis for finding bugs and enforcing code standards
- **Executable:** `semgrep`
- **Upstream:** PyPI (semgrep)
- **Use Case:** Security scanning, code pattern detection
- **Install:** `pipx install semgrep`
- **Upgrade:** `pipx upgrade semgrep`

### bandit
- **Purpose:** Security linter for Python code
- **Executable:** `bandit`
- **Upstream:** PyPI (bandit)
- **Use Case:** Finding security issues in Python
- **Install:** `pipx install bandit`
- **Upgrade:** `pipx upgrade bandit`

### gitleaks
- **Purpose:** Detect secrets in git repositories
- **Executable:** `gitleaks`
- **Upstream:** GitHub (gitleaks/gitleaks)
- **Use Case:** Preventing credential leaks
- **Install:** `brew install gitleaks` or download binary
- **Upgrade:** `brew upgrade gitleaks`

### trivy
- **Purpose:** Vulnerability scanner for containers and IaC
- **Executable:** `trivy`
- **Upstream:** GitHub (aquasecurity/trivy)
- **Use Case:** Container security scanning
- **Install:** Download from releases or `apt install trivy`
- **Upgrade:** Update system package or re-download

### pre-commit
- **Purpose:** Framework for managing git pre-commit hooks
- **Executable:** `pre-commit`
- **Upstream:** PyPI (pre-commit)
- **Use Case:** Automated code quality checks
- **Install:** `pipx install pre-commit`
- **Upgrade:** `pipx upgrade pre-commit`

---

## Git Tools

### git
- **Purpose:** Distributed version control system
- **Executable:** `git`
- **Upstream:** GitHub (git/git)
- **Use Case:** Version control, essential for AI agents
- **Install:** System package manager or build from source
- **Upgrade:** Update system package

### gh
- **Purpose:** GitHub CLI
- **Executable:** `gh`
- **Upstream:** GitHub (cli/cli)
- **Use Case:** GitHub operations from command line
- **Install:** `apt install gh` or download from releases
- **Upgrade:** `gh upgrade`

### glab
- **Purpose:** GitLab CLI
- **Executable:** `glab`
- **Upstream:** GitHub (profclems/glab)
- **Use Case:** GitLab operations from command line
- **Install:** `go install gitlab.com/gitlab-org/cli/cmd/glab@latest`
- **Upgrade:** `go install gitlab.com/gitlab-org/cli/cmd/glab@latest`

### git-absorb
- **Purpose:** Automatic fixup commits
- **Executable:** `git-absorb`
- **Upstream:** GitHub (tummychow/git-absorb)
- **Use Case:** Simplifying git history management
- **Install:** `cargo install git-absorb`
- **Upgrade:** `cargo install --force git-absorb`

### git-branchless
- **Purpose:** Tools for working with stacked branches
- **Executable:** `git-branchless`
- **Upstream:** GitHub (arxanas/git-branchless)
- **Use Case:** Advanced git workflows
- **Install:** `cargo install git-branchless`
- **Upgrade:** `cargo install --force git-branchless`

---

## Formatters & Linters

### black
- **Purpose:** Opinionated Python code formatter
- **Executable:** `black`
- **Upstream:** PyPI (black)
- **Use Case:** Python code formatting
- **Install:** `pipx install black`
- **Upgrade:** `pipx upgrade black`

### isort
- **Purpose:** Python import statement sorter
- **Executable:** `isort`
- **Upstream:** PyPI (isort)
- **Use Case:** Organizing Python imports
- **Install:** `pipx install isort`
- **Upgrade:** `pipx upgrade isort`

### flake8
- **Purpose:** Python linting tool
- **Executable:** `flake8`
- **Upstream:** PyPI (flake8)
- **Use Case:** Python code quality checks
- **Install:** `pipx install flake8`
- **Upgrade:** `pipx upgrade flake8`

### eslint
- **Purpose:** JavaScript/TypeScript linter
- **Executable:** `eslint`
- **Upstream:** GitHub (eslint/eslint)
- **Use Case:** JavaScript code quality
- **Install:** `npm install -g eslint`
- **Upgrade:** `npm update -g eslint`

### prettier
- **Purpose:** Opinionated code formatter for JS/TS/CSS/etc
- **Executable:** `prettier`
- **Upstream:** GitHub (prettier/prettier)
- **Use Case:** Multi-language code formatting
- **Install:** `npm install -g prettier`
- **Upgrade:** `npm update -g prettier`

### shfmt
- **Purpose:** Shell script formatter
- **Executable:** `shfmt`
- **Upstream:** GitHub (mvdan/sh)
- **Use Case:** Bash/shell script formatting
- **Install:** `go install mvdan.cc/sh/v3/cmd/shfmt@latest`
- **Upgrade:** `go install mvdan.cc/sh/v3/cmd/shfmt@latest`

### shellcheck
- **Purpose:** Shell script static analysis
- **Executable:** `shellcheck`
- **Upstream:** GitHub (koalaman/shellcheck)
- **Use Case:** Finding bugs in shell scripts
- **Install:** `apt install shellcheck` or download binary
- **Upgrade:** Update system package

---

## Cloud & Infrastructure

### aws
- **Purpose:** AWS Command Line Interface
- **Executable:** `aws`
- **Upstream:** GitHub (aws/aws-cli)
- **Use Case:** AWS cloud management
- **Install:** `scripts/install_aws.sh` or vendor installer
- **Upgrade:** `pip install --upgrade awscli` or `scripts/install_aws.sh update`

### kubectl
- **Purpose:** Kubernetes command-line tool
- **Executable:** `kubectl`
- **Upstream:** GitHub (kubernetes/kubernetes)
- **Use Case:** Kubernetes cluster management
- **Install:** `scripts/install_kubectl.sh` or vendor installer
- **Upgrade:** Download new binary or `scripts/install_kubectl.sh update`

### terraform
- **Purpose:** Infrastructure as Code tool
- **Executable:** `terraform`
- **Upstream:** GitHub (hashicorp/terraform)
- **Use Case:** Infrastructure provisioning
- **Install:** `scripts/install_terraform.sh` or download binary
- **Upgrade:** Download new binary or `scripts/install_terraform.sh update`

### docker
- **Purpose:** Container platform CLI
- **Executable:** `docker`
- **Upstream:** GitHub (docker/cli)
- **Use Case:** Container management
- **Install:** `scripts/install_docker.sh` or vendor installer
- **Upgrade:** Update system package or reinstall

### docker-compose
- **Purpose:** Multi-container Docker application management
- **Executable:** `docker-compose`, `docker compose`
- **Upstream:** GitHub (docker/compose)
- **Use Case:** Docker multi-container orchestration
- **Install:** `pip install docker-compose` or Docker plugin
- **Upgrade:** `pip install --upgrade docker-compose`

### dive
- **Purpose:** Docker image layer analyzer
- **Executable:** `dive`
- **Upstream:** GitHub (wagoodman/dive)
- **Use Case:** Analyzing and reducing Docker image sizes
- **Install:** `go install github.com/wagoodman/dive@latest`
- **Upgrade:** `go install github.com/wagoodman/dive@latest`

---

## Upgrade Strategies

### By Installation Method

**uv-managed tools:**
```bash
uv tool upgrade --all
```

**pipx-managed tools:**
```bash
pipx upgrade-all
```

**cargo-managed tools:**
```bash
cargo install-update -a  # requires cargo-update
```

**npm global tools:**
```bash
npm update -g
```

**go-installed tools:**
```bash
# Re-install with @latest
go install <module>@latest
```

### System-Wide Upgrade

```bash
# Update audit snapshot
make update

# Review outdated tools
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.[] | select(.status == "OUTDATED")'

# Use interactive upgrade guide
make upgrade
```

---

## See Also

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Makefile targets and installation scripts
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Adding new tools
- **[API_REFERENCE.md](API_REFERENCE.md)** - Tool dataclass structure
