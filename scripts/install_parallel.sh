#!/usr/bin/env bash
# Install GNU Parallel from FTP releases
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="parallel"
INSTALL_DIR="${HOME}/.local/bin"
FTP_URL="https://ftp.gnu.org/gnu/parallel/"

get_latest_version() {
  curl -sL "$FTP_URL" | \
    grep -oE 'parallel-[0-9]+\.tar\.' | \
    sed 's/parallel-//; s/\.tar\.//' | \
    sort -rn | head -1
}

get_installed_version() {
  if command -v parallel >/dev/null 2>&1; then
    parallel --version 2>/dev/null | head -1 | grep -oE '[0-9]{8}' || echo ""
  fi
}

install_parallel() {
  local version="${1:-}"

  if [ -z "$version" ]; then
    echo "[$TOOL] Fetching latest version..." >&2
    version="$(get_latest_version)"
  fi

  if [ -z "$version" ]; then
    echo "[$TOOL] Error: Could not determine latest version" >&2
    return 1
  fi

  local before="$(get_installed_version)"
  echo "[$TOOL] before: $before" >&2

  local tarball="parallel-${version}.tar.bz2"
  local url="${FTP_URL}${tarball}"
  local tmpdir="$(mktemp -d)"

  echo "[$TOOL] Downloading $url..." >&2

  mkdir -p "$INSTALL_DIR"

  if ! curl -sL "$url" -o "$tmpdir/$tarball"; then
    echo "[$TOOL] Error: Failed to download $url" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  echo "[$TOOL] Extracting..." >&2
  tar -xjf "$tmpdir/$tarball" -C "$tmpdir"

  # Install the main script
  local src_dir="$tmpdir/parallel-${version}/src"
  if [ -f "$src_dir/parallel" ]; then
    cp "$src_dir/parallel" "$INSTALL_DIR/parallel"
    chmod +x "$INSTALL_DIR/parallel"
    echo "[$TOOL] Installed parallel to $INSTALL_DIR/parallel" >&2
  else
    echo "[$TOOL] Error: parallel script not found in tarball" >&2
    rm -rf "$tmpdir"
    return 1
  fi

  # Install additional tools if present
  for script in parcat parsort parset niceload sql sem env_parallel; do
    if [ -f "$src_dir/$script" ]; then
      cp "$src_dir/$script" "$INSTALL_DIR/$script"
      chmod +x "$INSTALL_DIR/$script"
    fi
  done

  rm -rf "$tmpdir"

  local after="$(get_installed_version)"
  echo "[$TOOL] after:  $after" >&2
  echo "[$TOOL] path:   $(command -v parallel 2>/dev/null || echo "$INSTALL_DIR/parallel")" >&2

  # Refresh snapshot
  refresh_snapshot "$TOOL"

  return 0
}

uninstall_parallel() {
  echo "[$TOOL] Uninstalling parallel..." >&2

  # Remove all parallel-related binaries from install dir
  for script in parallel parcat parsort parset niceload sql sem env_parallel; do
    if [ -f "$INSTALL_DIR/$script" ]; then
      echo "[$TOOL] Removing $INSTALL_DIR/$script" >&2
      rm -f "$INSTALL_DIR/$script"
    fi
  done

  # Also check command -v in case it was installed elsewhere
  local parallel_bin
  parallel_bin="$(command -v parallel 2>/dev/null || echo "")"
  if [ -n "$parallel_bin" ] && [ -f "$parallel_bin" ]; then
    local bin_dir
    bin_dir="$(dirname "$parallel_bin")"
    echo "[$TOOL] Removing $parallel_bin" >&2
    if [ -w "$bin_dir" ]; then
      rm -f "$parallel_bin"
    else
      echo "[$TOOL] Cannot remove $parallel_bin (no write access), try: sudo rm -f $parallel_bin" >&2
    fi
  fi

  echo "[$TOOL] Uninstall complete" >&2
  refresh_snapshot "$TOOL"
}

# Main
case "${1:-install}" in
  install|update)
    install_parallel "${2:-}"
    ;;
  uninstall)
    uninstall_parallel
    ;;
  *)
    echo "Usage: $0 [install|update|uninstall] [version]" >&2
    exit 1
    ;;
esac
