PYTHON ?= python3

# Load defaults in precedence order: .env.default < .env (highest)
-include .env.default
-include .env

.PHONY: audit audit-offline audit-only-% audit-offline-% lint fmt help update audit-auto upgrade

help: ## Show available targets
	@awk 'BEGIN{FS=":.*##";print "\nUsage: make <target>\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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

update: ## Collect fresh data and write snapshot (~10s)
	@bash -c 'set -o pipefail; CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py' || true

SNAP_FILE?=$(shell python3 -c "import os;print(os.environ.get('CLI_AUDIT_SNAPSHOT_FILE','tools_snapshot.json'))")

audit-auto: ## Update snapshot if missing, then render
	@if [ ! -f "$(SNAP_FILE)" ]; then \
		echo "# snapshot missing: $(SNAP_FILE); running update..."; \
		CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py || true; \
	fi; \
	CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header || true

upgrade: scripts-perms ## Run interactive upgrade guide
	@bash scripts/guide.sh

guide: upgrade ## Alias for upgrade (deprecated)

lint: ## Run pyflakes lint checks
	@command -v pyflakes >/dev/null 2>&1 && pyflakes cli_audit.py || echo "pyflakes not installed; skipping"

fmt: ## Format code (placeholder)
	@echo "Nothing to format"

scripts-perms: ## Ensure scripts are executable
	chmod +x scripts/*.sh || true
	chmod +x scripts/lib/*.sh || true

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
