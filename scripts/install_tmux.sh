#!/usr/bin/env bash
# Install tmux from GitHub source releases (builds from source)
# Needed because apt often lags several major versions behind.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="tmux"
INSTALL_PREFIX="${HOME}/.local"
GITHUB_REPO="tmux/tmux"

get_installed_version() {
  if command -v tmux >/dev/null 2>&1; then
    tmux -V 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[a-z]?' || echo ""
  fi
}

install_tmux() {
  local version="${1:-}"

  if [ -z "$version" ]; then
    echo "[$TOOL] Fetching latest release..." >&2
    version="$(gh api repos/$GITHUB_REPO/releases/latest --jq '.tag_name' 2>/dev/null || true)"
  fi

  if [ -z "$version" ]; then
    echo "[$TOOL] Error: Could not determine latest version" >&2
    return 1
  fi

  local before="$(get_installed_version)"

  # Ensure build dependencies
  local missing_deps=()
  dpkg -s libevent-dev >/dev/null 2>&1 || missing_deps+=(libevent-dev)
  dpkg -s libncurses-dev >/dev/null 2>&1 || missing_deps+=(libncurses-dev)
  dpkg -s bison >/dev/null 2>&1 || missing_deps+=(bison)
  dpkg -s autoconf >/dev/null 2>&1 || missing_deps+=(autoconf)
  dpkg -s automake >/dev/null 2>&1 || missing_deps+=(automake)
  dpkg -s pkg-config >/dev/null 2>&1 || missing_deps+=(pkg-config)

  if [ ${#missing_deps[@]} -gt 0 ]; then
    echo "[$TOOL] Installing build dependencies: ${missing_deps[*]}" >&2
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${missing_deps[@]}"
  fi

  local tarball="tmux-${version}.tar.gz"
  local url="https://github.com/$GITHUB_REPO/releases/download/${version}/${tarball}"
  local tmpdir="$(mktemp -d)"

  echo "[$TOOL] Downloading $url..." >&2
  if ! curl -sL "$url" -o "$tmpdir/$tarball"; then
    echo "[$TOOL] Error: Failed to download $url" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  echo "[$TOOL] Extracting and building..." >&2
  tar -xzf "$tmpdir/$tarball" -C "$tmpdir"

  # Find the extracted directory (may be tmux-3.6a or tmux-3.6)
  local src_dir
  src_dir="$(find "$tmpdir" -maxdepth 1 -type d -name 'tmux-*' | head -1)"
  if [ -z "$src_dir" ]; then
    echo "[$TOOL] Error: Could not find source directory in tarball" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  cd "$src_dir"

  # Configure and build
  if [ -f configure.ac ] && [ ! -f configure ]; then
    autoreconf -fi
  fi

  ./configure --prefix="$INSTALL_PREFIX" >/dev/null 2>&1

  make -j"$(nproc)" >/dev/null 2>&1

  mkdir -p "$INSTALL_PREFIX/bin"
  make install >/dev/null 2>&1

  cd /
  rm -rf "$tmpdir"

  # Rehash so the new binary is found
  hash -r 2>/dev/null || true

  local after="$(get_installed_version)"
  printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
  printf "[%s] path:   %s\n" "$TOOL" "$(command -v tmux 2>/dev/null || echo "$INSTALL_PREFIX/bin/tmux")"

  # Refresh snapshot
  refresh_snapshot "$TOOL"

  return 0
}

# Main
case "${1:-install}" in
  install|update)
    install_tmux "${2:-}"
    ;;
  uninstall)
    echo "[$TOOL] Removing $INSTALL_PREFIX/bin/tmux" >&2
    rm -f "$INSTALL_PREFIX/bin/tmux"
    hash -r 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 [install|update|uninstall] [version]" >&2
    exit 1
    ;;
esac
