#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"
# Channel: 'node' (current latest) or 'lts'. Default to 'node' to match audit latest
NODE_CHANNEL="${NODE_CHANNEL:-node}"

ensure_nvm() {
  if ! have nvm; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  ensure_nvm_loaded
}

install_node() {
  ensure_nvm
  nvm install "$NODE_CHANNEL"
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
  corepack enable || true
  npm install -g npm@latest || true
  corepack prepare pnpm@latest --activate || true
  corepack prepare yarn@1 --activate || true
  npm install -g eslint prettier || true
}

update_node() {
  ensure_nvm
  nvm install "$NODE_CHANNEL"
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
  corepack enable || true
  npm install -g npm@latest || true
  # Update pnpm and yarn via corepack; fall back to npm global if corepack unavailable
  corepack prepare pnpm@latest --activate || npm install -g pnpm@latest || true
  corepack prepare yarn@1 --activate || npm install -g yarn@latest || true
  npm update -g eslint prettier || true
}

uninstall_node() {
  # remove nvm-managed node
  if [ -d "$HOME/.nvm" ]; then rm -rf "$HOME/.nvm"; fi
  apt_remove_if_present nodejs npm || true
}

reconcile_node() {
  local before after path
  before="$(command -v node >/dev/null 2>&1 && node -v || true)"
  if ! prefers_nvm_node; then
    apt_remove_if_present nodejs npm || true
    install_node
  else
    update_node
  fi
  after="$(command -v node >/dev/null 2>&1 && node -v || true)"
  path="$(command -v node 2>/dev/null || true)"
  printf "[%s] before: %s\n" "node" "${before:-<none>}"
  printf "[%s] after:  %s\n"  "node" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "node" "$path"; fi
}

case "$ACTION" in
  install) install_node ;;
  update) update_node ;;
  uninstall) uninstall_node ;;
  reconcile) reconcile_node ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac


