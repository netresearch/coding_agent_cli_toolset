#!/usr/bin/env bash
set -euo pipefail

# upgrade_all.sh - Orchestrated full system upgrade
# 6-stage workflow: refresh data → upgrade managers → upgrade runtimes → upgrade user packages → upgrade tools → health checks

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DIR/.." && pwd)"

# Source common helpers
. "$DIR/lib/common.sh"

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

get_version() {
	local version_cmd="$1"
	local version
	version="$(eval "$version_cmd" 2>/dev/null || true)"
	printf '%s' "${version:-unknown}"
}

log_success_with_info() {
	local name="$1"
	local binary="$2"
	local version_cmd="$3"
	local before_version="$4"
	local after_version
	after_version="$(get_version "$version_cmd")"
	log_success_with_versions "$name" "$binary" "$before_version" "$after_version"
}

log_success_with_versions() {
	local name="$1"
	local binary="$2"
	local before_version="$3"
	local after_version="$4"
	local location
	location="$(command -v "$binary" 2>/dev/null || echo "unknown")"
	local version_change
	if [ "$before_version" = "unknown" ] || [ "$after_version" = "unknown" ]; then
		version_change="version unavailable: $before_version → $after_version"
	elif [ "$before_version" = "$after_version" ]; then
		version_change="$after_version unchanged"
	else
		version_change="$before_version → $after_version"
	fi
	echo "  ${GREEN}✓${RESET} $name ($version_change at $location)" | tee -a "$LOG_FILE"
	TOTAL_UPGRADED=$((TOTAL_UPGRADED + 1))
}

get_uv_tool_version() {
	local package="$1"
	local version
	version="$(uv tool list 2>/dev/null | awk -v package="$package" '
		$1 == package {
			version = $2
			sub(/^v/, "", version)
			print version
			exit
		}
	')"
	printf '%s' "${version:-unknown}"
}

get_uv_tool_binary() {
	local package="$1"
	uv tool list 2>/dev/null | awk -v package="$package" '
		$1 == package { found = 1; next }
		found && $1 == "-" { print $2; exit }
		found { exit }
	'
}

upgrade_uv_tools() {
	local tools
	tools="$(uv tool list 2>/dev/null | awk '$1 != "-" && NF >= 2 { print $1 }' || true)"
	if [ -z "$tools" ]; then
		log_skip "uv (no tools installed)"
		return 0
	fi

	local count
	count="$(printf '%s\n' "$tools" | wc -l)"
	log_info "Found $count uv tools to upgrade"

	local tool before_version after_version binary
	while IFS= read -r tool; do
		[ -z "$tool" ] && continue
		before_version="$(get_uv_tool_version "$tool")"
		binary="$(get_uv_tool_binary "$tool")"
		if uv tool upgrade "$tool" >> "$LOG_FILE" 2>&1; then
			after_version="$(get_uv_tool_version "$tool")"
			log_success_with_versions "$tool" "${binary:-$tool}" "$before_version" "$after_version"
		else
			log_skip "uv tool: $tool (failed)"
		fi
	done <<< "$tools"
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

log_reconcile() {
	echo "  ${YELLOW}⚙${RESET} $*" | tee -a "$LOG_FILE"
	TOTAL_SKIPPED=$((TOTAL_SKIPPED + 1))
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

	# Check if version data is fresh (updated within last hour)
	local versions_file="$PROJECT_ROOT/upstream_versions.json"
	local cache_ttl=3600  # 1 hour in seconds

	if [ -f "$versions_file" ]; then
		local file_age=$(($(date +%s) - $(stat -c %Y "$versions_file" 2>/dev/null || stat -f %m "$versions_file" 2>/dev/null || echo 0)))
		if [ "$file_age" -lt "$cache_ttl" ]; then
			local age_minutes=$((file_age / 60))
			log_skip "Version data is fresh (updated ${age_minutes}m ago, cache: 60m)"
			return 0
		fi
	fi

	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: make update"
		log_skip "Version data refresh (dry-run)"
	else
		local start
		start="$(date +%s)"
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
			local end
			end="$(date +%s)"
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
			local before_version
			before_version="$(get_version "apt-get --version | head -1 | awk '{print \$2}'")"
			# The caller owns LOG_FILE; only apt-get itself needs sudo.
			# shellcheck disable=SC2024
			if {
				sudo apt-get update &&
					sudo apt-get upgrade -y
			} >> "$LOG_FILE" 2>&1; then
				log_success_with_info "apt (system)" "apt-get" "apt-get --version | head -1 | awk '{print \$2}'" "$before_version"
			else
				log_skip "apt (not available or failed)"
			fi
		fi
	else
		log_skip "apt (not installed)"
	fi

	if command -v brew >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: brew update && brew upgrade"
		else
			local before_version
			before_version="$(get_version "brew --version | head -1 | awk '{print \$2}'")"
			if brew update >> "$LOG_FILE" 2>&1 &&
				brew upgrade >> "$LOG_FILE" 2>&1; then
				log_success_with_info "brew" "brew" "brew --version | head -1 | awk '{print \$2}'" "$before_version"
			else
				log_skip "brew (failed)"
			fi
		fi
	else
		log_skip "brew (not installed)"
	fi

	if command -v snap >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: snap refresh"
		else
			local before_version
			before_version="$(get_version "snap version | awk '/^snap / {print \$2}'")"
			# The caller owns LOG_FILE; only snap itself needs sudo.
			# shellcheck disable=SC2024
			if sudo snap refresh >> "$LOG_FILE" 2>&1; then
				log_success_with_info "snap" "snap" "snap version | awk '/^snap / {print \$2}'" "$before_version"
			else
				log_skip "snap (failed)"
			fi
		fi
	else
		log_skip "snap (not installed)"
	fi

	if command -v flatpak >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: flatpak update -y"
		else
			local before_version
			before_version="$(get_version "flatpak --version | awk '{print \$2}'")"
			if flatpak update -y >> "$LOG_FILE" 2>&1; then
				log_success_with_info "flatpak" "flatpak" "flatpak --version | awk '{print \$2}'" "$before_version"
			else
				log_skip "flatpak (failed)"
			fi
		fi
	else
		log_skip "flatpak (not installed)"
	fi

	# Language-specific package managers
	if command -v python3 >/dev/null 2>&1 &&
		python3 -m pip --version >/dev/null 2>&1; then
		# Skip pip if uv is managing Python packages, suggest migration
		if command -v uv >/dev/null 2>&1; then
			# Check if there are user-installed pip packages to migrate
			local user_packages
			user_packages="$(python3 -m pip list --user --format=freeze 2>/dev/null | grep -v "^#" | wc -l)"
			if [ "$user_packages" -gt 0 ]; then
				log_reconcile "pip ($user_packages user packages, run: make reconcile-pip-to-uv to migrate)"
			else
				log_skip "pip (uv is managing Python packages)"
			fi
		elif [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: pip upgrade"
		else
			local before_version
			before_version="$(get_version "python3 -m pip --version | awk '{print \$2}'")"
			local upgrade_success=0
			# Check if in virtualenv - skip --user flag if so
			if [ -n "${VIRTUAL_ENV:-}" ]; then
				python3 -m pip install --upgrade pip >> "$LOG_FILE" 2>&1 && upgrade_success=1
			else
				python3 -m pip install --user --upgrade pip >> "$LOG_FILE" 2>&1 && upgrade_success=1
			fi

			if [ "$upgrade_success" = "1" ]; then
				log_success_with_info "pip (python3 -m pip)" "python3" "python3 -m pip --version | awk '{print \$2}'" "$before_version"
			else
				log_fail "pip (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "pip (python3 module not installed)"
	fi

	if command -v uv >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: uv self update"
		else
			local before_version
			before_version="$(get_version "uv --version | awk '{print \$2}'")"
			if uv self update >> "$LOG_FILE" 2>&1; then
				log_success_with_info "uv" "uv" "uv --version | awk '{print \$2}'" "$before_version"
			else
				log_fail "uv (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "uv (not installed)"
	fi

	if command -v pipx >/dev/null 2>&1; then
		# Skip pipx if uv is managing Python tools, suggest migration
		if command -v uv >/dev/null 2>&1; then
			# Check if there are pipx tools to migrate
			local pipx_tools
			pipx_tools="$(pipx list --short 2>/dev/null | wc -l)"
			if [ "$pipx_tools" -gt 0 ]; then
				log_reconcile "pipx ($pipx_tools tools installed, run: make reconcile-pipx-to-uv to migrate)"
			else
				log_skip "pipx (uv is managing Python tools)"
			fi
		elif [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: pip3 install --upgrade pipx"
		else
			local before_version
			before_version="$(get_version "pipx --version")"
			# Check if in virtualenv - skip --user flag if so
			local upgrade_success=0
			if [ -n "${VIRTUAL_ENV:-}" ]; then
				pip3 install --upgrade pipx >> "$LOG_FILE" 2>&1 && upgrade_success=1
			else
				pip3 install --user --upgrade pipx >> "$LOG_FILE" 2>&1 && upgrade_success=1
			fi

			if [ "$upgrade_success" = "1" ]; then
				log_success_with_info "pipx" "pipx" "pipx --version" "$before_version"
			else
				log_fail "pipx (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "pipx (not installed)"
	fi

	if command -v npm >/dev/null 2>&1; then
		local npm_path
		npm_path="$(command -v npm)"
		# Check if npm is system-managed (not nvm)
		if [[ "$npm_path" == /usr/bin/npm ]] || [[ "$npm_path" == /usr/local/bin/npm ]]; then
			log_reconcile "npm (system-managed at $npm_path, run: ./scripts/install_node.sh reconcile)"
		else
			if [ "$DRY_RUN" = "1" ]; then
				log_info "DRY-RUN: npm install -g npm@latest"
			else
				local before_version
				before_version="$(get_version "npm --version")"
				if npm install -g npm@latest >> "$LOG_FILE" 2>&1; then
					log_success_with_info "npm" "npm" "npm --version" "$before_version"
				else
					log_fail "npm (see $LOG_FILE for details)"
				fi
			fi
		fi
	else
		log_skip "npm (not installed)"
	fi

	if command -v pnpm >/dev/null 2>&1; then
		local pnpm_path
		pnpm_path="$(command -v pnpm)"
		# Check if pnpm is system-managed (not nvm/corepack)
		if [[ "$pnpm_path" == /usr/bin/pnpm ]] || [[ "$pnpm_path" == /usr/local/bin/pnpm ]]; then
			log_reconcile "pnpm (system-managed at $pnpm_path, run: ./scripts/install_node.sh reconcile)"
		else
			if [ "$DRY_RUN" = "1" ]; then
				log_info "DRY-RUN: pnpm upgrade"
			else
				local before_version
				before_version="$(get_version "pnpm --version")"
				local upgrade_success=0
				if command -v corepack >/dev/null 2>&1; then
					corepack prepare pnpm@latest --activate >> "$LOG_FILE" 2>&1 && upgrade_success=1
				else
					npm install -g pnpm@latest >> "$LOG_FILE" 2>&1 && upgrade_success=1
				fi

				if [ "$upgrade_success" = "1" ]; then
					log_success_with_info "pnpm" "pnpm" "pnpm --version" "$before_version"
				else
					log_fail "pnpm (see $LOG_FILE for details)"
				fi
			fi
		fi
	else
		log_skip "pnpm (not installed)"
	fi

	if command -v yarn >/dev/null 2>&1; then
		local yarn_path
		yarn_path="$(command -v yarn)"
		# Check if yarn is system-managed (not nvm/corepack)
		if [[ "$yarn_path" == /usr/bin/yarn ]] || [[ "$yarn_path" == /usr/local/bin/yarn ]]; then
			log_reconcile "yarn (system-managed at $yarn_path, run: ./scripts/install_node.sh reconcile)"
		else
			if [ "$DRY_RUN" = "1" ]; then
				log_info "DRY-RUN: yarn upgrade"
			else
				local before_version
				before_version="$(get_version "yarn --version")"
				local upgrade_success=0
				if command -v corepack >/dev/null 2>&1; then
					corepack prepare yarn@stable --activate >> "$LOG_FILE" 2>&1 && upgrade_success=1
				else
					npm install -g yarn@latest >> "$LOG_FILE" 2>&1 && upgrade_success=1
				fi

				if [ "$upgrade_success" = "1" ]; then
					log_success_with_info "yarn" "yarn" "yarn --version" "$before_version"
				else
					log_fail "yarn (see $LOG_FILE for details)"
				fi
			fi
		fi
	else
		log_skip "yarn (not installed)"
	fi

	if command -v cargo >/dev/null 2>&1 && command -v rustup >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: rustup update"
		else
			local before_version
			before_version="$(get_version "rustup --version | head -1 | awk '{print \$2}'")"
			if rustup update >> "$LOG_FILE" 2>&1; then
				log_success_with_info "rustup" "rustup" "rustup --version | head -1 | awk '{print \$2}'" "$before_version"
			else
				log_fail "rustup (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "rustup (not installed)"
	fi

	if command -v gem >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: gem update --system"
		else
			local before_version
			before_version="$(get_version "gem --version")"
			if gem update --system >> "$LOG_FILE" 2>&1; then
				log_success_with_info "gem" "gem" "gem --version" "$before_version"
			else
				log_fail "gem (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "gem (not installed)"
	fi

	if command -v composer >/dev/null 2>&1; then
		# Check if composer is system-installed (can't self-update)
		if [ "$(which composer)" = "/usr/bin/composer" ] || [ "$(which composer)" = "/usr/local/bin/composer" ]; then
			log_skip "composer (system-managed, use apt/brew to update)"
		elif [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: composer self-update"
		else
			local before_version
			before_version="$(get_version "composer --version | head -1 | awk '{print \$3}'")"
			if composer self-update >> "$LOG_FILE" 2>&1; then
				log_success_with_info "composer" "composer" "composer --version | head -1 | awk '{print \$3}'" "$before_version"
			else
				log_fail "composer (see $LOG_FILE for details)"
			fi
		fi
	else
		log_skip "composer (not installed)"
	fi

	if command -v poetry >/dev/null 2>&1; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: poetry upgrade"
		else
			local before_version
			before_version="$(get_version "poetry --version | awk '{print \$3}'")"
			local upgrade_success=0
			# Try poetry self update first (Poetry 1.2+)
			if poetry self update --help >/dev/null 2>&1; then
				poetry self update >> "$LOG_FILE" 2>&1 && upgrade_success=1
			# Fallback to uv tool upgrade if poetry is managed by uv
			elif command -v uv >/dev/null 2>&1 && uv tool list 2>/dev/null | grep -q "^poetry"; then
				uv tool upgrade poetry >> "$LOG_FILE" 2>&1 && upgrade_success=1
			# Fallback to pipx upgrade if poetry is managed by pipx
			elif command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "poetry"; then
				pipx upgrade poetry >> "$LOG_FILE" 2>&1 && upgrade_success=1
			else
				log_skip "poetry (no automatic update method)"
				upgrade_success=-1
			fi

			if [ "$upgrade_success" = "1" ]; then
				log_success_with_info "poetry" "poetry" "poetry --version | awk '{print \$3}'" "$before_version"
			elif [ "$upgrade_success" = "0" ]; then
				log_fail "poetry (see $LOG_FILE for details)"
			fi
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
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: ./scripts/install_python.sh update"
		else
			local before_version
			before_version="$(get_version "python3 --version | awk '{print \$2}'")"
			if ./scripts/install_python.sh update >> "$LOG_FILE" 2>&1; then
				if command -v python3 >/dev/null 2>&1; then
					log_success_with_info "Python" "python3" "python3 --version | awk '{print \$2}'" "$before_version"
				else
					log_success "Python runtime"
				fi
			else
				log_skip "Python (upgrade failed or not managed)"
			fi
		fi
	else
		log_skip "Python (install script not found)"
	fi

	# Node.js
	if [ -f "./scripts/install_node.sh" ]; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: ./scripts/install_node.sh update"
		else
			local before_version
			before_version="$(get_version "node --version | sed 's/^v//'")"
			if ./scripts/install_node.sh update >> "$LOG_FILE" 2>&1; then
				if command -v node >/dev/null 2>&1; then
					log_success_with_info "Node.js" "node" "node --version | sed 's/^v//'" "$before_version"
				else
					log_success "Node.js runtime"
				fi
			else
				log_skip "Node.js (upgrade failed or not managed)"
			fi
		fi
	else
		log_skip "Node.js (install script not found)"
	fi

	# Go
	if [ -f "./scripts/install_go.sh" ]; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: ./scripts/install_go.sh update"
		else
			local before_version
			before_version="$(get_version "go version | awk '{print \$3}' | sed 's/^go//'")"
			if ./scripts/install_go.sh update >> "$LOG_FILE" 2>&1; then
				if command -v go >/dev/null 2>&1; then
					log_success_with_info "Go" "go" "go version | awk '{print \$3}' | sed 's/^go//'" "$before_version"
				else
					log_success "Go runtime"
				fi
			else
				log_skip "Go (upgrade failed or not managed)"
			fi
		fi
	else
		log_skip "Go (install script not found)"
	fi

	# Ruby
	if [ -f "./scripts/install_ruby.sh" ]; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: ./scripts/install_ruby.sh update"
		else
			local before_version
			before_version="$(get_version "ruby --version | awk '{print \$2}'")"
			if ./scripts/install_ruby.sh update >> "$LOG_FILE" 2>&1; then
				if command -v ruby >/dev/null 2>&1; then
					log_success_with_info "Ruby" "ruby" "ruby --version | awk '{print \$2}'" "$before_version"
				else
					log_success "Ruby runtime"
				fi
			else
				log_skip "Ruby (upgrade failed or not managed)"
			fi
		fi
	else
		log_skip "Ruby (install script not found)"
	fi

	# Rust
	if [ -f "./scripts/install_rust.sh" ]; then
		if [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: ./scripts/install_rust.sh update"
		else
			local before_version
			before_version="$(get_version "rustc --version | awk '{print \$2}'")"
			if ./scripts/install_rust.sh update >> "$LOG_FILE" 2>&1; then
				if command -v rustc >/dev/null 2>&1; then
					log_success_with_info "Rust" "rustc" "rustc --version | awk '{print \$2}'" "$before_version"
				else
					log_success "Rust runtime"
				fi
			else
				log_skip "Rust (upgrade failed or not managed)"
			fi
		fi
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
			upgrade_uv_tools
		else
			log_info "DRY-RUN: uv tool upgrade <all-tools>"
		fi
	else
		log_skip "uv (not installed)"
	fi

	# Pipx packages
	if command -v pipx >/dev/null 2>&1; then
		# Skip pipx packages if uv is managing Python tools
		if command -v uv >/dev/null 2>&1; then
			local pipx_tools
			pipx_tools="$(pipx list --short 2>/dev/null | wc -l)"
			if [ "$pipx_tools" -gt 0 ]; then
				log_reconcile "pipx packages ($pipx_tools tools, run: make reconcile-pipx-to-uv to migrate)"
			else
				log_skip "pipx packages (uv tools handle this)"
			fi
		elif [ "$DRY_RUN" = "1" ]; then
			log_info "DRY-RUN: pipx upgrade-all"
		else
			local temp_log
			temp_log="$(mktemp)"
			if pipx upgrade-all >> "$LOG_FILE" 2>&1; then
				log_success "pipx packages"
			else
				# Check if only failure was missing metadata (known issue)
				if grep -q "missing internal pipx metadata" "$LOG_FILE" 2>/dev/null; then
					local broken_pkg
					broken_pkg="$(grep -oP "Not upgrading \K\w+" "$LOG_FILE" 2>/dev/null | tail -1)"
					log_reconcile "pipx packages (partial: $broken_pkg has missing metadata, run: pipx uninstall $broken_pkg && pipx install $broken_pkg)"
				else
					log_fail "pipx packages (see $LOG_FILE for details)"
				fi
			fi
			rm -f "$temp_log"
		fi
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
	log_stage 5 6 "Upgrading CLI tools..."

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
# Stage 6: Package Manager Health Checks
# ============================================================================
stage_6_health_checks() {
	log_stage 6 6 "Running package manager health checks..."

	cd "$PROJECT_ROOT"

	# Python package manager health check
	log_info "Checking Python package managers..."
	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: make check-python-managers"
	else
		if make check-python-managers >> "$LOG_FILE" 2>&1; then
			log_success "Python package managers (no conflicts)"
		else
			log_reconcile "Python package managers (conflicts detected, see log for guidance)"
		fi
	fi

	# Node.js package manager health check
	log_info "Checking Node.js package managers..."
	if [ "$DRY_RUN" = "1" ]; then
		log_info "DRY-RUN: make check-node-managers"
	else
		if make check-node-managers >> "$LOG_FILE" 2>&1; then
			log_success "Node.js package managers (no conflicts)"
		else
			log_reconcile "Node.js package managers (conflicts detected, see log for guidance)"
		fi
	fi
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
	stage_6_health_checks || true

	# Summary
	local end_time
	end_time="$(date +%s)"
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
