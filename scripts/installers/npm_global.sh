#!/usr/bin/env bash
# Generic installer for npm global packages
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

# Load nvm if available (needed for node-based package managers)
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh" --no-use
  nvm use default >/dev/null 2>&1 || true
fi

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

# Validate tool name to prevent path traversal
if [[ "$TOOL" == *"/"* ]] || [[ "$TOOL" == *".."* ]]; then
  echo "Error: Invalid tool name: $TOOL" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

# Parse catalog
PACKAGE_NAME="$(jq -r '.package_name // .name' "$CATALOG_FILE")"
BINARY_NAME="$(jq -r '.binary_name // empty' "$CATALOG_FILE")"
BINARY_NAME="${BINARY_NAME:-$TOOL}"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"
VERSION_FLAG="$(jq -r '.version_flag // empty' "$CATALOG_FILE")"

# Detect available package manager (pnpm > npm > yarn)
# Only use pnpm if it's properly configured with a global bin directory
PKG_MANAGER=""
if command -v pnpm >/dev/null 2>&1; then
  # Check if pnpm has a global-bin-dir configured
  if pnpm config get global-bin-dir 2>/dev/null | grep -qv "undefined"; then
    PKG_MANAGER="pnpm"
  fi
fi
if [ -z "$PKG_MANAGER" ] && command -v npm >/dev/null 2>&1; then
  PKG_MANAGER="npm"
elif [ -z "$PKG_MANAGER" ] && command -v yarn >/dev/null 2>&1; then
  PKG_MANAGER="yarn"
fi

if [ -z "$PKG_MANAGER" ]; then
  echo "[$TOOL] Error: No package manager found (pnpm, npm, or yarn required)" >&2
  exit 1
fi

# Version detection helper (uses catalog version_command/version_flag if available).
# Takes the resolved binary PATH (which may live in npm's global bin dir even
# when that dir is off PATH) so detection works regardless of PATH state.
get_npm_tool_version() {
  local bin_path="$1"
  local bin_dir=""
  [ -n "$bin_path" ] && bin_dir="$(dirname "$bin_path")"
  if [ -n "$VERSION_COMMAND" ]; then
    # version_command runs even when bin_path is empty (the catalog command may
    # locate the tool itself). Only extend PATH when the resolved bin dir is
    # genuinely off PATH: this lets a bare-name version_command resolve an
    # off-PATH npm-global install, without letting that dir shadow normal PATH
    # lookups (or a hostile npm prefix plant a sibling binary) in the common case.
    local pfx=""
    if [ -n "$bin_dir" ]; then
      case ":$PATH:" in
        *":$bin_dir:"*) : ;;
        *) pfx="$bin_dir:" ;;
      esac
    fi
    PATH="${pfx}$PATH" timeout 8 bash -c "$VERSION_COMMAND" 2>/dev/null | head -1 || true
    return
  fi
  [ -z "$bin_path" ] && return
  if [ -n "$VERSION_FLAG" ]; then
    timeout 8 "$bin_path" $VERSION_FLAG </dev/null 2>/dev/null | head -1 || true
  else
    timeout 8 "$bin_path" --version </dev/null 2>/dev/null | head -1 || true
  fi
}

# Get current version (resolve_global_bin also checks npm's global bin dir)
before="$(get_npm_tool_version "$(resolve_global_bin "$BINARY_NAME")")"

# Install or upgrade globally
echo "[$TOOL] Installing package globally via $PKG_MANAGER: $PACKAGE_NAME" >&2
case "$PKG_MANAGER" in
  pnpm)
    pnpm add -g "${PACKAGE_NAME}@latest" 2>&1 | grep -v "^npm warn deprecated" || {
      echo "[$TOOL] Error: pnpm install failed" >&2
      exit 1
    }
    ;;
  npm)
    # Try normal install first; retry with --force on EEXIST errors
    if ! npm install -g "${PACKAGE_NAME}@latest" 2>&1 | grep -v "^npm warn deprecated"; then
      if npm install -g --force "${PACKAGE_NAME}@latest" 2>&1 | grep -v "^npm warn deprecated"; then
        : # Force install succeeded
      else
        echo "[$TOOL] Error: npm install failed" >&2
        exit 1
      fi
    fi
    ;;
  yarn)
    yarn global add "${PACKAGE_NAME}@latest" 2>&1 | grep -v "^npm warn deprecated" || {
      echo "[$TOOL] Error: yarn install failed" >&2
      exit 1
    }
    ;;
esac

# Report
path="$(resolve_global_bin "$BINARY_NAME")"
after="$(get_npm_tool_version "$path")"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then
  printf "[%s] path:   %s\n" "$TOOL" "$path"
  # Surface the real reason a freshly-installed tool can be "missing": npm put
  # it in a global bin dir that is not on PATH.
  warn_if_bin_off_path "$TOOL" "$path"
fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
