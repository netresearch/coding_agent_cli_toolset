# Suggested Commands

## Essential Commands (Daily Use)

### Audit Operations
```bash
make audit               # Render from snapshot (no network, <100ms)
make update              # Collect fresh data, write snapshot (~3-10s)
make audit-offline       # Offline audit with remediation hints
make audit-auto          # Update snapshot if missing, then render
make upgrade             # Interactive upgrade guide with remediation
```

### Single Tool Audits
```bash
make audit-ripgrep       # Audit specific tool
make audit-python        # Audit Python runtime
make audit-node          # Audit Node.js runtime
```

### Role-Based Presets
```bash
make audit-agent-core    # Core agent tools (fd, fzf, ripgrep, jq, etc.)
make audit-python-core   # Python ecosystem (python, pip, pipx, black, etc.)
make audit-node-core     # Node.js ecosystem (node, npm, pnpm, eslint, etc.)
make audit-go-core       # Go ecosystem (go, gofmt, gopls, etc.)
make audit-infra-core    # Infrastructure tools (docker, kubectl, terraform)
make audit-security-core # Security tools (semgrep, bandit, gitleaks, trivy)
```

### Offline Mode
```bash
make audit-offline-python-core  # Offline with role-based preset
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py  # Force offline mode
```

## Installation Scripts

### Core Tools
```bash
make scripts-perms       # Make scripts executable (run once)
make install-core        # Install core tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
```

### Language Runtimes
```bash
make install-python      # Install Python via uv (preferred) or pyenv
make install-node        # Install Node.js via nvm
make install-go          # Install Go via official installer
make install-rust        # Install Rust via rustup
make install-ruby        # Install Ruby via rbenv
```

### Higher-Level Tools
```bash
make install-aws         # Install AWS CLI v2
make install-kubectl     # Install kubectl
make install-terraform   # Install Terraform
make install-ansible     # Install Ansible
make install-docker      # Install Docker
make install-brew        # Install Homebrew (macOS/Linux)
```

### Actions (Install/Update/Uninstall/Reconcile)
```bash
# Update existing installations
make update-python       # Update Python toolchain
make update-node         # Update Node.js toolchain
make update-core         # Update core tools

# Uninstall
make uninstall-node      # Remove Node.js

# Reconcile (remove duplicates, prefer one method)
make reconcile-node      # Remove distro Node, keep nvm-managed
make reconcile-rust      # Remove distro Rust, keep rustup-managed
```

## Auto-Update (Package Managers)

### Detection and Updates
```bash
make auto-update-detect          # Detect all installed package managers
make auto-update                 # Update all package managers and packages
make auto-update-dry-run         # Preview updates without making changes
make auto-update-system-only     # Update only system package managers (apt, brew, snap, flatpak)
make auto-update-skip-system     # Update all except system package managers
```

### Manual Script Usage
```bash
# Detect package managers
./scripts/auto_update.sh detect

# Update specific package manager
./scripts/auto_update.sh cargo
./scripts/auto_update.sh npm
./scripts/auto_update.sh brew

# With options
./scripts/auto_update.sh --dry-run update
./scripts/auto_update.sh --verbose update
./scripts/auto_update.sh --skip-system update
```

## Development Commands

### Linting and Formatting
```bash
make lint                # Run flake8
make lint-code           # Run flake8 on main code
make lint-types          # Run mypy type checking
make lint-security       # Run bandit security checks
make format              # Run black + isort (optional)
make format-check        # Check formatting without changes
```

### Testing
```bash
make test                # Run all tests (when test suite added)
make test-unit           # Run unit tests
make test-integration    # Run integration tests
make test-coverage       # Run with coverage report
make test-watch          # Watch mode (continuous testing)
make test-failed         # Re-run only failed tests

# Smoke test (current minimal test)
./scripts/test_smoke.sh
```

### Build and Package
```bash
make build               # Build distribution packages
make build-dist          # Build source distribution
make build-wheel         # Build wheel distribution
make check-dist          # Validate built distributions
```

### Publishing (Maintainers)
```bash
make publish-test        # Publish to TestPyPI
make publish-prod        # Publish to PyPI (production)
```

### Cleanup
```bash
make clean               # Clean all generated files
make clean-build         # Remove build artifacts
make clean-test          # Remove test artifacts
make clean-pyc           # Remove Python cache files
make clean-all           # Nuclear clean (all + node_modules)
```

## Direct Python Invocation

### Basic Usage
```bash
# Table output (default)
python3 cli_audit.py | python3 smart_column.py -s "|" -t --right 3,5 --header

# JSON output
CLI_AUDIT_JSON=1 python3 cli_audit.py | jq '.'

# Specific tools only
python3 cli_audit.py --only ripgrep,fd,jq

# Role-based preset
python3 cli_audit.py --only agent-core
```

### Mode Toggles
```bash
# Collect-only (write snapshot)
CLI_AUDIT_COLLECT=1 python3 cli_audit.py

# Render-only (read snapshot)
CLI_AUDIT_RENDER=1 python3 cli_audit.py

# Offline mode
CLI_AUDIT_OFFLINE=1 python3 cli_audit.py

# Debug mode
CLI_AUDIT_DEBUG=1 python3 cli_audit.py --only ripgrep

# Fast mode (skip slow operations)
CLI_AUDIT_FAST=1 python3 cli_audit.py
```

### Output Options
```bash
# Disable hints
CLI_AUDIT_HINTS=0 python3 cli_audit.py

# Show timings
CLI_AUDIT_TIMINGS=1 python3 cli_audit.py

# Sort alphabetically (default is definition order)
CLI_AUDIT_SORT=alpha python3 cli_audit.py

# Disable emoji icons
CLI_AUDIT_EMOJI=0 python3 cli_audit.py

# Disable clickable links
CLI_AUDIT_LINKS=0 python3 cli_audit.py
```

## Git Commands

### Branch Management
```bash
git status               # Check working directory status
git branch               # List branches
git branch --show-current # Show current branch name
git checkout -b feature/name # Create and switch to feature branch
```

### Commit Workflow
```bash
git add <files>          # Stage changes
git diff --staged        # Review staged changes
git commit -m "type(scope): description"  # Commit with message
git push -u origin branch-name  # Push new branch
```

### Viewing History
```bash
git log --oneline        # Compact commit history
git log -10              # Last 10 commits
git diff                 # View unstaged changes
git diff HEAD~1          # Compare with previous commit
```

## Environment Setup

### Direnv (Optional)
```bash
direnv allow             # Allow .envrc in current directory
direnv reload            # Reload environment
```

### Python Virtual Environment (Optional)
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate

# Using venv
python3 -m venv .venv
source .venv/bin/activate
```

### Development Dependencies
```bash
# Install dev dependencies (optional)
pip install -e ".[dev]"
```

## Useful Linux Commands (System Context)

### File Operations
```bash
ls -lah                  # List files with details
find . -name "*.py"      # Find Python files
grep -r "pattern" .      # Search for pattern recursively
cat file.txt             # Display file contents
head -n 20 file.txt      # First 20 lines
tail -n 20 file.txt      # Last 20 lines
```

### Process Management
```bash
ps aux | grep python     # Find Python processes
kill -9 PID              # Force kill process
top                      # Monitor system resources
htop                     # Interactive process viewer (if installed)
```

### Network
```bash
curl -I https://example.com  # HTTP headers
wget https://example.com/file # Download file
netstat -tlnp            # List listening ports
```

### Permissions
```bash
chmod +x script.sh       # Make script executable
chmod 644 file.txt       # Set file permissions (rw-r--r--)
chown user:group file    # Change ownership
```

## Help and Documentation

### Built-in Help
```bash
make help                # Show all Makefile targets
make user-help           # Show user commands only (default)
python3 cli_audit.py --help  # CLI help text
```

### Documentation Files
```bash
# Entry points
cat README.md            # Main user documentation
cat AGENTS.md            # Root agent guidance
cat scripts/AGENTS.md    # Script-specific agent guidance

# Comprehensive docs
cat docs/INDEX.md        # Documentation index by role/task
cat docs/QUICK_REFERENCE.md # One-liner command reference
cat docs/ARCHITECTURE.md # System design and patterns
cat docs/DEVELOPER_GUIDE.md # Contribution guidelines
cat docs/TROUBLESHOOTING.md # Common issues and solutions
```

## Complete Workflow Example

### New Machine Setup
```bash
# 1. Clone repository
git clone https://github.com/your-org/ai_cli_preparation.git
cd ai_cli_preparation

# 2. Make scripts executable
make scripts-perms

# 3. Install core tools
make install-core

# 4. Install language runtimes
make install-python
make install-node

# 5. Update snapshot
make update

# 6. Run audit
make audit

# 7. Install any missing/outdated tools
make upgrade  # Interactive guide
```

### Daily Development
```bash
# 1. Check tool status
make audit

# 2. Update specific tools
make install-python  # or make update-python

# 3. Re-audit
make audit

# 4. Update all package managers
make auto-update-dry-run  # Preview
make auto-update          # Execute
```

### Contributing Code
```bash
# 1. Create feature branch
git checkout -b feature/improve-caching

# 2. Make changes
# ... edit files ...

# 3. Run linter
make lint

# 4. Test changes
./scripts/test_smoke.sh

# 5. Commit
git add <files>
git commit -m "feat(cache): improve version lookup performance"

# 6. Push and create PR
git push -u origin feature/improve-caching
```