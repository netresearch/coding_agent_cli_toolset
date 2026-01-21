#!/usr/bin/env bash
# reset_pins.sh - Remove all version pins from all tools
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

echo "Resetting all version pins..."

count=0
for catalog_file in "$ROOT"/catalog/*.json; do
  [ -f "$catalog_file" ] || continue
  tool_name="$(basename "$catalog_file" .json)"

  # Check for pinned_version
  pinned="$(jq -r '.pinned_version // empty' "$catalog_file")"
  if [ -n "$pinned" ]; then
    echo "  Removing pin from $tool_name (was: $pinned)"
    TMP_FILE=$(mktemp)
    jq 'del(.pinned_version)' "$catalog_file" > "$TMP_FILE"
    mv "$TMP_FILE" "$catalog_file"
    ((count++)) || true
  fi

  # Check for pinned_versions (multi-version pins)
  has_pinned_versions="$(jq -r 'if .pinned_versions then "yes" else empty end' "$catalog_file")"
  if [ -n "$has_pinned_versions" ]; then
    versions="$(jq -r '.pinned_versions | keys | join(", ")' "$catalog_file")"
    echo "  Removing multi-version pins from $tool_name (cycles: $versions)"
    TMP_FILE=$(mktemp)
    jq 'del(.pinned_versions)' "$catalog_file" > "$TMP_FILE"
    mv "$TMP_FILE" "$catalog_file"
    ((count++)) || true
  fi
done

if [ $count -eq 0 ]; then
  echo "No pins found."
else
  echo ""
  echo "✓ Reset $count tool(s)"
  echo ""
  echo "All tools will now appear in upgrade prompts."
fi
