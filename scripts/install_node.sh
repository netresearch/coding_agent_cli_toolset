#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

ACTION="${1:-install}"
# Channel: 'node' (current latest), 'lts', or specific major version (24, 25, etc.)
# NODE_VERSION takes precedence for multi-version installs (e.g., NODE_VERSION=24)
NODE_CHANNEL="${NODE_VERSION:-${NODE_CHANNEL:-node}}"

# For multi-version display
DISPLAY_NAME="node"
if [ -n "${NODE_VERSION:-}" ]; then
  DISPLAY_NAME="node@${NODE_VERSION}"
fi

ensure_nvm() {
  if ! have nvm; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  ensure_nvm_loaded
}

# Get version of a specific Node.js major version (e.g., "24" -> "v24.13.0")
get_specific_node_version() {
  local channel="$1"
  ensure_nvm_loaded
  # nvm version returns the installed version for a channel/alias
  local ver
  ver="$(nvm version "$channel" 2>/dev/null || true)"
  if [ -n "$ver" ] && [ "$ver" != "N/A" ]; then
    echo "$ver"
  fi
}

install_node() {
  ensure_nvm
  nvm install "$NODE_CHANNEL"

  # Only set default if this is NOT a multi-version install
  # (multi-version = specific major version like 24, 25)
  if [ -z "${NODE_VERSION:-}" ]; then
    # Resolve the concrete version (e.g. v24.8.0) and pin default to it
    local resolved
    resolved="$(nvm version "$NODE_CHANNEL" 2>/dev/null || true)"
    if [ -n "$resolved" ] && [ "$resolved" != "N/A" ]; then
      nvm alias default "$resolved" || true
      nvm use "$resolved" || nvm use default || true
    else
      # Fallback to channel if resolution failed for any reason
      nvm alias default "$NODE_CHANNEL" || true
      nvm use default || true
    fi
    corepack enable 2>/dev/null || true
    npm install -g npm@latest || true
    corepack prepare pnpm@latest --activate 2>/dev/null || true
    corepack prepare yarn@1 --activate 2>/dev/null || true
    npm install -g eslint prettier || true
  else
    echo "=> Node.js version $NODE_VERSION has been successfully installed"
  fi
}

update_node() {
  ensure_nvm
  nvm install "$NODE_CHANNEL"

  # Only set default and update global packages if NOT a multi-version install
  if [ -z "${NODE_VERSION:-}" ]; then
    # Resolve and pin default to the exact installed version
    local resolved
    resolved="$(nvm version "$NODE_CHANNEL" 2>/dev/null || true)"
    if [ -n "$resolved" ] && [ "$resolved" != "N/A" ]; then
      nvm alias default "$resolved" || true
      nvm use "$resolved" || nvm use default || true
    else
      nvm alias default "$NODE_CHANNEL" || true
      nvm use default || true
    fi
    # Ensure corepack shims are present
    corepack enable 2>/dev/null || true
    npm install -g npm@latest || true
    # Update pnpm and yarn via corepack; fall back to npm global if corepack unavailable
    corepack prepare pnpm@latest --activate 2>/dev/null || npm install -g pnpm@latest || true
    corepack prepare yarn@1 --activate 2>/dev/null || npm install -g yarn@latest || true
    npm update -g eslint prettier || true
  else
    echo "=> Node.js version $NODE_VERSION has been updated"
  fi
}

uninstall_node() {
  # remove nvm-managed node
  if [ -d "$HOME/.nvm" ]; then rm -rf "$HOME/.nvm"; fi
  apt_remove_if_present nodejs npm || true
}

reconcile_node() {
  local before after path

  # For multi-version installs, check the specific version being installed
  if [ -n "${NODE_VERSION:-}" ]; then
    before="$(get_specific_node_version "$NODE_CHANNEL")"
  else
    before="$(command -v node >/dev/null 2>&1 && node -v || true)"
  fi

  if ! prefers_nvm_node; then
    apt_remove_if_present nodejs npm || true
    install_node
  else
    update_node
  fi

  # Check version of the specific channel we installed
  if [ -n "${NODE_VERSION:-}" ]; then
    after="$(get_specific_node_version "$NODE_CHANNEL")"
    # Get path to the specific version's node binary
    local nvm_dir="${NVM_DIR:-$HOME/.nvm}"
    local resolved_ver="$(nvm version "$NODE_CHANNEL" 2>/dev/null || true)"
    if [ -n "$resolved_ver" ] && [ "$resolved_ver" != "N/A" ]; then
      path="$nvm_dir/versions/node/$resolved_ver/bin/node"
    fi
  else
    after="$(command -v node >/dev/null 2>&1 && node -v || true)"
    path="$(command -v node 2>/dev/null || true)"
  fi

  printf "[%s] before: %s\n" "$DISPLAY_NAME" "${before:-<none>}"
  printf "[%s] after:  %s\n"  "$DISPLAY_NAME" "${after:-<none>}"
  if [ -n "$path" ] && [ -x "$path" ]; then printf "[%s] path:   %s\n" "$DISPLAY_NAME" "$path"; fi

  refresh_snapshot "node"
}

case "$ACTION" in
  install) install_node ;;
  update) update_node ;;
  uninstall) uninstall_node ;;
  reconcile) reconcile_node ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac


