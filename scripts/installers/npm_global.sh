#!/usr/bin/env bash
# Generic installer for npm global packages
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Parse catalog
PACKAGE_NAME="$(jq -r '.package_name // .name' "$CATALOG_FILE")"

# Ensure npm is available
if ! command -v npm >/dev/null 2>&1; then
  echo "[$TOOL] Error: npm not found. Please install Node.js and npm first." >&2
  exit 1
fi

# Get current version
before=""
if command -v "$TOOL" >/dev/null 2>&1; then
  before="$("$TOOL" --version 2>/dev/null || true)"
fi

# Install or upgrade globally
echo "[$TOOL] Installing npm package globally: $PACKAGE_NAME" >&2
npm install -g "$PACKAGE_NAME" || {
  echo "[$TOOL] Error: npm install failed" >&2
  exit 1
}

# Report
after=""
if command -v "$TOOL" >/dev/null 2>&1; then
  after="$("$TOOL" --version 2>/dev/null || true)"
fi

path="$(command -v "$TOOL" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
