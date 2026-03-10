#!/usr/bin/env bash
# pip installer - ensures pip is available via Python's ensurepip
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

ACTION="${1:-install}"

get_pip_version() {
  if command -v pip3 >/dev/null 2>&1; then
    pip3 --version 2>/dev/null | awk '{print $2}' || true
  elif command -v pip >/dev/null 2>&1; then
    pip --version 2>/dev/null | awk '{print $2}' || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m pip --version 2>/dev/null | awk '{print $2}' || true
  fi
}

install_pip() {
  local before after path

  before="$(get_pip_version)"

  # Ensure Python is available
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[pip] Error: python3 not found. Install Python first." >&2
    exit 1
  fi

  # Use ensurepip to bootstrap pip if not present
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "[pip] Bootstrapping pip via ensurepip..." >&2
    python3 -m ensurepip --upgrade 2>&1 || {
      echo "[pip] ensurepip failed, trying apt..." >&2
      apt_install_if_missing python3-pip || true
    }
  fi

  # Upgrade pip to latest
  # Use uv if available (avoids externally-managed-environment errors)
  if command -v uv >/dev/null 2>&1; then
    # uv manages Python installations; pip upgrade is best left to uv's Python
    echo "[pip] pip is managed by the Python distribution (uv/brew). Skipping standalone upgrade." >&2
  else
    # Only attempt pip upgrade if not in an externally-managed environment
    python3 -m pip install --upgrade pip 2>&1 | grep -v "externally-managed-environment" || true
  fi

  after="$(get_pip_version)"
  path="$(command -v pip3 2>/dev/null || command -v pip 2>/dev/null || true)"

  printf "[%s] before: %s\n" "pip" "${before:-<none>}"
  printf "[%s] after:  %s\n" "pip" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "pip" "$path"; fi

  refresh_snapshot "pip"
}

uninstall_pip() {
  echo "[pip] pip is bundled with Python and cannot be uninstalled separately" >&2
}

case "$ACTION" in
  install|update|reconcile) install_pip ;;
  uninstall) uninstall_pip ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac
