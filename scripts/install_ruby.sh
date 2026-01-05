#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-reconcile}"
# Target Ruby version (default: latest stable)
RUBY_VERSION="${RUBY_VERSION:-3.3.6}"

ensure_rbenv() {
  if [ ! -d "$HOME/.rbenv" ]; then
    echo "Installing rbenv..."
    git clone https://github.com/rbenv/rbenv.git "$HOME/.rbenv"
    cd "$HOME/.rbenv" && src/configure && make -C src || true
  fi

  # Install ruby-build plugin if missing
  if [ ! -d "$HOME/.rbenv/plugins/ruby-build" ]; then
    echo "Installing ruby-build plugin..."
    git clone https://github.com/rbenv/ruby-build.git "$HOME/.rbenv/plugins/ruby-build"
  fi

  ensure_rbenv_loaded
}

ensure_rbenv_loaded() {
  # Add rbenv to PATH and initialize if not already done
  export PATH="$HOME/.rbenv/bin:$PATH"
  if command -v rbenv >/dev/null 2>&1; then
    eval "$(rbenv init - bash)" || true
  fi
}

get_latest_ruby_version() {
  ensure_rbenv
  # Get latest stable Ruby version from rbenv (MRI Ruby only, excludes jruby/mruby/truffleruby)
  rbenv install --list 2>/dev/null | grep -E '^\s*[0-9]+\.[0-9]+\.[0-9]+$' | tail -1 | tr -d ' ' || echo "4.0.0"
}

install_ruby() {
  ensure_rbenv

  # Use latest if RUBY_VERSION not specified
  if [ "$RUBY_VERSION" = "latest" ]; then
    RUBY_VERSION=$(get_latest_ruby_version)
  fi

  echo "Installing Ruby $RUBY_VERSION via rbenv..."
  if ! rbenv install --skip-existing "$RUBY_VERSION"; then
    echo "[ruby] Error: Failed to install Ruby $RUBY_VERSION" >&2
    echo "[ruby] You may need to install build dependencies:" >&2
    echo "[ruby]   sudo apt install build-essential libssl-dev libreadline-dev zlib1g-dev libyaml-dev libffi-dev" >&2
    return 1
  fi

  # Verify the version is actually installed before continuing
  if ! rbenv versions --bare | grep -q "^${RUBY_VERSION}$"; then
    echo "[ruby] Error: Ruby $RUBY_VERSION not found after install" >&2
    return 1
  fi

  rbenv global "$RUBY_VERSION" || true
  rbenv rehash || true

  # Update gem itself
  gem update --system || true

  # Install common gems
  gem install bundler rake || true
  rbenv rehash || true
}

update_ruby() {
  ensure_rbenv

  # Get current version
  local current_version target_version
  current_version=$(rbenv global 2>/dev/null || echo "")

  # Use RUBY_VERSION if set, otherwise get latest from rbenv
  if [ -n "${RUBY_VERSION:-}" ] && [ "$RUBY_VERSION" != "latest" ]; then
    target_version="$RUBY_VERSION"
  else
    target_version=$(get_latest_ruby_version)
    RUBY_VERSION="$target_version"
  fi

  echo "Current Ruby: $current_version"
  echo "Target Ruby: $target_version"

  # Install target if different
  if [ "$current_version" != "$target_version" ]; then
    install_ruby
  else
    # Just update gems
    gem update --system || true
    gem update bundler rake || true
    rbenv rehash || true
  fi
}

uninstall_ruby() {
  # Remove rbenv-managed Ruby
  if [ -d "$HOME/.rbenv" ]; then
    rm -rf "$HOME/.rbenv"
  fi

  # Remove apt Ruby if present
  apt_remove_if_present ruby ruby-dev ruby-rubygems || true
}

prefers_rbenv_ruby() {
  local ruby_path
  ruby_path="$(command -v ruby 2>/dev/null || true)"

  # Prefer rbenv if Ruby is under ~/.rbenv
  case "$ruby_path" in
    "$HOME/.rbenv/"*) return 0 ;;
    *) return 1 ;;
  esac
}

reconcile_ruby() {
  local before after path
  before="$(command -v ruby >/dev/null 2>&1 && ruby --version || true)"

  if ! prefers_rbenv_ruby; then
    echo "Removing apt-managed Ruby in favor of rbenv..."
    apt_remove_if_present ruby ruby-dev ruby-rubygems || true
    install_ruby
  else
    update_ruby
  fi

  after="$(command -v ruby >/dev/null 2>&1 && ruby --version || true)"
  path="$(command -v ruby 2>/dev/null || true)"

  printf "[%s] before: %s\n" "ruby" "${before:-<none>}"
  printf "[%s] after:  %s\n" "ruby" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "ruby" "$path"; fi
}

case "$ACTION" in
  install) install_ruby ;;
  update) update_ruby ;;
  uninstall) uninstall_ruby ;;
  reconcile) reconcile_ruby ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
