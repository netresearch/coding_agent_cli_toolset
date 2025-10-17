PYTHON ?= python3

# Load defaults in precedence order: .env.default < .env (highest)
-include .env.default
-include .env

# Export all loaded Make variables to environment for subprocesses
export

.PHONY: user-help help audit audit-offline audit-% audit-offline-% update upgrade guide \
	test test-unit test-integration test-coverage test-watch test-failed \
	lint lint-code lint-types lint-security format format-check \
	install install-dev install-core install-python install-node install-go \
	install-aws install-kubectl install-terraform install-ansible install-docker \
	install-brew install-rust upgrade-% uninstall-% reconcile-% \
	build build-dist build-wheel check-dist publish publish-test publish-prod \
	clean clean-build clean-test clean-pyc clean-all \
	scripts-perms audit-auto detect-managers upgrade-managed upgrade-dry-run \
	upgrade-managed-system upgrade-managed-user upgrade-project-deps upgrade-managed-all \
	upgrade-managed-system-only upgrade-managed-skip-system bootstrap init \
	upgrade-all upgrade-all-dry-run check-path fix-path

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
# MODULAR INCLUDES
# ============================================================================

include Makefile.d/user.mk
include Makefile.d/dev.mk
include Makefile.d/maint.mk

# Shortcuts must be last to act as catch-all
include Makefile.d/shortcuts.mk
