#!/usr/bin/env bash
# Generic installer for Go tools via 'go install'
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

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

# Check if Go is available
if ! command -v go >/dev/null 2>&1; then
  echo "[$TOOL] Error: go not found. Install Go first." >&2
  exit 1
fi

# Parse catalog
BINARY_NAME="$(jq -r '.binary_name // .name' "$CATALOG_FILE")"
GO_PACKAGE="$(jq -r '.go_package // empty' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"
VERSION_REGEX="$(jq -r '.version_regex // empty' "$CATALOG_FILE")"

if [ -z "$GO_PACKAGE" ]; then
  echo "[$TOOL] Error: No go_package specified in catalog" >&2
  exit 1
fi

# Get current version
get_version() {
  if [ -n "$VERSION_COMMAND" ]; then
    timeout 2 bash -c "$VERSION_COMMAND" 2>/dev/null || true
  elif command -v "$BINARY_NAME" >/dev/null 2>&1; then
    timeout 2 "$BINARY_NAME" --version </dev/null 2>/dev/null | head -1 || \
    timeout 2 "$BINARY_NAME" version </dev/null 2>/dev/null | head -1 || true
  fi
}

before="$(get_version)"

# Install/update via go install
echo "[$TOOL] Installing via go install: ${GO_PACKAGE}@latest" >&2
go install "${GO_PACKAGE}@latest" || {
  echo "[$TOOL] Error: go install failed" >&2
  exit 1
}

# Report
after="$(get_version)"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
