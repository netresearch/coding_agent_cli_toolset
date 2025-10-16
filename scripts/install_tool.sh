#!/usr/bin/env bash
# Main orchestrator for tool installation
# Reads catalog and delegates to appropriate installer
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"

# Check if tool has catalog entry
if [ ! -f "$CATALOG_FILE" ]; then
  echo "[$TOOL] Error: No catalog entry found" >&2
  echo "[$TOOL] Available tools: $(find "$DIR/../catalog" -name '*.json' -exec basename {} .json \; | tr '\n' ' ')" >&2
  exit 1
fi

# Check if jq is available
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not found" >&2
  exit 1
fi

# Read install method from catalog
INSTALL_METHOD="$(jq -r '.install_method' "$CATALOG_FILE")"

if [ -z "$INSTALL_METHOD" ] || [ "$INSTALL_METHOD" = "null" ]; then
  echo "[$TOOL] Error: No install_method specified in catalog" >&2
  exit 1
fi

# Delegate to appropriate installer
INSTALLER_SCRIPT="$DIR/installers/${INSTALL_METHOD}.sh"

if [ ! -f "$INSTALLER_SCRIPT" ]; then
  echo "[$TOOL] Error: Installer not found: $INSTALLER_SCRIPT" >&2
  echo "[$TOOL] install_method: $INSTALL_METHOD" >&2
  exit 1
fi

if [ ! -x "$INSTALLER_SCRIPT" ]; then
  echo "[$TOOL] Error: Installer not executable: $INSTALLER_SCRIPT" >&2
  exit 1
fi

# Execute installer with all remaining arguments
shift  # Remove TOOL from $@
exec "$INSTALLER_SCRIPT" "$TOOL" "$@"
