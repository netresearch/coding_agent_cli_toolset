PYTHON ?= python3

# Load defaults in precedence order: .env.default < .env (highest)
-include .env.default
-include .env

.PHONY: audit audit-offline audit-only-% audit-offline-% lint fmt help update audit-auto upgrade

help:
	@echo "Available targets:"
	@echo "  audit        - render audit from snapshot (no network)"
	@echo "  audit-auto   - update snapshot if stale/missing, then render"
	@echo "  update       - collect-only (fetch + write snapshot), verbose"
	@echo "  upgrade      - run the interactive upgrade guide (renamed)"
	@echo "  guide        - alias for upgrade (deprecated)"
	@echo "  lint         - run basic lint checks"
	@echo "  fmt          - no-op (placeholder)"
	@echo "  install-*    - install various toolchains"

# Render-only from snapshot
audit:
	@bash -c 'set -o pipefail; CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Offline, grouped, with hints (fast local scan)
audit-offline:
	@bash -c 'set -o pipefail; CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Audit a single tool (table)
audit-%: scripts-perms
	@bash -c 'set -o pipefail; CLI_AUDIT_RENDER=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py --only $* | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Offline subset (respects alias presets like python-core, infra-core, etc.)
audit-offline-%: scripts-perms
	@bash -c 'set -o pipefail; CLI_AUDIT_OFFLINE=1 CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py --only $* | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Collect-only: fetch and write snapshot (verbose)
update:
	@bash -c 'set -o pipefail; CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py' || true

# Audit-auto: attempt collect when snapshot missing; then render
SNAP_FILE?=$(shell python3 -c "import os;print(os.environ.get('CLI_AUDIT_SNAPSHOT_FILE','tools_snapshot.json'))")

audit-auto:
	@if [ ! -f "$(SNAP_FILE)" ]; then \
		echo "# snapshot missing: $(SNAP_FILE); running update..."; \
		CLI_AUDIT_COLLECT=1 CLI_AUDIT_DEBUG=1 CLI_AUDIT_PROGRESS=1 $(PYTHON) cli_audit.py || true; \
	fi; \
	CLI_AUDIT_RENDER=1 CLI_AUDIT_GROUP=0 CLI_AUDIT_HINTS=1 CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header || true

# Rename guide -> upgrade
upgrade: scripts-perms
	@bash scripts/guide.sh

guide: upgrade

lint:
	@command -v pyflakes >/dev/null 2>&1 && pyflakes cli_audit.py || echo "pyflakes not installed; skipping"

fmt:
	@echo "Nothing to format"

scripts-perms:
	chmod +x scripts/*.sh || true
	chmod +x scripts/lib/*.sh || true

install-core: scripts-perms
	./scripts/install_core.sh

install-python: scripts-perms
	./scripts/install_python.sh

install-node: scripts-perms
	./scripts/install_node.sh

install-go: scripts-perms
	./scripts/install_go.sh

install-aws: scripts-perms
	./scripts/install_aws.sh

install-kubectl: scripts-perms
	./scripts/install_kubectl.sh

install-terraform: scripts-perms
	./scripts/install_terraform.sh

install-ansible: scripts-perms
	./scripts/install_ansible.sh

install-docker: scripts-perms
	./scripts/install_docker.sh

install-brew: scripts-perms
	./scripts/install_brew.sh

install-rust: scripts-perms
	./scripts/install_rust.sh

# Generic action targets (install/update/uninstall/reconcile)
update-%: scripts-perms
	./scripts/install_$*.sh update

uninstall-%: scripts-perms
	./scripts/install_$*.sh uninstall

reconcile-%: scripts-perms
	./scripts/install_$*.sh reconcile
