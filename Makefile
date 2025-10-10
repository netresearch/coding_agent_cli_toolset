PYTHON ?= python3

# Load defaults in precedence order: .env.default < .env (highest)
-include .env.default
-include .env

.PHONY: user-help help audit audit-offline audit-% audit-offline-% update upgrade guide \
	test test-unit test-integration test-coverage test-watch test-failed \
	lint lint-code lint-types lint-security format format-check \
	install install-dev install-core install-python install-node install-go \
	install-aws install-kubectl install-terraform install-ansible install-docker \
	install-brew install-rust update-% uninstall-% reconcile-% \
	build build-dist build-wheel check-dist publish publish-test publish-prod \
	clean clean-build clean-test clean-pyc clean-all \
	scripts-perms audit-auto

# ============================================================================
# HELP & OVERVIEW
# ============================================================================

.DEFAULT_GOAL := user-help

user-help: ## Show user commands only (default)
	@echo ""
	@echo "AI CLI Preparation - User Commands"
	@echo "==================================="
	@echo ""
	@awk 'BEGIN{FS=":.*##"; section=""} \
		/^## / {section=$$0; gsub(/^## /, "", section)} \
		/^[a-zA-Z0-9_-]+:.*##/ && section=="USER" {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "\033[90mRun '\033[0m\033[1mmake help\033[0m\033[90m' for development and maintenance commands.\033[0m"
	@echo ""

help: ## Show complete help with all commands
	@echo ""
	@echo "AI CLI Preparation - Makefile Commands"
	@echo "======================================"
	@echo ""
	@echo "USER COMMANDS (Application Functionality):"
	@echo "-------------------------------------------"
	@awk 'BEGIN{FS=":.*##"; section=""} \
		/^## / {section=$$0; gsub(/^## /, "", section)} \
		/^[a-zA-Z0-9_-]+:.*##/ && section=="USER" {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "DEVELOPMENT COMMANDS (Build, Test, Quality):"
	@echo "---------------------------------------------"
	@awk 'BEGIN{FS=":.*##"; section=""} \
		/^## / {section=$$0; gsub(/^## /, "", section)} \
		/^[a-zA-Z0-9_-]+:.*##/ && section=="DEV" {printf "  \033[33m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "MAINTENANCE COMMANDS (Package, Deploy, Clean):"
	@echo "-----------------------------------------------"
	@awk 'BEGIN{FS=":.*##"; section=""} \
		/^## / {section=$$0; gsub(/^## /, "", section)} \
		/^[a-zA-Z0-9_-]+:.*##/ && section=="MAINT" {printf "  \033[35m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# ============================================================================
# USER COMMANDS - Application Functionality
# ============================================================================
## USER

audit: ## Render audit from snapshot (no network, <100ms)
	@bash -c 'set -o pipefail; CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

audit-offline: ## Offline audit with hints (fast local scan)
	@bash -c 'set -o pipefail; CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

audit-%: scripts-perms ## Audit single tool (e.g., make audit-ripgrep)
	@bash -c 'set -o pipefail; CLI_AUDIT_RENDER=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py --only $* | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

audit-offline-%: scripts-perms ## Offline audit subset (e.g., make audit-offline-python-core)
	@bash -c 'set -o pipefail; CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py --only $* | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

SNAP_FILE?=$(shell python3 -c "import os;print(os.environ.get('CLI_AUDIT_SNAPSHOT_FILE','tools_snapshot.json'))")

audit-auto: ## Update snapshot if missing, then render
	@if [ ! -f "$(SNAP_FILE)" ]; then \
		echo "# snapshot missing: $(SNAP_FILE); running update..."; \
		CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py || true; \
	fi; \
	CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header || true

update: ## Collect fresh data and write snapshot (~10s)
	@bash -c 'set -o pipefail; CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py' || true

upgrade: scripts-perms ## Run interactive upgrade guide
	@bash scripts/guide.sh

guide: upgrade ## Alias for upgrade (deprecated)

install-core: scripts-perms ## Install core tools (fd, fzf, ripgrep, jq, yq, bat, delta, just)
	./scripts/install_core.sh

install-python: scripts-perms ## Install Python toolchain via uv
	./scripts/install_python.sh

install-node: scripts-perms ## Install Node.js via nvm
	./scripts/install_node.sh

install-go: scripts-perms ## Install Go runtime
	./scripts/install_go.sh

install-aws: scripts-perms ## Install AWS CLI
	./scripts/install_aws.sh

install-kubectl: scripts-perms ## Install Kubernetes CLI
	./scripts/install_kubectl.sh

install-terraform: scripts-perms ## Install Terraform
	./scripts/install_terraform.sh

install-ansible: scripts-perms ## Install Ansible
	./scripts/install_ansible.sh

install-docker: scripts-perms ## Install Docker
	./scripts/install_docker.sh

install-brew: scripts-perms ## Install Homebrew (macOS/Linux)
	./scripts/install_brew.sh

install-rust: scripts-perms ## Install Rust via rustup
	./scripts/install_rust.sh

update-%: scripts-perms ## Update tool (e.g., make update-python)
	./scripts/install_$*.sh update

uninstall-%: scripts-perms ## Uninstall tool (e.g., make uninstall-python)
	./scripts/install_$*.sh uninstall

reconcile-%: scripts-perms ## Reconcile tool installation (e.g., make reconcile-node)
	./scripts/install_$*.sh reconcile

# ============================================================================
# DEVELOPMENT COMMANDS - Testing, Linting, Formatting
# ============================================================================
## DEV

test: ## Run all tests
	$(PYTHON) -m pytest

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/ -k "not integration"

test-integration: ## Run integration tests only
	$(PYTHON) -m pytest tests/integration/

test-coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest --cov=cli_audit --cov-report=term --cov-report=html

test-coverage-xml: ## Run tests with XML coverage (for CI)
	$(PYTHON) -m pytest --cov=cli_audit --cov-report=xml --cov-report=term

test-watch: ## Run tests in watch mode (requires pytest-watch)
	$(PYTHON) -m pytest_watch

test-failed: ## Re-run only failed tests
	$(PYTHON) -m pytest --lf

test-verbose: ## Run tests with verbose output
	$(PYTHON) -m pytest -vv -s

test-parallel: ## Run tests in parallel (requires pytest-xdist)
	$(PYTHON) -m pytest -n auto

lint: lint-code lint-types lint-security ## Run all linting checks

lint-code: ## Run flake8 code linting
	@echo "→ Running flake8..."
	@$(PYTHON) -m flake8 cli_audit tests || echo "flake8 checks failed"

lint-types: ## Run mypy type checking
	@echo "→ Running mypy..."
	@$(PYTHON) -m mypy cli_audit || echo "mypy checks failed"

lint-security: ## Run bandit security checks
	@echo "→ Running bandit..."
	@$(PYTHON) -m bandit -r cli_audit -ll || echo "bandit checks failed"

format: ## Format code with black and isort
	@echo "→ Running black..."
	@$(PYTHON) -m black cli_audit tests
	@echo "→ Running isort..."
	@$(PYTHON) -m isort cli_audit tests

format-check: ## Check code formatting without changes
	@echo "→ Checking black..."
	@$(PYTHON) -m black --check cli_audit tests
	@echo "→ Checking isort..."
	@$(PYTHON) -m isort --check-only cli_audit tests

install: ## Install package in editable mode
	$(PYTHON) -m pip install -e .

install-dev: ## Install package with development dependencies
	$(PYTHON) -m pip install -e ".[dev]"

# ============================================================================
# MAINTENANCE COMMANDS - Build, Package, Deploy, Clean
# ============================================================================
## MAINT

build: clean-build ## Build source and wheel distributions
	$(PYTHON) -m build

build-dist: build ## Alias for build

build-wheel: clean-build ## Build wheel distribution only
	$(PYTHON) -m build --wheel

check-dist: build ## Check distribution for PyPI compatibility
	$(PYTHON) -m twine check dist/*

publish-test: check-dist ## Publish to TestPyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

publish-prod: check-dist ## Publish to production PyPI
	$(PYTHON) -m twine upload dist/*

clean: clean-build clean-test clean-pyc ## Remove all build, test, and Python artifacts

clean-build: ## Remove build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/

clean-test: ## Remove test and coverage artifacts
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf coverage.xml

clean-pyc: ## Remove Python file artifacts
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} + || true

clean-all: clean ## Remove all artifacts including virtual environments
	rm -rf .venv/
	rm -rf venv/
	rm -rf .tox/

scripts-perms: ## Ensure scripts are executable
	@chmod +x scripts/*.sh 2>/dev/null || true
	@chmod +x scripts/lib/*.sh 2>/dev/null || true
