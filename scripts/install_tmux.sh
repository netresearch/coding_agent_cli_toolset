#!/usr/bin/env bash
# Install tmux from GitHub source releases (builds from source)
# Needed because apt often lags several major versions behind.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/install_strategy.sh
. "$DIR/lib/install_strategy.sh"

TOOL="tmux"
INSTALL_PREFIX="${HOME}/.local"
GITHUB_REPO="tmux/tmux"
BUILD_LOG=""
BUILD_TMPDIR=""

cleanup() {
  if [ -n "$BUILD_TMPDIR" ] && [ -d "$BUILD_TMPDIR" ]; then
    rm -rf "$BUILD_TMPDIR"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

show_build_failure() {
  local step="$1"
  echo "[$TOOL] Error: $step failed" >&2
  if [ -n "$BUILD_LOG" ] && [ -f "$BUILD_LOG" ]; then
    echo "[$TOOL] Last build output:" >&2
    tail -n 40 "$BUILD_LOG" >&2
  fi
}

get_installed_version() {
  if command -v tmux >/dev/null 2>&1; then
    tmux -V 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[a-z]?' || echo ""
  fi
}

get_target_version() {
  local version=""
  if command -v gh >/dev/null 2>&1; then
    version="$(gh api "repos/$GITHUB_REPO/releases/latest" --jq '.tag_name' 2>/dev/null || true)"
  fi
  if [ -z "$version" ]; then
    version="$(curl -fsSIL -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' \
      "https://github.com/$GITHUB_REPO/releases/latest" 2>/dev/null | awk -F/ '{print $NF}')"
  fi
  printf '%s' "$version"
}

install_tmux() {
  local version="${1:-}"

  if [ -z "$version" ]; then
    echo "[$TOOL] Fetching latest release..." >&2
    version="$(get_target_version)"
  fi

  if [ -z "$version" ]; then
    echo "[$TOOL] Error: Could not determine latest version" >&2
    return 1
  fi

  local before
  before="$(get_installed_version)"

  # Ensure build dependencies
  local missing_deps=()
  dpkg -s build-essential >/dev/null 2>&1 || missing_deps+=(build-essential)
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
  BUILD_TMPDIR="$(mktemp -d)"
  BUILD_LOG="$BUILD_TMPDIR/build.log"

  echo "[$TOOL] Downloading $url..." >&2
  if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 \
    "$url" -o "$BUILD_TMPDIR/$tarball"; then
    echo "[$TOOL] Error: Failed to download $url" >&2
    return 1
  fi

  echo "[$TOOL] Extracting and building..." >&2
  if ! tar -xzf "$BUILD_TMPDIR/$tarball" -C "$BUILD_TMPDIR"; then
    echo "[$TOOL] Error: Invalid source archive: $url" >&2
    return 1
  fi

  # Find the extracted directory (may be tmux-3.6a or tmux-3.6)
  local src_dir
  src_dir="$(find "$BUILD_TMPDIR" -maxdepth 1 -type d -name 'tmux-*' | head -1)"
  if [ -z "$src_dir" ]; then
    echo "[$TOOL] Error: Could not find source directory in tarball" >&2
    return 1
  fi

  cd "$src_dir"

  # Configure and build
  if [ -f configure.ac ] && [ ! -f configure ]; then
    if ! autoreconf -fi >"$BUILD_LOG" 2>&1; then
      show_build_failure "autoreconf"
      return 1
    fi
  fi

  if ! ./configure --prefix="$INSTALL_PREFIX" >"$BUILD_LOG" 2>&1; then
    show_build_failure "configure"
    return 1
  fi

  if ! make -j"$(nproc)" >>"$BUILD_LOG" 2>&1; then
    show_build_failure "build"
    return 1
  fi

  # Install only the executable. `make install` also writes the optional
  # manpage below ~/.local/share and can fail in restricted/sandboxed WSL
  # environments after the binary has already been installed successfully.
  mkdir -p "$INSTALL_PREFIX/bin"
  if ! install -m 0755 tmux "$INSTALL_PREFIX/bin/tmux" >>"$BUILD_LOG" 2>&1; then
    show_build_failure "install"
    return 1
  fi

  cd /
  local installed_binary="$INSTALL_PREFIX/bin/tmux"
  local after=""
  if [ -x "$installed_binary" ]; then
    after="$("$installed_binary" -V 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[a-z]?' || true)"
  fi
  if [ "$after" != "$version" ]; then
    echo "[$TOOL] Error: Installed binary reports '${after:-<none>}', expected '$version'" >&2
    return 1
  fi

  printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
  printf "[%s] path:   %s\n" "$TOOL" "$installed_binary"

  if [ -n "${TMUX:-}" ]; then
    echo "[$TOOL] note:   tmux $after is installed; restart the running tmux server to use it" >&2
  fi

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
