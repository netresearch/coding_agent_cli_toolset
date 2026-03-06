#!/usr/bin/env bash
# Google Cloud CLI installer
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="${1:-gcloud}"
CATALOG_FILE="$DIR/../catalog/$TOOL.json"

if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

BINARY_NAME="$(jq -r '.binary_name' "$CATALOG_FILE")"

# Get current version
before="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && "$BINARY_NAME" version 2>/dev/null | head -1 || true)"

if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  # Already installed - use built-in update
  "$BINARY_NAME" components update --quiet 2>&1 || true
else
  # Fresh install via Google Cloud SDK installer
  TMP="$(mktemp -d)"
  cd "$TMP"
  curl -fsSL https://sdk.cloud.google.com -o install.sh
  bash install.sh --disable-prompts --install-dir="$HOME" 2>&1
  cd - >/dev/null
  rm -rf "$TMP"

  # Add to PATH if not already present
  GCLOUD_BIN="$HOME/google-cloud-sdk/bin"
  if [ -d "$GCLOUD_BIN" ] && ! command -v "$BINARY_NAME" >/dev/null 2>&1; then
    export PATH="$GCLOUD_BIN:$PATH"
  fi
fi

# Report
after="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && "$BINARY_NAME" version 2>/dev/null | head -1 || true)"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
