#!/usr/bin/env bash
# Install tree from GitHub source (builds from source)
# Needed because apt often lags behind upstream.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="tree"
INSTALL_DIR="${HOME}/.local/bin"
GITHUB_REPO="Old-Man-Programmer/tree"

get_installed_version() {
  if command -v tree >/dev/null 2>&1; then
    tree --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo ""
  fi
}

install_tree() {
  local version="${1:-}"

  if [ -z "$version" ]; then
    echo "[$TOOL] Fetching latest tag..." >&2
    version="$(gh api repos/$GITHUB_REPO/tags --jq '.[0].name' 2>/dev/null || true)"
  fi

  if [ -z "$version" ]; then
    echo "[$TOOL] Error: Could not determine latest version" >&2
    return 1
  fi

  local before="$(get_installed_version)"

  local url="https://github.com/$GITHUB_REPO/archive/refs/tags/${version}.tar.gz"
  local tmpdir="$(mktemp -d)"

  echo "[$TOOL] Downloading $url..." >&2
  if ! curl -sL "$url" -o "$tmpdir/tree.tar.gz"; then
    echo "[$TOOL] Error: Failed to download $url" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  echo "[$TOOL] Building..." >&2
  tar -xzf "$tmpdir/tree.tar.gz" -C "$tmpdir"

  local src_dir
  src_dir="$(find "$tmpdir" -maxdepth 1 -type d -name 'tree-*' | head -1)"
  if [ -z "$src_dir" ]; then
    echo "[$TOOL] Error: Could not find source directory" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  cd "$src_dir"
  make -j"$(nproc)" >/dev/null 2>&1

  mkdir -p "$INSTALL_DIR"
  cp tree "$INSTALL_DIR/tree"
  chmod +x "$INSTALL_DIR/tree"

  cd /
  rm -rf "$tmpdir"

  hash -r 2>/dev/null || true

  local after="$(get_installed_version)"
  printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
  printf "[%s] path:   %s\n" "$TOOL" "$(command -v tree 2>/dev/null || echo "$INSTALL_DIR/tree")"

  # Refresh snapshot
  refresh_snapshot "$TOOL"

  return 0
}

# Main
case "${1:-install}" in
  install|update)
    install_tree "${2:-}"
    ;;
  uninstall)
    echo "[$TOOL] Removing $INSTALL_DIR/tree" >&2
    rm -f "$INSTALL_DIR/tree"
    hash -r 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 [install|update|uninstall] [version]" >&2
    exit 1
    ;;
esac
