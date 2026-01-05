#!/usr/bin/env bash
# set_auto_update.sh - Enable/disable automatic updates for a tool
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

TOOL="${1:-}"
VALUE="${2:-true}"  # true or false

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME [true|false]" >&2
  echo "" >&2
  echo "Enable or disable automatic updates for a tool." >&2
  echo "When enabled, 'make upgrade' will update the tool without asking." >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 prettier         # Enable auto-update for prettier" >&2
  echo "  $0 prettier true    # Enable auto-update for prettier" >&2
  echo "  $0 prettier false   # Disable auto-update for prettier" >&2
  exit 1
fi

CATALOG_FILE="$ROOT/catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Tool '$TOOL' not found in catalog" >&2
  exit 1
fi

# Normalize value
case "$VALUE" in
  true|1|yes|on) VALUE="true" ;;
  false|0|no|off) VALUE="false" ;;
  *)
    echo "Error: Invalid value '$VALUE'. Use 'true' or 'false'" >&2
    exit 1
    ;;
esac

if [ "$VALUE" = "true" ]; then
  echo "Enabling automatic updates for '$TOOL'..."
  TMP_FILE=$(mktemp)
  jq '. + {auto_update: true}' "$CATALOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CATALOG_FILE"
  echo "✓ Auto-update enabled for '$TOOL'"
  echo ""
  echo "This tool will be automatically updated during 'make upgrade' without prompting."
  echo "To disable: $0 $TOOL false"
else
  echo "Disabling automatic updates for '$TOOL'..."
  TMP_FILE=$(mktemp)
  jq 'del(.auto_update)' "$CATALOG_FILE" > "$TMP_FILE"
  mv "$TMP_FILE" "$CATALOG_FILE"
  echo "✓ Auto-update disabled for '$TOOL'"
  echo ""
  echo "You will be prompted before updating this tool."
fi
