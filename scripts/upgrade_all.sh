#!/usr/bin/env bash
set -euo pipefail

# upgrade_all.sh - Orchestrated full system upgrade
# 5-stage workflow: refresh data → upgrade managers → upgrade runtimes → upgrade user managers → upgrade tools

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DIR/.." && pwd)"

DRY_RUN="${DRY_RUN:-0}"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/upgrade-$(date +%Y%m%d-%H%M%S).log"

# Stats tracking
TOTAL_UPGRADED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
START_TIME=$(date +%s)

# Colors (if terminal supports it)
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors)" -ge 8 ]; then
	BOLD=$(tput bold)
	GREEN=$(tput setaf 2)
	YELLOW=$(tput setaf 3)
	RED=$(tput setaf 1)
	BLUE=$(tput setaf 4)
	RESET=$(tput sgr0)
else
	BOLD=""
	GREEN=""
	YELLOW=""
	RED=""
	BLUE=""
	RESET=""
fi

log() {
	local msg="$*"
	echo "$msg" | tee -a "$LOG_FILE"
}

log_stage() {
	local stage="$1"
	local total="$2"
	local desc="$3"
	echo "" | tee -a "$LOG_FILE"
	echo "${BOLD}${BLUE}[$stage/$total] $desc${RESET}" | tee -a "$LOG_FILE"
}

log_success() {
	echo "  ${GREEN}✓${RESET} $*" | tee -a "$LOG_FILE"
	TOTAL_UPGRADED=$((TOTAL_UPGRADED + 1))
}

log_skip() {
	echo "  ${YELLOW}⏭${RESET} $*" | tee -a "$LOG_FILE"
	TOTAL_SKIPPED=$((TOTAL_SKIPPED + 1))
}

log_fail() {
	echo "  ${RED}❌${RESET} $*" | tee -a "$LOG_FILE"
	TOTAL_FAILED=$((TOTAL_FAILED + 1))
}

log_info() {
	echo "  ${BLUE}→${RESET} $*" | tee -a "$LOG_FILE"
}

run_cmd() {
	local desc="$1"
	shift

	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: $desc"
		log_info "  Command: $*"
		return 0
	fi

	if "$@" >> "$LOG_FILE" 2>&1; then
		log_success "$desc"
		return 0
	else
		log_fail "$desc (see $LOG_FILE for details)"
		return 1
	fi
}

# ============================================================================
# Stage 1: Refresh Version Data
# ============================================================================
stage_1_refresh() {
	log_stage 1 5 "Refreshing version data..."

	cd "$PROJECT_ROOT"

	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: make update"
		log_skip "Version data refresh (dry-run)"
	else
		local start=$(date +%s)
		log_info "Fetching latest versions (this may take a minute)..."

		# Run make update with progress indication
		(
			make update >> "$LOG_FILE" 2>&1 &
			local pid=$!
			local spinner='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
			local i=0
			while kill -0 $pid 2>/dev/null; do
				printf "\r  ${BLUE}→${RESET} Fetching... %s" "${spinner:i++%${#spinner}:1}"
				sleep 0.1
			done
			wait $pid
			local exit_code=$?
			printf "\r"
			return $exit_code
		)

		if [ $? -eq 0 ]; then
			local end=$(date +%s)
			local duration=$((end - start))
			log_success "Fetched latest version data (${duration}s)"
		else
			log_fail "Failed to refresh version data"
			return 1
		fi
	fi
}

# ============================================================================
# Stage 2: Upgrade Package Managers
# ============================================================================
stage_2_managers() {
	log_stage 2 5 "Upgrading package managers..."

	cd "$PROJECT_ROOT"

	# System package managers
	if command -v apt-get >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: apt-get update && apt-get upgrade"
		else
			run_cmd "apt (system)" sudo apt-get update >/dev/null 2>&1 && sudo apt-get upgrade -y >/dev/null 2>&1 || log_skip "apt (not available or failed)"
		fi
	else
		log_skip "apt (not installed)"
	fi

	if command -v brew >/dev/null 2>&1; then
		run_cmd "brew" brew update >/dev/null 2>&1 && brew upgrade >/dev/null 2>&1 || log_skip "brew (failed)"
	else
		log_skip "brew (not installed)"
	fi

	if command -v snap >/dev/null 2>&1; then
		run_cmd "snap" sudo snap refresh || log_skip "snap (failed)"
	else
		log_skip "snap (not installed)"
	fi

	if command -v flatpak >/dev/null 2>&1; then
		run_cmd "flatpak" flatpak update -y || log_skip "flatpak (failed)"
	else
		log_skip "flatpak (not installed)"
	fi

	# Language-specific package managers
	if command -v pip3 >/dev/null 2>&1; then
		run_cmd "pip" python3 -m pip install --user --upgrade pip || log_skip "pip (failed)"
	else
		log_skip "pip (not installed)"
	fi

	if command -v uv >/dev/null 2>&1; then
		run_cmd "uv" uv self update || log_skip "uv (failed)"
	else
		log_skip "uv (not installed)"
	fi

	if command -v pipx >/dev/null 2>&1; then
		run_cmd "pipx" pip3 install --user --upgrade pipx || log_skip "pipx (failed)"
	else
		log_skip "pipx (not installed)"
	fi

	if command -v npm >/dev/null 2>&1; then
		run_cmd "npm" npm install -g npm@latest || log_skip "npm (failed)"
	else
		log_skip "npm (not installed)"
	fi

	if command -v pnpm >/dev/null 2>&1; then
		if command -v corepack >/dev/null 2>&1; then
			run_cmd "pnpm" corepack prepare pnpm@latest --activate || log_skip "pnpm (failed)"
		else
			run_cmd "pnpm" npm install -g pnpm@latest || log_skip "pnpm (failed)"
		fi
	else
		log_skip "pnpm (not installed)"
	fi

	if command -v yarn >/dev/null 2>&1; then
		if command -v corepack >/dev/null 2>&1; then
			run_cmd "yarn" corepack prepare yarn@stable --activate || log_skip "yarn (failed)"
		else
			run_cmd "yarn" npm install -g yarn@latest || log_skip "yarn (failed)"
		fi
	else
		log_skip "yarn (not installed)"
	fi

	if command -v cargo >/dev/null 2>&1 && command -v rustup >/dev/null 2>&1; then
		run_cmd "rustup" rustup update || log_skip "rustup (failed)"
	else
		log_skip "rustup (not installed)"
	fi

	if command -v gem >/dev/null 2>&1; then
		run_cmd "gem" gem update --system || log_skip "gem (failed)"
	else
		log_skip "gem (not installed)"
	fi

	if command -v composer >/dev/null 2>&1; then
		# Check if composer is system-installed (can't self-update)
		if [ "$(which composer)" = "/usr/bin/composer" ] || [ "$(which composer)" = "/usr/local/bin/composer" ]; then
			log_skip "composer (system-managed, use apt/brew to update)"
		else
			run_cmd "composer" composer self-update || log_skip "composer (failed)"
		fi
	else
		log_skip "composer (not installed)"
	fi

	if command -v poetry >/dev/null 2>&1; then
		# Try poetry self update first (Poetry 1.2+)
		if poetry self update --help >/dev/null 2>&1; then
			run_cmd "poetry" poetry self update || log_skip "poetry (failed)"
		# Fallback to uv tool upgrade if poetry is managed by uv
		elif command -v uv >/dev/null 2>&1 && uv tool list 2>/dev/null | grep -q "^poetry"; then
			run_cmd "poetry" uv tool upgrade poetry || log_skip "poetry (failed)"
		# Fallback to pipx upgrade if poetry is managed by pipx
		elif command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "poetry"; then
			run_cmd "poetry" pipx upgrade poetry || log_skip "poetry (failed)"
		else
			log_skip "poetry (no automatic update method)"
		fi
	else
		log_skip "poetry (not installed)"
	fi
}

# ============================================================================
# Stage 3: Upgrade Language Runtimes
# ============================================================================
stage_3_runtimes() {
	log_stage 3 5 "Upgrading language runtimes..."

	cd "$PROJECT_ROOT"

	# Python
	if [ -f "./scripts/install_python.sh" ]; then
		run_cmd "Python runtime" ./scripts/install_python.sh update || log_skip "Python (upgrade failed or not managed)"
	else
		log_skip "Python (install script not found)"
	fi

	# Node.js
	if [ -f "./scripts/install_node.sh" ]; then
		run_cmd "Node.js runtime" ./scripts/install_node.sh update || log_skip "Node.js (upgrade failed or not managed)"
	else
		log_skip "Node.js (install script not found)"
	fi

	# Go
	if [ -f "./scripts/install_go.sh" ]; then
		run_cmd "Go runtime" ./scripts/install_go.sh update || log_skip "Go (upgrade failed or not managed)"
	else
		log_skip "Go (install script not found)"
	fi

	# Ruby
	if [ -f "./scripts/install_ruby.sh" ]; then
		run_cmd "Ruby runtime" ./scripts/install_ruby.sh update || log_skip "Ruby (upgrade failed or not managed)"
	else
		log_skip "Ruby (install script not found)"
	fi

	# Rust
	if [ -f "./scripts/install_rust.sh" ]; then
		run_cmd "Rust runtime" ./scripts/install_rust.sh update || log_skip "Rust (upgrade failed or not managed)"
	else
		log_skip "Rust (install script not found)"
	fi
}

# ============================================================================
# Stage 4: Upgrade Packages Managed by Package Managers
# ============================================================================
stage_4_user_packages() {
	log_stage 4 5 "Upgrading packages managed by package managers..."

	cd "$PROJECT_ROOT"

	# UV tools
	if command -v uv >/dev/null 2>&1; then
		log_info "Upgrading uv tools..."
		if [ "$DRY_RUN" = "0" ]; then
			local tools
			# Filter out binary lines (starting with dash) and keep only tool names
			tools="$(uv tool list 2>/dev/null | grep -v '^-' | awk 'NF > 0 {print $1}' || true)"
			if [ -n "$tools" ]; then
				local count=$(echo "$tools" | wc -l)
				log_info "Found $count uv tools to upgrade"
				while IFS= read -r tool; do
					[ -z "$tool" ] && continue
					run_cmd "uv tool: $tool" uv tool upgrade "$tool" || log_skip "uv tool: $tool (failed)"
				done <<< "$tools"
			else
				log_skip "uv (no tools installed)"
			fi
		else
			log_info "DRY-RUN: uv tool upgrade <all-tools>"
		fi
	else
		log_skip "uv (not installed)"
	fi

	# Pipx packages
	if command -v pipx >/dev/null 2>&1; then
		run_cmd "pipx packages" pipx upgrade-all || log_skip "pipx packages (failed)"
	else
		log_skip "pipx (not installed)"
	fi

	# Cargo install-update
	if command -v cargo >/dev/null 2>&1; then
		if ! command -v cargo-install-update >/dev/null 2>&1; then
			run_cmd "cargo-update tool" cargo install cargo-update || log_skip "cargo-update (install failed)"
		fi

		if command -v cargo-install-update >/dev/null 2>&1; then
			run_cmd "cargo packages" cargo install-update -a || log_skip "cargo packages (failed)"
		fi
	else
		log_skip "cargo (not installed)"
	fi

	# Gem packages
	if command -v gem >/dev/null 2>&1; then
		run_cmd "gem packages" gem update || log_skip "gem packages (failed)"
	else
		log_skip "gem (not installed)"
	fi

	# Composer global packages
	if command -v composer >/dev/null 2>&1; then
		run_cmd "composer packages" composer global update || log_skip "composer packages (failed)"
	else
		log_skip "composer (not installed)"
	fi
}

# ============================================================================
# Stage 5: Upgrade CLI Tools
# ============================================================================
stage_5_tools() {
	log_stage 5 5 "Upgrading CLI tools..."

	cd "$PROJECT_ROOT"

	log_info "Using upgrade-managed for comprehensive package upgrades"

	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: make upgrade-managed-user"
		log_skip "CLI tools upgrade (dry-run)"
	else
		if make upgrade-managed-user >> "$LOG_FILE" 2>&1; then
			log_success "Upgraded user-scoped packages via upgrade-managed"
		else
			log_skip "upgrade-managed (failed or not available)"
		fi
	fi

	log_info "For tool-specific upgrades, run: make upgrade-<tool>"
	log_info "For interactive guide, run: make upgrade"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
	# Create log directory if it doesn't exist
	mkdir -p "$LOG_DIR"

	# Header
	echo "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
	echo "${BOLD}  Full System Upgrade${RESET}"
	echo "${BOLD}═══════════════════════════════════════════════════════════${RESET}"

	if [ "$DRY_RUN" = "1" ]; then
		echo "${YELLOW}DRY-RUN MODE: No changes will be made${RESET}"
	fi

	echo ""
	echo "Log: $LOG_FILE"
	echo ""

	# Execute stages
	stage_1_refresh || true
	stage_2_managers || true
	stage_3_runtimes || true
	stage_4_user_packages || true
	stage_5_tools || true

	# Summary
	local end_time=$(date +%s)
	local total_time=$((end_time - START_TIME))
	local minutes=$((total_time / 60))
	local seconds=$((total_time % 60))

	echo ""
	echo "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
	echo "${BOLD}Upgrade Summary:${RESET}"
	echo "  ${GREEN}✓ Successful: $TOTAL_UPGRADED components${RESET}"
	echo "  ${YELLOW}⏭ Skipped:    $TOTAL_SKIPPED components${RESET}"
	echo "  ${RED}❌ Failed:     $TOTAL_FAILED components${RESET}"
	echo ""
	echo "Time: ${minutes}m ${seconds}s"
	echo "Log: $LOG_FILE"
	echo "${BOLD}═══════════════════════════════════════════════════════════${RESET}"

	# Exit with error if any failures
	if [ "$TOTAL_FAILED" -gt 0 ]; then
		exit 1
	fi
}

main "$@"
