#!/usr/bin/env bash
# Generic installer for uv tools
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# Get current version (skip for tools that hang or don't output proper versions)
# codex/gam binaries hang on --version
# git-filter-repo outputs git hash instead of version
if [ "$TOOL" = "codex" ] || [ "$TOOL" = "gam" ] || [ "$TOOL" = "git-filter-repo" ]; then
  before="<none>"
else
  before="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && timeout 2 "$BINARY_NAME" --version </dev/null 2>/dev/null || true)"
fi

# Install or upgrade with optional Python version pinning
if [ -n "$PYTHON_VERSION" ]; then
  echo "[$TOOL] Installing with Python $PYTHON_VERSION..."
  uv tool install --force --upgrade --python "$PYTHON_VERSION" "$PACKAGE_NAME" || true
else
  uv tool install --force --upgrade "$PACKAGE_NAME" || true
fi

# Report
if [ "$TOOL" = "codex" ] || [ "$TOOL" = "gam" ] || [ "$TOOL" = "git-filter-repo" ]; then
  # These tools hang or don't output proper versions - use uv tool list instead
  # Use the specific package name for this tool to avoid matching wrong package
  after="$(uv tool list 2>/dev/null | grep -E "^${PACKAGE_NAME} " | head -1 || echo "<failed>")"
else
  after="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && timeout 2 "$BINARY_NAME" --version 2>/dev/null || true)"
fi
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
# Source install_strategy.sh for refresh_snapshot function
. "$(dirname "${BASH_SOURCE[0]}")/../lib/install_strategy.sh"
refresh_snapshot "$TOOL"
