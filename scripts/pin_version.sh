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
  echo "" >&2
  echo "For multi-version tools (e.g., go@1.24, php@8.3):" >&2
  echo "  $0 go@1.24 never    # Never prompt for this version cycle" >&2
  echo "  $0 php@8.3 8.3.15   # Pin to specific patch version" >&2
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

# If no version provided, get current installed version or use "never" for multi-version
if [ -z "$VERSION" ]; then
  if [ -n "$IS_MULTI_VERSION" ]; then
    # For multi-version tools without explicit version, default to "never"
    VERSION="never"
  else
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
fi

# Handle multi-version tools differently
if [ -n "$IS_MULTI_VERSION" ]; then
  echo "Pinning '$TOOL' (version cycle $VERSION_CYCLE) to: $VERSION..."

  # Update catalog with pinned_versions object
  TMP_FILE=$(mktemp)
  jq --arg cycle "$VERSION_CYCLE" --arg version "$VERSION" \
    '.pinned_versions = ((.pinned_versions // {}) + {($cycle): $version})' \
    "$CATALOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CATALOG_FILE"

  echo "✓ Pinned '$TOOL' to: $VERSION"
  echo ""
  if [ "$VERSION" = "never" ]; then
    echo "This version cycle will never appear in upgrade prompts."
  else
    echo "This version cycle will no longer appear in upgrade prompts unless:"
    echo "  - A version newer than $VERSION is available"
  fi
  echo "To remove the pin: ./scripts/unpin_version.sh $TOOL"
else
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
fi
