#!/usr/bin/env bash
# Shared installation strategy logic for all install scripts

# Determine installation directory based on INSTALL_STRATEGY
# Usage: get_install_dir TOOL_NAME
# Returns: Directory path where tool should be installed
get_install_dir() {
  local tool_name="${1:-}"
  local strategy="${INSTALL_STRATEGY:-USER}"
  local prefix="${PREFIX:-$HOME/.local}"
  local bin_dir=""

  case "$strategy" in
    CURRENT)
      # Keep tool where it is currently installed
      if [ -n "$tool_name" ]; then
        local current_path="$(command -v "$tool_name" 2>/dev/null || true)"
        if [ -n "$current_path" ]; then
          bin_dir="$(dirname "$current_path")"
        else
          # Not installed, fall back to USER
          bin_dir="$prefix/bin"
        fi
      else
        # No specific tool, fall back to USER
        bin_dir="$prefix/bin"
      fi
      ;;
    GLOBAL)
      bin_dir="/usr/local/bin"
      ;;
    PROJECT)
      bin_dir="./.local/bin"
      ;;
    USER|*)
      bin_dir="$prefix/bin"
      ;;
  esac

  echo "$bin_dir"
}

# Get install command based on target directory
# Usage: get_install_cmd BIN_DIR
# Sets: INSTALL and RM variables
get_install_cmd() {
  local bin_dir="$1"

  if [ "$bin_dir" = "/usr/local/bin" ]; then
    if [ -w "$bin_dir" ]; then
      INSTALL="install -m 0755"
      RM="rm -f"
    else
      INSTALL="sudo install -m 0755"
      RM="sudo rm -f"
    fi
  else
    INSTALL="install -m 0755"
    RM="rm -f"
  fi
}
