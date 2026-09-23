#!/usr/bin/env bash
# check_environment.sh - Audit a development environment: PATH, duplicate
# installations, package managers, and the tools a project needs.
#
# Usage: check_environment.sh [audit|path|duplicates|project|managers|update-check] [project_dir]
#
# Needs only bash and jq -- no Python environment -- so it runs from a fresh
# checkout or plugin install.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALOG_DIR="${CLI_AUDIT_CATALOG_DIR:-$DIR/../catalog}"
# shellcheck source=lib/capability.sh
. "$DIR/lib/capability.sh"

ACTION="${1:-audit}"
PROJECT_DIR="${2:-.}"

if [ -t 1 ]; then
    RED=$'\033[0;31m' GREEN=$'\033[0;32m' YELLOW=$'\033[0;33m' BLUE=$'\033[0;34m' NC=$'\033[0m'
else
    RED="" GREEN="" YELLOW="" BLUE="" NC=""
fi

log_ok() { printf '%s✓%s %s\n' "$GREEN" "$NC" "$*"; }
log_warn() { printf '%s⚠%s %s\n' "$YELLOW" "$NC" "$*"; }
log_error() { printf '%s✗%s %s\n' "$RED" "$NC" "$*"; }
log_info() { printf '%s→%s %s\n' "$BLUE" "$NC" "$*"; }

# first_line CMD... -> first output line of CMD, stdin detached. The output is
# captured whole before it is cut: `cmd | head -1` lets SIGPIPE, under
# pipefail, turn a working command into a failure.
first_line() {
    local out
    out="$("$@" </dev/null 2>&1)" || true
    printf '%s' "${out%%$'\n'*}"
}

# binary_for TOOL -> the command a catalog tool provides (rust -> rustc,
# ansible-core -> ansible); the tool name itself when the catalog has no entry.
binary_for() {
    local tool="$1" file="$CATALOG_DIR/$1.json" bin=""
    if [ -f "$file" ] && command -v jq >/dev/null 2>&1; then
        bin="$(jq -r '.binary_name // empty' "$file" 2>/dev/null || true)"
    fi
    printf '%s' "${bin:-$tool}"
}

# debian_alias NAME ALIAS -> ALIAS when only ALIAS is on PATH, else NAME
debian_alias() {
    if ! command -v "$1" >/dev/null 2>&1 && command -v "$2" >/dev/null 2>&1; then
        printf '%s' "$2"
    else
        printf '%s' "$1"
    fi
}

# check_tool TOOL [BINARY]
check_tool() {
    local tool="$1"
    local binary="${2:-$(binary_for "$1")}"
    if command -v "$binary" >/dev/null 2>&1; then
        log_ok "$tool: $(first_line "$binary" --version)"
        return 0
    fi
    log_error "$tool: NOT INSTALLED"
    return 1
}

check_path() {
    log_info "Checking PATH configuration..."
    local issues=0 p node_path
    for p in "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.rbenv/bin" "$HOME/go/bin"; do
        if [ -d "$p" ] && [[ ":$PATH:" != *":$p:"* ]]; then
            log_warn "$p exists but is not in PATH"
            issues=$((issues + 1))
        fi
    done
    if node_path="$(command -v node 2>/dev/null)" && [[ "$node_path" == /usr/* ]] && [ -d "$HOME/.nvm" ]; then
        log_warn "System node ($node_path) may shadow nvm-managed node"
        issues=$((issues + 1))
    fi
    if [ "$issues" -eq 0 ]; then
        log_ok "PATH configuration looks good"
    else
        log_warn "$issues PATH issue(s) found"
    fi
    return "$issues"
}

check_duplicates() {
    log_info "Checking for duplicate installations..."
    local issues=0 tool found
    for tool in node python3 ruby cargo; do
        # detect_all_installations (lib/capability.sh) skips virtualenvs and
        # counts a file once however many PATH entries reach it.
        found="$(detect_all_installations "$tool" "$tool")"
        if [ -n "$found" ] && [ "$(wc -l <<<"$found")" -gt 1 ]; then
            log_warn "$tool has $(wc -l <<<"$found") installations:"
            sed 's/^/    /' <<<"$found"
            issues=$((issues + 1))
        fi
    done
    if [ "$issues" -eq 0 ]; then
        log_ok "No duplicate installations detected"
    fi
    return "$issues"
}

check_project() {
    local project_dir="$1" required tool missing=0
    log_info "Checking project requirements in $project_dir..."
    "$DIR/detect_project_type.sh" text "$project_dir"
    echo ""
    required="$("$DIR/detect_project_type.sh" json "$project_dir" | jq -r '.required_tools[]')"
    while IFS= read -r tool; do
        [ -n "$tool" ] || continue
        check_tool "$tool" || missing=$((missing + 1))
    done <<<"$required"
    if [ "$missing" -gt 0 ]; then
        log_warn "$missing required tool(s) missing -- install with scripts/install_tool.sh <tool>"
    else
        log_ok "All required tools installed"
    fi
}

check_package_managers() {
    log_info "Checking package managers..."
    local entry name binary version found=0
    for entry in apt:apt-get brew:brew cargo:cargo npm:npm pnpm:pnpm yarn:yarn pip:pip3 uv:uv pipx:pipx gem:gem go:go; do
        name="${entry%%:*}"
        binary="${entry##*:}"
        if command -v "$binary" >/dev/null 2>&1; then
            if [ "$binary" = go ]; then
                version="$(first_line go version)" # go has no --version flag
            else
                version="$(first_line "$binary" --version)"
            fi
            printf '  %s●%s %s: %s\n' "$GREEN" "$NC" "$name" "$version"
            found=$((found + 1))
        fi
    done
    log_ok "$found package manager(s) available"
}

run_audit() {
    echo "═══════════════════════════════════════════════"
    echo "  CLI Tools Environment Audit"
    echo "═══════════════════════════════════════════════"
    echo ""
    # check_path and check_duplicates return their issue count; under set -e
    # a bare call would end the audit at the first issue.
    check_path || true
    echo ""
    check_duplicates || true
    echo ""
    check_package_managers
    echo ""
    check_project "$PROJECT_DIR"
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  Core Tools"
    echo "═══════════════════════════════════════════════"
    check_tool git || true
    check_tool jq || true
    check_tool ripgrep || true
    # Debian and Ubuntu ship fd and bat as fdfind and batcat
    check_tool fd "$(debian_alias fd fdfind)" || true
    check_tool fzf || true
    check_tool bat "$(debian_alias bat batcat)" || true
}

case "$ACTION" in
    audit | check) run_audit ;;
    path) check_path ;;
    duplicates) check_duplicates ;;
    project) check_project "$PROJECT_DIR" ;;
    managers) check_package_managers ;;
    update-check) DRY_RUN=1 "$DIR/auto_update.sh" update ;;
    *)
        echo "Usage: $0 {audit|path|duplicates|project|managers|update-check} [project_dir]" >&2
        exit 1
        ;;
esac
