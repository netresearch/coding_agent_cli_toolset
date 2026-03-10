#!/usr/bin/env bash
# Generic installer for uv tools
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

# Parse catalog
PACKAGE_NAME="$(jq -r '.package_name' "$CATALOG_FILE")"
PYTHON_VERSION="$(jq -r '.python_version // empty' "$CATALOG_FILE")"
BINARY_NAME="$(jq -r '.binary_name // empty' "$CATALOG_FILE")"
# Use binary_name if specified, otherwise fall back to tool name
BINARY_NAME="${BINARY_NAME:-$TOOL}"

# Ensure uv is available
if ! command -v uv >/dev/null 2>&1; then
  echo "[$TOOL] Error: uv not found. Please install uv first." >&2
  exit 1
fi

# Get current version
# Some tools need special handling for version detection
VERSION_FLAG="$(jq -r '.version_flag // empty' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"

get_uv_tool_version() {
  local tool="$1" bin="$2" flag="${3:---version}"
  # Use catalog-specified version command if available (most reliable)
  if [ -n "$VERSION_COMMAND" ]; then
    local ver
    ver="$(timeout 2 bash -c "$VERSION_COMMAND" 2>/dev/null || true)"
    if [ -n "$ver" ]; then
      echo "$ver"
      return
    fi
  fi
  # Try the binary with its version flag
  if command -v "$bin" >/dev/null 2>&1; then
    local ver
    ver="$(timeout 2 "$bin" $flag </dev/null 2>/dev/null || true)"
    if [ -n "$ver" ]; then
      echo "$ver"
      return
    fi
  fi
  # Fallback: extract version from uv tool list
  uv tool list 2>/dev/null | grep -E "^${PACKAGE_NAME} " | head -1 || true
}

before="$(get_uv_tool_version "$TOOL" "$BINARY_NAME" "${VERSION_FLAG:---version}")"
# Fallback: if binary version detection failed, try uv tool list directly
if [ -z "$before" ] || [ "$before" = "<none>" ]; then
  before="$(uv tool list 2>/dev/null | grep -E "^${PACKAGE_NAME} " | head -1 | sed 's/^[^ ]* //' || true)"
fi

# Install or upgrade with optional Python version pinning
# Use --upgrade (not --force) to avoid unnecessary reinstalls
if [ -n "$PYTHON_VERSION" ]; then
  echo "[$TOOL] Installing with Python $PYTHON_VERSION..."
  uv tool install --upgrade --python "$PYTHON_VERSION" "$PACKAGE_NAME" || \
    uv tool install --force --upgrade --python "$PYTHON_VERSION" "$PACKAGE_NAME" || true
else
  uv tool install --upgrade "$PACKAGE_NAME" || \
    uv tool install --force --upgrade "$PACKAGE_NAME" || true
fi

# Report
after="$(get_uv_tool_version "$TOOL" "$BINARY_NAME" "${VERSION_FLAG:---version}")"
# Normalize multi-line or verbose version output to a clean version string
before="$(normalize_version_output "${before:-}")"
after="$(normalize_version_output "${after:-}")"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
# Source install_strategy.sh for refresh_snapshot function
. "$(dirname "${BASH_SOURCE[0]}")/../lib/install_strategy.sh"
refresh_snapshot "$TOOL"
