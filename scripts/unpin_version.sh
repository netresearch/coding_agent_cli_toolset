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
  exit 1
fi

CATALOG_FILE="$ROOT/catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Tool '$TOOL' not found in catalog" >&2
  exit 1
fi

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
echo ""
echo "This tool will now appear in upgrade prompts when updates are available."
