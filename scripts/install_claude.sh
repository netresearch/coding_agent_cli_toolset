#!/usr/bin/env bash
# Dedicated installer for Claude Code CLI
# Uses official native installer (recommended) with fallbacks
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-install}"

# Get current version
get_current_version() {
  local claude_bin
  claude_bin=$(command -v claude 2>/dev/null || true)

  if [ -z "$claude_bin" ]; then
    echo ""
    return
  fi

  local real_path
  real_path=$(readlink -f "$claude_bin" 2>/dev/null || echo "$claude_bin")

  # If npm install, get version from package.json (avoids Node.js version issues)
  if echo "$real_path" | grep -q 'node_modules'; then
    local pkg_dir
    pkg_dir=$(dirname "$real_path")
    if [ -f "$pkg_dir/package.json" ]; then
      grep '"version"' "$pkg_dir/package.json" | head -1 | sed 's/.*"version": *"\([0-9][0-9.]*\)".*/\1/' && return
    fi
  fi

  # For native installs, try --version
  timeout 2 "$claude_bin" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
}

# Install via native installer (recommended)
install_native() {
  echo "[claude] Installing via native installer (recommended)..." >&2

  if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
    # macOS / Linux / WSL
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://claude.ai/install.sh | bash
      return $?
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://claude.ai/install.sh | bash
      return $?
    fi
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
  if echo "$real_path" | grep -q 'node_modules'; then
    echo "[claude] Detected npm installation, upgrading via npm..." >&2
    npm update -g @anthropic-ai/claude-code || install_native
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
