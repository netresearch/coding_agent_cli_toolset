#!/usr/bin/env bash
# unpin_version.sh - Remove version pin from a tool
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

TOOL="${1:-}"

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  echo "" >&2
  echo "Remove version pin from a tool to resume upgrade prompts." >&2
  echo "" >&2
  echo "For multi-version tools (e.g., go@1.24, php@8.3):" >&2
  echo "  $0 go@1.24   # Remove pin for this version cycle" >&2
  exit 1
fi

# Handle multi-version tools (e.g., go@1.24 -> base=go, cycle=1.24)
BASE_TOOL="$TOOL"
VERSION_CYCLE=""
IS_MULTI_VERSION=""

if [[ "$TOOL" == *"@"* ]]; then
  BASE_TOOL="${TOOL%%@*}"
  VERSION_CYCLE="${TOOL#*@}"
  IS_MULTI_VERSION="true"
fi

CATALOG_FILE="$ROOT/catalog/$BASE_TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Tool '$BASE_TOOL' not found in catalog" >&2
  exit 1
fi

# Handle multi-version tools differently
if [ -n "$IS_MULTI_VERSION" ]; then
  # Check if pinned in pinned_versions object
  PINNED_VALUE="$(jq -r --arg cycle "$VERSION_CYCLE" '.pinned_versions[$cycle] // empty' "$CATALOG_FILE")"
  if [ -z "$PINNED_VALUE" ]; then
    echo "Tool '$TOOL' is not pinned" >&2
    exit 0
  fi

  echo "Removing version pin for '$TOOL' (was pinned to: $PINNED_VALUE)..."

  # Remove specific cycle from pinned_versions object
  TMP_FILE=$(mktemp)
  jq --arg cycle "$VERSION_CYCLE" 'del(.pinned_versions[$cycle]) | if .pinned_versions == {} then del(.pinned_versions) else . end' "$CATALOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CATALOG_FILE"

  echo "✓ Removed pin for '$TOOL'"
else
  # Check if pinned
  PINNED_VERSION="$(jq -r '.pinned_version // empty' "$CATALOG_FILE")"
  if [ -z "$PINNED_VERSION" ]; then
    echo "Tool '$TOOL' is not pinned" >&2
    exit 0
  fi

  echo "Removing version pin for '$TOOL' (was pinned to $PINNED_VERSION)..."

  # Remove pinned_version field from catalog
  TMP_FILE=$(mktemp)
  jq 'del(.pinned_version)' "$CATALOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CATALOG_FILE"

  echo "✓ Removed pin for '$TOOL'"
fi

echo ""
echo "This tool will now appear in upgrade prompts when updates are available."
