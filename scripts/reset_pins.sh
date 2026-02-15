#!/usr/bin/env bash
# reset_pins.sh - Remove all version pins from all tools
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load pin library
. "$DIR/lib/pins.sh"

echo "Resetting all version pins..."

# Show what's being removed
if [ -f "$PINS_FILE" ]; then
  current="$(jq -r 'to_entries[] | if (.value | type) == "object" then "\(.key): \(.value | to_entries | map("\(.key)=\(.value)") | join(", "))" else "\(.key): \(.value)" end' "$PINS_FILE" 2>/dev/null)"
  if [ -n "$current" ]; then
    while IFS= read -r line; do
      echo "  Removing pin: $line"
    done <<< "$current"
    echo ""
    pins_reset_all
    echo "✓ All pins removed"
  else
    echo "No pins found."
  fi
else
  echo "No pins found."
fi

echo ""
echo "All tools will now appear in upgrade prompts."
