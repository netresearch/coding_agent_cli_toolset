#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-update}"

ensure_rbenv_loaded() {
  # Add rbenv to PATH and initialize if available
  if [ -d "$HOME/.rbenv" ]; then
    export PATH="$HOME/.rbenv/bin:$PATH"
    if command -v rbenv >/dev/null 2>&1; then
      eval "$(rbenv init - bash)" || true
    fi
  fi
}

update_gem() {
  ensure_rbenv_loaded

  if ! command -v gem >/dev/null 2>&1; then
    echo "[gem] Error: gem not found. Install Ruby first via 'make install-ruby' or 'scripts/install_ruby.sh'" >&2
    return 1
  fi

  local before after path
  before="$(gem --version 2>/dev/null || echo '<none>')"

  # Update RubyGems itself
  gem update --system || true

  # Update bundler and rake
  gem update bundler rake || true

  # Rehash rbenv shims if using rbenv
  if command -v rbenv >/dev/null 2>&1; then
    rbenv rehash || true
  fi

  after="$(gem --version 2>/dev/null || echo '<none>')"
  path="$(command -v gem 2>/dev/null || echo '<none>')"

  printf "[%s] before: %s\n" "gem" "$before"
  printf "[%s] after:  %s\n" "gem" "$after"
  printf "[%s] path:   %s\n" "gem" "$path"
}

install_gem() {
  echo "[gem] gem comes bundled with Ruby. Installing/updating Ruby instead..."
  "$DIR/install_ruby.sh" install || true
  update_gem
}

reconcile_gem() {
  ensure_rbenv_loaded

  if ! command -v gem >/dev/null 2>&1; then
    echo "[gem] gem not found. Installing Ruby (which includes gem)..."
    "$DIR/install_ruby.sh" reconcile || true
  fi

  update_gem
}

uninstall_gem() {
  echo "[gem] gem is bundled with Ruby. To remove gem, uninstall Ruby via 'scripts/install_ruby.sh uninstall'" >&2
}

case "$ACTION" in
  install) install_gem ;;
  update) update_gem ;;
  uninstall) uninstall_gem ;;
  reconcile) reconcile_gem ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
