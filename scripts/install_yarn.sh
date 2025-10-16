#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-update}"

check_nvm_node() {
  # Check if Node.js is nvm-managed
  local node_path
  node_path="$(command -v node 2>/dev/null || echo '')"

  case "$node_path" in
    "$HOME/.nvm/"*)
      return 0  # nvm-managed
      ;;
    *)
      return 1  # not nvm-managed (apt, system, or missing)
      ;;
  esac
}

update_yarn() {
  ensure_nvm_loaded

  if ! command -v node >/dev/null 2>&1; then
    echo "[yarn] Error: Node.js not found. Install Node.js first via 'make install-node' or 'scripts/install_node.sh'" >&2
    return 1
  fi

  # Check if Node.js is nvm-managed before trying to update yarn
  if ! check_nvm_node; then
    echo "[yarn] Error: Node.js is not nvm-managed (currently apt/system)" >&2
    echo "[yarn] Cannot update yarn for system Node.js" >&2
    echo "[yarn] Please install Node.js via nvm first:" >&2
    echo "[yarn]   make install-node" >&2
    echo "[yarn]   or: scripts/install_node.sh reconcile" >&2
    return 1
  fi

  local before after path
  before="$(yarn --version 2>/dev/null || echo '<none>')"

  # Try corepack first (modern approach)
  if command -v corepack >/dev/null 2>&1; then
    echo "[yarn] Updating yarn via corepack..." >&2
    corepack enable || true
    corepack prepare yarn@stable --activate || true
  else
    # Fallback to npm global install
    echo "[yarn] Updating yarn via npm..." >&2
    npm install -g yarn@latest || true
  fi

  after="$(yarn --version 2>/dev/null || echo '<none>')"
  path="$(command -v yarn 2>/dev/null || echo '<none>')"

  printf "[%s] before: %s\n" "yarn" "$before"
  printf "[%s] after:  %s\n" "yarn" "$after"
  printf "[%s] path:   %s\n" "yarn" "$path"
}

install_yarn() {
  echo "[yarn] yarn should be installed via Node.js corepack/npm. Installing/updating Node.js first..."
  "$DIR/install_node.sh" install || true
  update_yarn
}

reconcile_yarn() {
  ensure_nvm_loaded

  if ! command -v node >/dev/null 2>&1; then
    echo "[yarn] Node.js not found. Installing Node.js (which includes yarn via corepack)..."
    "$DIR/install_node.sh" reconcile || true
  elif ! check_nvm_node; then
    echo "[yarn] Node.js is not nvm-managed. Installing Node.js via nvm first..."
    "$DIR/install_node.sh" reconcile || true
  fi

  # Remove apt-installed cmdtest if present (Ubuntu's yarn package conflict)
  if command -v dpkg >/dev/null 2>&1 && dpkg -l | grep -q "^ii.*cmdtest"; then
    echo "[yarn] Removing apt package 'cmdtest' (conflicts with yarn)..." >&2
    apt_remove_if_present cmdtest yarnpkg || true
  fi

  update_yarn
}

uninstall_yarn() {
  echo "[yarn] yarn is managed by Node.js/npm. To remove:" >&2
  echo "[yarn]   npm uninstall -g yarn" >&2
  echo "[yarn]   or: corepack disable" >&2
}

case "$ACTION" in
  install) install_yarn ;;
  update) update_yarn ;;
  uninstall) uninstall_yarn ;;
  reconcile) reconcile_yarn ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
