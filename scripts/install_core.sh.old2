#!/usr/bin/env bash
set -euo pipefail

# Install/update/uninstall simple, language-agnostic tools.
# All tools with catalog entries now use install_tool.sh

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"
ONLY_TOOL="${2:-}"

# reconcile_one: Install or update a single tool
reconcile_one() {
  local t="$1"

  # Check if tool has catalog entry
  if [ -f "$DIR/../catalog/$t.json" ]; then
    # Use catalog-based installer
    "$DIR/install_tool.sh" "$t"
  else
    # Handle non-cataloged tools (system packages, special cases)
    case "$t" in
      git)
        # Git requires PPA and source build logic
        if have brew; then brew install git || brew upgrade git || true; return; fi
        if have apt-get; then
          sudo apt-get update && (sudo apt-get install -y --only-upgrade git || sudo apt-get install -y git)
        fi
        ;;
      ctags)
        # Universal ctags requires source build with checkinstall
        if have brew; then brew install universal-ctags || brew install ctags; return; fi
        if have apt-get; then
          (sudo apt-get install -y universal-ctags || sudo apt-get install -y exuberant-ctags ctags)
        fi
        ;;
      cscope)
        if have brew; then brew install cscope; return; fi
        if have apt-get; then sudo apt-get install -y cscope; return; fi
        ;;
      gam)
        # GAM has complex multi-directory installation
        echo "[$t] GAM installation requires special handling - use original script" >&2
        ;;
      eslint)
        # Node.js packages
        ensure_nvm_loaded || true
        if command -v npm >/dev/null 2>&1; then
          env -u PREFIX npm install -g "$t" || env -u PREFIX npm install -g --prefix "$HOME/.local" "$t"
        fi
        ;;
      *)
        echo "[$t] Unknown tool - no catalog entry or special handler" >&2
        return 1
        ;;
    esac
  fi
}

install_core_tools() {
  for t in fd fzf ripgrep jq yq bat delta just; do
    reconcile_one "$t"
  done
}

update_core_tools() {
  if have brew; then
    brew upgrade fd fzf ripgrep jq yq bat git-delta just || true
  fi
  # For cataloged tools, just call reconcile which will update them
  for t in fd fzf ripgrep jq yq bat delta just; do
    reconcile_one "$t"
  done
}

uninstall_core_tools() {
  if have brew; then brew uninstall -f fd fzf ripgrep jq yq bat git-delta just || true; fi
  apt_remove_if_present fd-find fzf ripgrep jq yq bat || true
}

case "$ACTION" in
  install) install_core_tools ;;
  update) update_core_tools ;;
  uninstall) uninstall_core_tools ;;
  reconcile)
    if [ -n "$ONLY_TOOL" ]; then
      reconcile_one "$ONLY_TOOL"
    else
      for t in fd fzf ripgrep jq yq bat delta just; do reconcile_one "$t"; done
    fi
    ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
