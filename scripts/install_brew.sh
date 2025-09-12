#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"

install_brew() {
  if have brew; then log "brew already installed"; return 0; fi
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -d "/home/linuxbrew/.linuxbrew" ]; then
    echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> "$HOME/.bash_profile" || true
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  fi
}

update_brew() { have brew && brew update && brew upgrade || true; }

uninstall_brew() {
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)" || true
}

case "$ACTION" in
  install) install_brew ;;
  update) update_brew ;;
  uninstall) uninstall_brew ;;
  reconcile) install_brew ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac

echo "brew: $ACTION complete (or attempted)."


