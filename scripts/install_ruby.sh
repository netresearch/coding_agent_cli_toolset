#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-reconcile}"
# Target Ruby version (default: latest stable)
RUBY_VERSION="${RUBY_VERSION:-3.3.6}"

# Get version of a specific Ruby installation
get_specific_ruby_version() {
  local version="$1"
  local ruby_bin="$HOME/.rbenv/versions/$version/bin/ruby"
  if [ -x "$ruby_bin" ]; then
    "$ruby_bin" --version 2>/dev/null || true
  fi
}

# Extract major.minor from full version (3.4.8 -> 3.4)
get_version_cycle() {
  echo "$1" | sed 's/^\([0-9]*\.[0-9]*\).*/\1/'
}

update_ruby_build() {
  local ruby_build_dir="$HOME/.rbenv/plugins/ruby-build"
  if [ -d "$ruby_build_dir/.git" ]; then
    echo "[ruby] Updating ruby-build definitions..."
    git -C "$ruby_build_dir" pull --quiet || true
  fi
}

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
  else
    # Update ruby-build to get latest version definitions
    update_ruby_build
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
  local latest
  latest=$(rbenv install --list 2>/dev/null | grep -E '^\s*[0-9]+\.[0-9]+\.[0-9]+$' | tail -1 | tr -d ' ')
  if [ -z "$latest" ]; then
    # Fallback to known stable version if list fails
    echo "${RUBY_VERSION:-3.3.6}"
  else
    echo "$latest"
  fi
}

install_ruby() {
  ensure_rbenv

  # Use latest if RUBY_VERSION not specified
  if [ "$RUBY_VERSION" = "latest" ]; then
    RUBY_VERSION=$(get_latest_ruby_version)
  fi

  # Check version before install
  local before="$(get_specific_ruby_version "$RUBY_VERSION")"
  local version_cycle="$(get_version_cycle "$RUBY_VERSION")"
  local display_name="ruby"
  [ -n "$version_cycle" ] && display_name="ruby@${version_cycle}"

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

  # Only set global if no global version is set yet
  local current_global="$(rbenv global 2>/dev/null || true)"
  if [ -z "$current_global" ] || [ "$current_global" = "system" ]; then
    rbenv global "$RUBY_VERSION" || true
  fi
  rbenv rehash || true

  # Update gem in this specific version
  RBENV_VERSION="$RUBY_VERSION" gem update --system || true

  # Install common gems in this specific version
  RBENV_VERSION="$RUBY_VERSION" gem install bundler rake || true
  rbenv rehash || true

  # Report version for this specific install
  local after="$(get_specific_ruby_version "$RUBY_VERSION")"
  local path="$HOME/.rbenv/versions/$RUBY_VERSION/bin/ruby"
  printf "[%s] before: %s\n" "$display_name" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$display_name" "${after:-<none>}"
  if [ -x "$path" ]; then printf "[%s] path:   %s\n" "$display_name" "$path"; fi
}

update_ruby() {
  ensure_rbenv

  # Use RUBY_VERSION if set, otherwise get latest from rbenv
  if [ -z "${RUBY_VERSION:-}" ] || [ "$RUBY_VERSION" = "latest" ]; then
    RUBY_VERSION=$(get_latest_ruby_version)
  fi

  # install_ruby handles its own before/after reporting
  install_ruby
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
  if ! prefers_rbenv_ruby; then
    echo "Removing apt-managed Ruby in favor of rbenv..."
    apt_remove_if_present ruby ruby-dev ruby-rubygems || true
  fi
  # install_ruby handles its own before/after reporting
  install_ruby
}

case "$ACTION" in
  install) install_ruby ;;
  update) update_ruby ;;
  uninstall) uninstall_ruby ;;
  reconcile) reconcile_ruby ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
