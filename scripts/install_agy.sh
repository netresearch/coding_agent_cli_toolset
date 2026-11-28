#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
# Dedicated installer for the Google Antigravity CLI (agy)
# Uses the official installer; updates go through the CLI's own updater
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-install}"
INSTALLER_URL="https://antigravity.google/cli/install.sh"
BIN_DIR="$HOME/.local/bin"
AGY_BIN="$BIN_DIR/agy"
# curl may only use https, including on redirects
CURL_HTTPS_ONLY=(--proto '=https')

get_current_version() {
  timeout 2 agy --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
}

# True when ~/.local/bin is already a PATH entry
bin_dir_on_path() {
  case ":$PATH:" in
    *":$BIN_DIR:"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Run the official installer. It downloads the binary, checks its SHA512
# against the release manifest and then runs `agy install`, which appends a
# PATH line to ~/.bashrc and ~/.profile. When ~/.local/bin is already on PATH
# that line only moves the directory to the front, so pass --skip-path.
install_native() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "[agy] curl is required for the official installer" >&2
    return 1
  fi
  local work_dir installer_script
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/cli-audit-agy.XXXXXX")" || return 1
  installer_script="$work_dir/install.sh"

  if ! curl "${CURL_HTTPS_ONLY[@]}" -fsSL "$INSTALLER_URL" -o "$installer_script"; then
    echo "[agy] Failed to download $INSTALLER_URL" >&2
    rm -rf "$work_dir"
    return 1
  fi

  if bin_dir_on_path; then
    # The anchor is the line that hands over to `agy install`; if Google
    # changes it, install without the patch rather than fail
    if grep -qF '"$BINARY_PATH" install || true' "$installer_script"; then
      # sed without -i: BSD and GNU sed disagree on its argument
      sed 's/"\$BINARY_PATH" install || true/"\$BINARY_PATH" install --skip-path || true/' \
        "$installer_script" >"$installer_script.patched" && mv "$installer_script.patched" "$installer_script"
    else
      echo "[agy] Warning: installer layout changed; it may add a PATH line to your shell profile" >&2
    fi
  fi

  local rc=0
  bash "$installer_script" || rc=$?
  rm -rf "$work_dir"
  return "$rc"
}

install_agy() {
  local before after path
  before="$(get_current_version)"

  if [ -x "$AGY_BIN" ]; then
    echo "[agy] Already installed at $AGY_BIN; it updates itself (run: agy update)" >&2
  elif ! install_native; then
    echo "[agy] Error: installation failed" >&2
    echo "[agy] Install manually: curl -fsSL $INSTALLER_URL | bash" >&2
    return 1
  fi

  hash -r 2>/dev/null || true
  after="$(get_current_version)"
  path="$(command -v agy 2>/dev/null || true)"

  printf "[%s] before: %s\n" "agy" "${before:-<none>}"
  printf "[%s] after:  %s\n" "agy" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "agy" "$path"; fi

  if [ -f "$DIR/lib/install_strategy.sh" ]; then
    . "$DIR/lib/install_strategy.sh"
    refresh_snapshot "agy" 2>/dev/null || true
  fi
}

upgrade_agy() {
  if [ ! -x "$AGY_BIN" ]; then
    echo "[agy] Not installed, running install..." >&2
    install_agy
    return $?
  fi
  "$AGY_BIN" update </dev/null
  hash -r 2>/dev/null || true
  printf "[%s] after:  %s\n" "agy" "$(get_current_version)"
}

uninstall_agy() {
  if [ ! -e "$AGY_BIN" ]; then
    echo "[agy] Not installed at $AGY_BIN" >&2
    return 0
  fi
  rm -f "$AGY_BIN"
  hash -r 2>/dev/null || true
  echo "[agy] Removed $AGY_BIN" >&2
  echo "[agy] Settings and sign-in remain in ~/.config/antigravity; remove them by hand if wanted" >&2
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "$ACTION" in
    install) install_agy ;;
    update|upgrade) upgrade_agy ;;
    uninstall) uninstall_agy ;;
    reconcile) install_agy ;;
    *) echo "Usage: $0 {install|update|upgrade|uninstall|reconcile}" ; exit 2 ;;
  esac
fi
