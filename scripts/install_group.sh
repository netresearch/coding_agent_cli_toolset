#!/usr/bin/env bash
set -euo pipefail

# Install tools by catalog tag
# Usage: install_group.sh TAG [install|update|uninstall]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

TAG="${1:-}"
ACTION="${2:-install}"

if [ -z "$TAG" ]; then
  echo "Usage: $0 TAG [install|update|uninstall]" >&2
  echo "" >&2
  echo "Available tags:" >&2
  # Extract all unique tags from catalog
  find "$DIR/../catalog" -name "*.json" -exec jq -r '.tags[]? // empty' {} \; 2>/dev/null | sort -u | sed 's/^/  - /'
  exit 1
fi

# Check if jq is available
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not found" >&2
  exit 1
fi

# Find all tools with the specified tag
TOOLS=()
for json in "$DIR"/../catalog/*.json; do
  if [ -f "$json" ]; then
    # Check if this tool has the tag
    if jq -e --arg tag "$TAG" '.tags[]? | select(. == $tag)' "$json" >/dev/null 2>&1; then
      tool_name="$(jq -r '.name' "$json")"
      TOOLS+=("$tool_name")
    fi
  fi
done

if [ ${#TOOLS[@]} -eq 0 ]; then
  echo "No tools found with tag: $TAG" >&2
  exit 1
fi

echo "[$TAG] Found ${#TOOLS[@]} tools: ${TOOLS[*]}"

# Install/update/uninstall each tool
for tool in "${TOOLS[@]}"; do
  case "$ACTION" in
    install|reconcile)
      "$DIR/install_tool.sh" "$tool"
      ;;
    update)
      "$DIR/install_tool.sh" "$tool"
      ;;
    uninstall)
      # For uninstall, we'd need to implement uninstall support in installers
      echo "[$tool] Uninstall not yet implemented" >&2
      ;;
    *)
      echo "Unknown action: $ACTION" >&2
      exit 2
      ;;
  esac
done

echo "[$TAG] Completed $ACTION for ${#TOOLS[@]} tools"
