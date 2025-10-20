# ============================================================================
# USER COMMANDS - Application Functionality
# ============================================================================
## USER

audit: ## Render audit from snapshot (no network, <100ms)
	@bash -c ' \
		SNAP_FILE=$${CLI_AUDIT_SNAPSHOT_FILE:-tools_snapshot.json}; \
		CACHE_MAX_AGE_HOURS=$${CACHE_MAX_AGE_HOURS:-24}; \
		if [ ! -f "$$SNAP_FILE" ]; then \
			echo "⚠️  Warning: Snapshot cache missing ($$SNAP_FILE)" >&2; \
			echo "   Run '\''make update'\'' first to populate the cache." >&2; \
		else \
			now=$$(date +%s); \
			snap_time=$$(stat -c %Y "$$SNAP_FILE" 2>/dev/null || stat -f %m "$$SNAP_FILE" 2>/dev/null || echo 0); \
			age_seconds=$$((now - snap_time)); \
			age_hours=$$((age_seconds / 3600)); \
			if [ $$age_hours -gt $$CACHE_MAX_AGE_HOURS ]; then \
				echo "⚠️  Warning: Snapshot cache is $${age_hours} hours old (threshold: $${CACHE_MAX_AGE_HOURS}h)" >&2; \
				echo "   Consider running '\''make update'\'' for fresh version data." >&2; \
			fi; \
		fi; \
		set -o pipefail; CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
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

update: ## Collect fresh version data with network calls and update snapshot (~10s)
	@echo "→ Collecting fresh version data from upstream sources..." >&2
	@bash -c 'set -o pipefail; CLI_AUDIT_COLLECT=1 CLI_AUDIT_TIMINGS=1 $(PYTHON) cli_audit.py' || true
	@echo "✓ Snapshot updated. Run 'make audit' or 'make upgrade' to use it." >&2
	@echo "" >&2
	@echo "→ Running system health checks..." >&2
	@$(MAKE) check-path || true
	@$(MAKE) check-python-managers || true
	@$(MAKE) check-node-managers || true

update-debug: ## Collect with verbose debug output (shows network calls)
	@bash -c 'set -o pipefail; CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_TIMINGS=1 $(PYTHON) cli_audit.py' || true

upgrade: scripts-perms ## Run interactive upgrade guide (uses snapshot, no network calls)
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

upgrade-%: scripts-perms ## Upgrade tool (e.g., make upgrade-python)
	./scripts/install_$*.sh update

uninstall-%: scripts-perms ## Uninstall tool (e.g., make uninstall-python)
	./scripts/install_$*.sh uninstall

reconcile-pip-to-uv: scripts-perms ## Migrate user pip packages to UV tools
	@./scripts/reconcile_pip_to_uv.sh

reconcile-pipx-to-uv: scripts-perms ## Migrate pipx tools to UV
	@./scripts/reconcile_pipx_to_uv.sh

reconcile-%: scripts-perms ## Reconcile tool installation (e.g., make reconcile-node)
	./scripts/install_$*.sh reconcile

detect-managers: scripts-perms ## Detect all installed package managers
	./scripts/auto_update.sh detect

upgrade-managed: scripts-perms ## Upgrade all package managers and their packages
	SCOPE=all ./scripts/auto_update.sh update

upgrade-dry-run: scripts-perms ## Preview what would be upgraded without making changes
	SCOPE=all ./scripts/auto_update.sh --dry-run update

upgrade-managed-system-only: scripts-perms ## Upgrade only system package managers (apt, brew, snap, flatpak)
	@bash -c './scripts/auto_update.sh apt && ./scripts/auto_update.sh brew && ./scripts/auto_update.sh snap && ./scripts/auto_update.sh flatpak' || true

upgrade-managed-skip-system: scripts-perms ## Upgrade all package managers except system ones
	./scripts/auto_update.sh --skip-system update

upgrade-managed-system: scripts-perms ## Upgrade only system-scoped packages (requires sudo)
	SCOPE=system ./scripts/auto_update.sh update

upgrade-managed-user: scripts-perms ## Upgrade only user-scoped packages (no sudo)
	SCOPE=user ./scripts/auto_update.sh update

upgrade-project-deps: scripts-perms ## Upgrade project dependencies (with confirmation)
	SCOPE=project ./scripts/auto_update.sh update

upgrade-managed-all: scripts-perms ## Upgrade system + user scopes (skip project)
	SCOPE=all ./scripts/auto_update.sh update

bootstrap: scripts-perms ## Initialize system (install Python if needed, setup environment)
	@echo "→ Bootstrapping ai_cli_preparation..." >&2
	@bash -c ' \
		if ! command -v python3 >/dev/null 2>&1; then \
			echo "⚠️  Python not found. Installing..." >&2; \
			./scripts/install_python.sh || exit 1; \
		fi; \
		py_version=$$(python3 --version 2>&1 | sed "s/Python //"); \
		echo "✓ Python $$py_version available" >&2; \
		$(MAKE) check-path || $(MAKE) fix-path; \
		$(MAKE) update; \
		echo "✓ Bootstrap complete. Run '\''make audit'\'' to see installed tools." >&2'

init: bootstrap ## Alias for bootstrap

upgrade-all: scripts-perms ## Complete system upgrade: update data → upgrade managers → upgrade tools
	@bash scripts/upgrade_all.sh

upgrade-all-dry-run: scripts-perms ## Preview complete system upgrade without making changes
	@DRY_RUN=1 bash scripts/upgrade_all.sh

check-path: scripts-perms ## Check PATH configuration for package managers
	@bash -c "source scripts/lib/path_check.sh && check_all_paths"

fix-path: scripts-perms ## Fix PATH configuration issues automatically
	@bash -c "source scripts/lib/path_check.sh && fix_all_paths"

check-python-managers: ## Check for multiple Python package managers and recommend consolidation
	@bash scripts/check_python_package_managers.sh

check-node-managers: ## Check for multiple Node.js package managers and recommend consolidation
	@bash scripts/check_node_package_managers.sh
