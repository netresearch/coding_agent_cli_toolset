#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-reconcile}"

# Ensure only the official GitHub binary distribution of uv is present.
cleanup_other_uv() {
  local BIN
  BIN="$HOME/.local/bin/uv"
  # Remove pipx-managed uv
  if command -v pipx >/dev/null 2>&1; then
    pipx uninstall uv >/dev/null 2>&1 || true
  fi
  # Remove pip-installed uv (best effort)
  if command -v python3 >/dev/null 2>&1; then
    python3 -m pip uninstall -y uv >/dev/null 2>&1 || true
  fi
  # Remove common symlinks/binaries pointing to non-official locations
  if [ -L "$BIN" ]; then
    real="$(readlink -f "$BIN" 2>/dev/null || echo)"
    case "$real" in
      "$HOME/.local/pipx/venvs/uv"/*) rm -f "$BIN" >/dev/null 2>&1 || true ;;
    esac
  fi
  rm -f "$HOME/.cargo/bin/uv" "$HOME/.cargo/bin/uvx" >/dev/null 2>&1 || true
  rm -f "$HOME/.local/bin/uvx" >/dev/null 2>&1 || true
  # Remove other uv occurrences on PATH that are not the target BIN
  if command -v uv >/dev/null 2>&1; then
    while IFS= read -r p; do
      p="${p%%$'\r'}"
      if [ -n "$p" ] && [ "$p" != "$BIN" ]; then
        if [ -w "$p" ]; then rm -f "$p" >/dev/null 2>&1 || true; else command -v sudo >/dev/null 2>&1 && sudo -n rm -f "$p" >/dev/null 2>&1 || true; fi
      fi
    done < <(which -a uv 2>/dev/null | awk 'NR>0{print $0}')
  fi
}

install_official_uv() {
  mkdir -p "$HOME/.local/bin" >/dev/null 2>&1 || true
  if command -v curl >/dev/null 2>&1; then
    sh -c "$(curl -LsSf https://astral.sh/uv/install.sh)" || true
  else
    echo "curl is required to install uv" >&2
    return 1
  fi
}

self_update_uv() {
  command -v uv >/dev/null 2>&1 || return 0
  local before after
  before="$(uv --version 2>/dev/null | awk '{print $2}' || echo 'unknown')"
  uv self update --no-progress 2>&1 | grep -v "^info:" || true
  after="$(uv --version 2>/dev/null | awk '{print $2}' || echo 'unknown')"
  if [ "$before" != "$after" ]; then
    echo "uv upgraded: $before → $after"
  else
    echo "uv already at latest version: $after"
  fi
}

upgrade_uv_tools() {
  command -v uv >/dev/null 2>&1 || return 0
  echo "Checking uv-managed tools..."
  uv tool upgrade --all || true
}

reconcile_uv() {
  cleanup_other_uv
  # If uv missing or not under ~/.local/bin, install official
  local path
  path="$(command -v uv 2>/dev/null || true)"
  if [ -z "$path" ] || [ "$path" != "$HOME/.local/bin/uv" ]; then
    install_official_uv || true
  fi
  # Try self-update to latest stable
  self_update_uv || true
  # Upgrade all uv-managed tools
  upgrade_uv_tools || true
  # Verify final state
  echo "uv path: $(command -v uv 2>/dev/null || echo '<none>')"
  uv --version 2>/dev/null || true
}

case "$ACTION" in
  install|reconcile)
    reconcile_uv ;;
  update)
    self_update_uv || true
    upgrade_uv_tools || true ;;
  uninstall)
    cleanup_other_uv
    rm -f "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx" >/dev/null 2>&1 || true ;;
  *)
    echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
 esac
