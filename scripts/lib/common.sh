#!/usr/bin/env bash
set -euo pipefail

# Common helpers for installer scripts

have() { command -v "$1" >/dev/null 2>&1; }

log() { printf '%s\n' "$*" >&2; }

os_id() {
  if [ -f /etc/os-release ]; then . /etc/os-release; echo "${ID:-unknown}"; else echo unknown; fi
}

ensure_sudo() { have sudo || { log "sudo not available"; exit 1; }; }

apt_remove_if_present() {
  have apt-get || return 0
  ensure_sudo
  for pkg in "$@"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then sudo apt-get remove -y "$pkg" || true; fi
  done
}

apt_purge_if_present() {
  have apt-get || return 0
  ensure_sudo
  for pkg in "$@"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then sudo apt-get purge -y "$pkg" || true; fi
  done
}

apt_install_if_missing() {
  have apt-get || return 1
  ensure_sudo
  for pkg in "$@"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y "$pkg" || return 1
    fi
  done
}

brew_install() { brew install "$@"; }
brew_upgrade() { brew upgrade "$@" || true; }
brew_uninstall() { brew uninstall -f "$@" || true; }

pipx_install() { have pipx || python3 -m pip install --user pipx; pipx install "$1" || true; }
pipx_upgrade() { have pipx && pipx upgrade "$1" || true; }
pipx_uninstall() { have pipx && pipx uninstall "$1" || true; }

# nvm helpers
ensure_nvm_loaded() {
  # shellcheck disable=SC1090,SC1091
  [ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" || true
}

nvm_install_lts() { ensure_nvm_loaded; have nvm || return 1; nvm install --lts; }
nvm_use_lts() { ensure_nvm_loaded; have nvm || return 1; nvm use --lts || nvm alias default 'lts/*' || true; }

# rustup helpers
rustup_update() { have rustup && rustup self update && rustup update || true; }
rustup_uninstall() { have rustup && rustup self uninstall -y || true; }

# Paths helpers for preferred sources
is_path_under() { case "$1" in "$2"*) return 0 ;; *) return 1 ;; esac }

prefers_nvm_node() {
  local p
  p="$(command -v node || true)"
  # Resolve symlinks: a ~/.local/bin/node shim often points into ~/.nvm, in
  # which case node is still nvm-managed and must not trigger the apt path.
  [ -n "$p" ] && p="$(readlink -f "$p" 2>/dev/null || echo "$p")"
  is_path_under "$p" "$HOME/.nvm" || return 1
}

prefers_rustup() {
  local p
  p="$(command -v cargo || true)"
  is_path_under "$p" "$HOME/.cargo" || return 1
}

# rbenv helpers
ensure_rbenv_loaded() {
  # Add rbenv to PATH and initialize if available
  if [ -d "$HOME/.rbenv" ]; then
    export PATH="$HOME/.rbenv/bin:$PATH"
    if command -v rbenv >/dev/null 2>&1; then
      eval "$(rbenv init - bash)" || true
    fi
  fi
}

prefers_rbenv_ruby() {
  local p
  p="$(command -v ruby || true)"
  is_path_under "$p" "$HOME/.rbenv" || return 1
}

# True if directory $1 is an exact member of PATH.
path_contains_dir() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

# npm installs global packages into `npm prefix -g`/bin, which is NOT always on
# PATH (e.g. when a stale node shim hijacks the prefix). These helpers locate a
# globally-installed binary even when it landed off PATH, so a successful
# install is not misreported as <none> or "binary not found".
npm_global_bin_dir() {
  command -v npm >/dev/null 2>&1 || return 0
  local p
  p="$(npm prefix -g 2>/dev/null || true)"
  [[ -n "$p" ]] && printf '%s/bin' "$p"
  return 0
}

# Resolve a global CLI binary path: prefer PATH, fall back to npm's global bin.
resolve_global_bin() {
  local bin="$1" p
  p="$(command -v "$bin" 2>/dev/null || true)"
  if [[ -z "$p" ]]; then
    local gdir
    gdir="$(npm_global_bin_dir)"
    [[ -n "$gdir" ]] && [[ -x "$gdir/$bin" ]] && p="$gdir/$bin"
  fi
  printf '%s' "$p"
}

# Warn (to stderr) when a binary's directory is not on PATH.
warn_if_bin_off_path() {
  local label="$1" bin_path="$2"
  [[ -z "$bin_path" ]] && return 0
  local d
  d="$(dirname "$bin_path")"
  path_contains_dir "$d" && return 0
  log "[$label] warning: $d is not on PATH; your shell will not find '$(basename "$bin_path")' until you add that directory to PATH (for an nvm global bin, make it your nvm default, then run 'hash -r')"
}

# Ensure uv is available, offer to install if missing
ensure_uv() {
  have uv && return 0
  log "Error: uv is required but not installed."
  log ""
  log "Install uv:"
  log "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  log ""
  log "Or run: make upgrade-uv"
  log ""
  log "See: https://docs.astral.sh/uv/"
  # Auto-install if interactive and install script exists
  local install_script="${DIR:-}/install_uv.sh"
  if [ -t 0 ] && [ -f "$install_script" ]; then
    read -rp "Install uv now? [Y/n] " answer
    case "${answer:-y}" in
      [Yy]*|"") bash "$install_script" && have uv && return 0 ;;
    esac
  fi
  return 1
}

# WSL detection
is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null
}

# Normalize version output to a concise single-line format
# Extracts the first version-like string (X.Y.Z or X.Y) from potentially verbose output
# Usage: normalize_version_output "golangci-lint has version 2.11.3 built with go1.26.1..."
#        → "2.11.3"
normalize_version_output() {
  local raw="$1"
  [ -z "$raw" ] && return
  # Take only first line
  raw="$(echo "$raw" | head -1)"
  # Try to extract a version number (X.Y.Z or X.Y)
  local ver
  ver="$(echo "$raw" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ -z "$ver" ]; then
    ver="$(echo "$raw" | grep -oE '[0-9]+\.[0-9]+' | head -1)"
  fi
  # If we got a version, print it; otherwise print the raw first line (trimmed)
  if [ -n "$ver" ]; then
    echo "$ver"
  else
    echo "$raw"
  fi
}


