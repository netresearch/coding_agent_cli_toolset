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

# Ensure uv is available
if ! command -v uv >/dev/null 2>&1; then
  echo "[$TOOL] Error: uv not found. Please install uv first." >&2
  exit 1
fi

# Get current version
before="$(command -v "$TOOL" >/dev/null 2>&1 && "$TOOL" --version 2>/dev/null || true)"

# Install or upgrade
uv tool install --force --upgrade "$PACKAGE_NAME" || true

# Report
after="$(command -v "$TOOL" >/dev/null 2>&1 && "$TOOL" --version 2>/dev/null || true)"
path="$(command -v "$TOOL" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi
