#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"

install_rust() {
  if have cargo; then log "cargo already present"; return 0; fi
  curl -fsSL https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1090
  [ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
}

update_rust() {
  rustup_update || true
}

uninstall_rust() {
  rustup_uninstall || true
  apt_remove_if_present rustc cargo || true
}

reconcile_rust() {
  if ! prefers_rustup; then
    log "Switching to rustup-managed toolchain"
    apt_remove_if_present rustc cargo || true
    uninstall_rust || true
  fi
  install_rust
  # Always update to latest after ensuring rustup installation
  update_rust
}

case "$ACTION" in
  install) install_rust ;;
  update) update_rust ;;
  uninstall) uninstall_rust ;;
  reconcile) reconcile_rust ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac

echo "rust: $ACTION complete (or attempted)."


