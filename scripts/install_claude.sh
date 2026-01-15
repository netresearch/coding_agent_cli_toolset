#!/usr/bin/env bash
# Dedicated installer for Claude Code CLI
# Uses official native installer (recommended) with fallbacks
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-install}"

# Get current version
get_current_version() {
  # Always use --version for accurate version detection
  timeout 2 claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
}

# Install via native installer (recommended)
# Accepts optional version argument to skip CDN version fetch
install_native() {
  local target_version="${1:-}"
  local use_force="${2:-}"
  echo "[claude] Installing via native installer (recommended)..." >&2

  if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
    # macOS / Linux / WSL
    local installer_script="/tmp/claude-install-$$.sh"

    # Download installer script
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://claude.ai/install.sh -o "$installer_script" || return 1
    elif command -v wget >/dev/null 2>&1; then
      wget -qO "$installer_script" https://claude.ai/install.sh || return 1
    else
      return 1
    fi

    # Patch installer to add --force flag if needed (handles network timeouts)
    if [ "$use_force" = "force" ]; then
      echo "[claude] Using --force to bypass network checks..." >&2
      sed -i 's/\$binary_path" install/\$binary_path" install --force/' "$installer_script"
    fi

    # Run installer with optional version
    local installer_args=""
    if [ -n "$target_version" ]; then
      installer_args="$target_version"
      echo "[claude] Using version: $target_version" >&2
    fi

    if bash "$installer_script" $installer_args; then
      rm -f "$installer_script"
      return 0
    fi

    # If failed without force, retry with force and explicit version
    if [ "$use_force" != "force" ]; then
      echo "[claude] Installer failed, retrying with --force..." >&2
      local github_version
      github_version=$(get_latest_version)
      if [ -n "$github_version" ]; then
        echo "[claude] Using version from GitHub: $github_version" >&2
        # Patch to add --force
        sed -i 's/\$binary_path" install/\$binary_path" install --force/' "$installer_script"
        if bash "$installer_script" "$github_version"; then
          rm -f "$installer_script"
          return 0
        fi
      fi
    fi

    rm -f "$installer_script"
    return 1
  fi

  return 1
}

# Install via Homebrew (macOS alternative)
install_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    echo "[claude] Installing via Homebrew cask..." >&2
    brew install --cask claude-code
    return $?
  fi
  return 1
}

# Install via npm (legacy fallback)
install_npm() {
  if command -v npm >/dev/null 2>&1; then
    # Check Node.js version - npm install doesn't work with v25+
    local node_version
    node_version=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)

    if [ -n "$node_version" ] && [ "$node_version" -ge 25 ]; then
      echo "[claude] Warning: npm install not supported on Node.js v25+ (SlowBuffer API removed)" >&2
      echo "[claude] Please use native installer: curl -fsSL https://claude.ai/install.sh | bash" >&2
      return 1
    fi

    echo "[claude] Installing via npm (legacy)..." >&2
    npm install -g @anthropic-ai/claude-code
    return $?
  fi
  return 1
}

# Get latest version from GitHub
get_latest_version() {
  curl -fsSIL -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' \
    "https://github.com/anthropics/claude-code/releases/latest" 2>/dev/null | awk -F'/' '{print $NF}' | sed 's/^v//'
}

# Compare versions (returns 0 if v1 < v2)
version_lt() {
  [ "$(printf '%s\n%s' "$1" "$2" | sort -V | head -1)" = "$1" ] && [ "$1" != "$2" ]
}

# Migrate from npm to native installer
migrate_npm_to_native() {
  echo "[claude] Migrating from npm to native installer..." >&2
  echo "[claude] Removing npm package..." >&2
  npm uninstall -g @anthropic-ai/claude-code 2>/dev/null || true
  hash -r 2>/dev/null || true
  echo "[claude] Installing native version..." >&2
  install_native
}

# Upgrade existing installation
upgrade_claude() {
  local claude_bin
  claude_bin=$(command -v claude 2>/dev/null || true)

  if [ -z "$claude_bin" ]; then
    echo "[claude] Not installed, running install..." >&2
    install_claude
    return $?
  fi

  local real_path
  real_path=$(readlink -f "$claude_bin" 2>/dev/null || echo "$claude_bin")

  # Detect installation method and upgrade accordingly
  # Check for npm install: node_modules in resolved path OR .nvm path (nvm-managed npm)
  if echo "$real_path" | grep -qE 'node_modules|\.nvm/'; then
    local current_ver
    current_ver=$(get_current_version)

    echo "[claude] Detected npm installation (v${current_ver:-unknown})" >&2
    echo "[claude] The npm package is deprecated. Migrating to native installer..." >&2
    migrate_npm_to_native
  elif echo "$real_path" | grep -q 'Cellar\|homebrew'; then
    echo "[claude] Detected Homebrew installation, upgrading via brew..." >&2
    brew upgrade --cask claude-code || brew reinstall --cask claude-code
  else
    echo "[claude] Detected native installation, re-running installer..." >&2
    install_native
  fi
}

# Main install function
install_claude() {
  local before after path
  before="$(get_current_version)"

  # Try installation methods in order of preference
  if ! install_native; then
    echo "[claude] Native installer failed, trying alternatives..." >&2
    if ! install_homebrew; then
      if ! install_npm; then
        echo "[claude] Error: All installation methods failed" >&2
        echo "[claude] Please install manually from: https://claude.ai/download" >&2
        return 1
      fi
    fi
  fi

  # Refresh PATH
  hash -r 2>/dev/null || true

  after="$(get_current_version)"
  path="$(command -v claude 2>/dev/null || true)"

  printf "[%s] before: %s\n" "claude" "${before:-<none>}"
  printf "[%s] after:  %s\n" "claude" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "claude" "$path"; fi

  # Refresh snapshot if available
  if [ -f "$DIR/lib/install_strategy.sh" ]; then
    . "$DIR/lib/install_strategy.sh"
    refresh_snapshot "claude" 2>/dev/null || true
  fi
}

# Uninstall
uninstall_claude() {
  local claude_bin
  claude_bin=$(command -v claude 2>/dev/null || true)

  if [ -z "$claude_bin" ]; then
    echo "[claude] Not installed" >&2
    return 0
  fi

  local real_path
  real_path=$(readlink -f "$claude_bin" 2>/dev/null || echo "$claude_bin")

  if echo "$real_path" | grep -q 'node_modules'; then
    echo "[claude] Uninstalling npm package..." >&2
    npm uninstall -g @anthropic-ai/claude-code
  elif echo "$real_path" | grep -q 'Cellar\|homebrew'; then
    echo "[claude] Uninstalling Homebrew cask..." >&2
    brew uninstall --cask claude-code
  else
    echo "[claude] Native installation detected" >&2
    echo "[claude] To uninstall, remove: $claude_bin" >&2
    echo "[claude] And optionally: rm -rf ~/.claude" >&2
  fi
}

case "$ACTION" in
  install) install_claude ;;
  update|upgrade) upgrade_claude ;;
  uninstall) uninstall_claude ;;
  reconcile) install_claude ;;
  *) echo "Usage: $0 {install|update|upgrade|uninstall|reconcile}" ; exit 2 ;;
esac
