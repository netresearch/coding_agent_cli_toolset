#!/usr/bin/env bash
# pin_version.sh - Pin a tool to a specific version to suppress upgrade prompts
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

TOOL="${1:-}"
VERSION="${2:-}"

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME [VERSION]" >&2
  echo "" >&2
  echo "Pin a tool to a specific version to suppress upgrade prompts." >&2
  echo "If VERSION is omitted, uses the currently installed version." >&2
  exit 1
fi

CATALOG_FILE="$ROOT/catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Tool '$TOOL' not found in catalog" >&2
  exit 1
fi

# If no version provided, get current installed version
if [ -z "$VERSION" ]; then
  # Try to get version from tool
  BINARY_NAME="$(jq -r '.binary_name // .name' "$CATALOG_FILE")"

  if command -v "$BINARY_NAME" >/dev/null 2>&1; then
    # Try various version command formats
    VERSION="$(timeout 2 "$BINARY_NAME" --version </dev/null 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1 || true)"

    if [ -z "$VERSION" ]; then
      echo "Error: Could not detect current version for '$TOOL'" >&2
      echo "Please specify version explicitly: $0 $TOOL VERSION" >&2
      exit 1
    fi
  else
    echo "Error: '$BINARY_NAME' not installed, cannot detect version" >&2
    echo "Please specify version explicitly: $0 $TOOL VERSION" >&2
    exit 1
  fi
fi

echo "Pinning '$TOOL' to version $VERSION..."

# Update catalog with pinned_version field
TMP_FILE=$(mktemp)
jq --arg version "$VERSION" '. + {pinned_version: $version}' "$CATALOG_FILE" > "$TMP_FILE"
mv "$TMP_FILE" "$CATALOG_FILE"

echo "✓ Pinned '$TOOL' to version $VERSION"
echo ""
echo "This tool will no longer appear in upgrade prompts unless:"
echo "  - A version newer than $VERSION is available AND"
echo "  - You remove the pin with: ./scripts/unpin_version.sh $TOOL"
