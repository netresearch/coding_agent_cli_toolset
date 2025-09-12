PYTHON ?= python3

.PHONY: audit lint fmt help

help:
	@echo "Available targets:"
	@echo "  audit  - run the CLI audit"
	@echo "  guide  - interactive install/update walkthrough (ordered)"
	@echo "  lint   - run basic lint checks"
	@echo "  fmt    - no-op (placeholder)"
	@echo "  install-core    - install core simple tools"
	@echo "  install-python  - install Python toolchain"
	@echo "  install-node    - install Node toolchain"
	@echo "  install-go      - install Go toolchain"
	@echo "  install-aws     - install AWS CLI"
	@echo "  install-kubectl - install kubectl"
	@echo "  install-terraform - install Terraform"
	@echo "  install-ansible - install Ansible"
	@echo "  install-docker  - install Docker CLI"
	@echo "  install-brew    - install Homebrew (Linuxbrew)"
	@echo "  install-rust    - install Rust (rustup/cargo)"

audit:
	@bash -c 'set -o pipefail; CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Audit a single tool (table)
audit-%: scripts-perms
	@bash -c 'set -o pipefail; CLI_AUDIT_LINKS=1 CLI_AUDIT_EMOJI=1 $(PYTHON) cli_audit.py --only $* | \
	$(PYTHON) smart_column.py -s "|" -t --right 3,5 --header' || true

# Audit a single tool (JSON)
audit-json-%: scripts-perms
	@bash -c 'set -o pipefail; CLI_AUDIT_JSON=1 $(PYTHON) cli_audit.py --only $*' || true

guide: scripts-perms
	@bash scripts/guide.sh

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
