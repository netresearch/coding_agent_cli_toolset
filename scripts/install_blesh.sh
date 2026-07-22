#!/usr/bin/env bash
# Install ble.sh (Bash Line Editor) from source.
# ble.sh is *sourced* into interactive Bash (not a PATH binary): it installs to
# ~/.local/share/blesh/ble.sh and is loaded via a managed block in ~/.bashrc.
# Recommended upstream install is `git clone --recursive` + `make install`.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="blesh"
GITHUB_REPO="akinomyoga/ble.sh"
INSTALL_PREFIX="${HOME}/.local"
SRC_DIR="${HOME}/.local/src/ble.sh"
BLE_FILE="${INSTALL_PREFIX}/share/blesh/ble.sh"
SHARE_DIR="${INSTALL_PREFIX}/share/blesh"
BASHRC="${HOME}/.bashrc"

# Managed .bashrc block delimiters (must be unique and stable)
BEGIN_MARK="# >>> cli-audit: ble.sh >>>"
END_MARK="# <<< cli-audit: ble.sh <<<"

get_installed_version() {
  if [ -f "$BLE_FILE" ]; then
    bash "$BLE_FILE" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+[^ ]*' | head -1 || true
  fi
}

# Idempotently ensure the source line is present in ~/.bashrc.
ensure_bashrc_block() {
  [ -f "$BASHRC" ] || touch "$BASHRC"
  if grep -qF "$BEGIN_MARK" "$BASHRC" 2>/dev/null; then
    return 0
  fi
  {
    printf '\n%s\n' "$BEGIN_MARK"
    printf '[[ $- == *i* ]] && source -- %s\n' "$BLE_FILE"
    printf '%s\n' "$END_MARK"
  } >>"$BASHRC"
  echo "[$TOOL] Added ble.sh source line to $BASHRC" >&2
}

# Remove the managed block from ~/.bashrc (deletes only the delimited region).
remove_bashrc_block() {
  [ -f "$BASHRC" ] || return 0
  grep -qF "$BEGIN_MARK" "$BASHRC" 2>/dev/null || return 0
  local tmp
  tmp="$(mktemp)"
  # Hardened: if the begin marker has no matching end marker (tampering / a
  # write interrupted mid-block), restore the region intact rather than
  # deleting everything that follows the begin marker.
  awk -v b="$BEGIN_MARK" -v e="$END_MARK" '
    !skip && $0 == b { skip=1; buf=$0 ORS; next }
    skip {
      buf = buf $0 ORS
      if ($0 == e) { skip=0; buf="" }
      next
    }
    { print }
    END { if (skip) printf "%s", buf }
  ' "$BASHRC" >"$tmp"
  cat "$tmp" >"$BASHRC"
  rm -f "$tmp"
  echo "[$TOOL] Removed ble.sh source line from $BASHRC" >&2
}

ensure_deps() {
  local missing_deps=()
  command -v git >/dev/null 2>&1 || missing_deps+=(git)
  command -v make >/dev/null 2>&1 || missing_deps+=(make)
  command -v gawk >/dev/null 2>&1 || missing_deps+=(gawk)
  if [ ${#missing_deps[@]} -gt 0 ]; then
    echo "[$TOOL] Installing build dependencies: ${missing_deps[*]}" >&2
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${missing_deps[@]}"
  fi
}

install_blesh() {
  ensure_deps

  local before
  before="$(get_installed_version)"

  # Clone or update the source tree (with submodules).
  if [ ! -d "$SRC_DIR/.git" ]; then
    echo "[$TOOL] Cloning $GITHUB_REPO..." >&2
    mkdir -p "$(dirname "$SRC_DIR")"
    rm -rf "$SRC_DIR"
    git clone --recursive --depth 1 --shallow-submodules \
      "https://github.com/${GITHUB_REPO}.git" "$SRC_DIR" || {
      echo "[$TOOL] Error: git clone failed" >&2
      return 1
    }
  else
    echo "[$TOOL] Updating $SRC_DIR..." >&2
    git -C "$SRC_DIR" fetch origin --depth 1 || {
      echo "[$TOOL] Error: git fetch failed" >&2
      return 1
    }
    git -C "$SRC_DIR" reset --hard origin/HEAD || {
      echo "[$TOOL] Error: git reset failed" >&2
      return 1
    }
    git -C "$SRC_DIR" submodule update --init --recursive --depth 1 || true
  fi

  echo "[$TOOL] Building and installing to $INSTALL_PREFIX..." >&2
  make -C "$SRC_DIR" install PREFIX="$INSTALL_PREFIX" >/dev/null || {
    echo "[$TOOL] Error: make install failed" >&2
    return 1
  }

  ensure_bashrc_block

  local after
  after="$(get_installed_version)"
  printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
  printf "[%s] after:  %s\n" "$TOOL" "${after:-<unknown>}"
  printf "[%s] path:   %s\n" "$TOOL" "$BLE_FILE"

  refresh_snapshot "$TOOL"
  return 0
}

uninstall_blesh() {
  echo "[$TOOL] Removing $SHARE_DIR and $SRC_DIR" >&2
  rm -rf "$SHARE_DIR" "$SRC_DIR"
  remove_bashrc_block
}

# Only dispatch when executed directly; allow sourcing for tests.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  case "${1:-install}" in
    install|update)
      install_blesh
      ;;
    uninstall)
      uninstall_blesh
      ;;
    *)
      echo "Usage: $0 [install|update|uninstall]" >&2
      exit 1
      ;;
  esac
fi
