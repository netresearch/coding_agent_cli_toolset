#!/usr/bin/env bash
set -euo pipefail

# wslu provides `wslview`, which opens URLs/files in the Windows default browser.
# It is only meaningful under WSL, so every action is a graceful no-op elsewhere.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"

wslview_version() { have wslview && wslview --version 2>/dev/null | head -1 || true; }

set_default_browser() {
  # Point the xdg default browser at wslview so links (xdg-open, Python's
  # webbrowser, MCP servers, etc.) open in the Windows browser instead of a
  # WSLg Linux browser. Opt out with WSLU_SET_DEFAULT_BROWSER=0.
  [ "${WSLU_SET_DEFAULT_BROWSER:-1}" = "1" ] || {
    echo "[wslu] WSLU_SET_DEFAULT_BROWSER=0 - leaving default browser unchanged"
    return 0
  }
  have xdg-settings || {
    echo "[wslu] xdg-settings not found - skipping default-browser setup"
    return 0
  }
  local current
  current="$(xdg-settings get default-web-browser 2>/dev/null || true)"
  if [ "$current" = "wslview.desktop" ]; then
    echo "[wslu] default web browser already wslview.desktop"
    return 0
  fi
  if xdg-settings set default-web-browser wslview.desktop 2>/dev/null; then
    echo "[wslu] default web browser set to wslview.desktop (was: ${current:-unset})"
  else
    echo "[wslu] could not set default browser (non-fatal); run: xdg-settings set default-web-browser wslview.desktop"
  fi
}

install_wslu() {
  if ! is_wsl; then
    echo "[wslu] Not running under WSL - nothing to do (wslu/wslview only applies on WSL)."
    return 0
  fi
  echo "[wslu] current: $(wslview_version)"
  if have apt-get; then
    apt_install_if_missing wslu || { echo "[wslu] apt install failed" >&2; return 1; }
  elif have dnf; then
    sudo dnf install -y wslu
  elif have pacman; then
    sudo pacman -S --noconfirm wslu
  elif have zypper; then
    sudo zypper install -y wslu
  else
    echo "[wslu] No supported package manager found." >&2
    echo "[wslu] Install wslu manually: https://wslutiliti.es/wslu/install.html" >&2
    return 1
  fi
  echo "[wslu] installed: $(wslview_version)"
  set_default_browser
}

uninstall_wslu() {
  if have apt-get; then
    apt_remove_if_present wslu
  elif have dnf; then
    sudo dnf remove -y wslu || true
  elif have pacman; then
    sudo pacman -R --noconfirm wslu || true
  elif have zypper; then
    sudo zypper remove -y wslu || true
  else
    echo "[wslu] Please remove wslu via your system package manager." >&2
  fi
}

case "$ACTION" in
  install|update) install_wslu ;;
  uninstall) uninstall_wslu ;;
  *) echo "Usage: $0 {install|update|uninstall}" >&2 ; exit 2 ;;
esac
