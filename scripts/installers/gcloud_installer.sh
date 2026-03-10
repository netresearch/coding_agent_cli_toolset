#!/usr/bin/env bash
# Google Cloud CLI installer
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

TOOL="${1:-gcloud}"
CATALOG_FILE="$DIR/../catalog/$TOOL.json"

if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

BINARY_NAME="$(jq -r '.binary_name' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"
GCLOUD_SDK="$HOME/google-cloud-sdk"
GCLOUD_BIN="$GCLOUD_SDK/bin"

# Ensure SDK bin is in PATH for detection and post-install
if [ -d "$GCLOUD_BIN" ]; then
  export PATH="$GCLOUD_BIN:$PATH"
fi

# Version detection helper
get_gcloud_version() {
  if [ -n "$VERSION_COMMAND" ]; then
    timeout 5 bash -c "$VERSION_COMMAND" 2>/dev/null || true
  elif command -v "$BINARY_NAME" >/dev/null 2>&1; then
    "$BINARY_NAME" version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true
  fi
}

# Get current version
before="$(get_gcloud_version)"

if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  # Already installed - use built-in update (quiet)
  "$BINARY_NAME" components update --quiet 2>&1 | tail -1
elif [ -d "$GCLOUD_SDK" ]; then
  # SDK directory exists but gcloud not functional - try to recover
  if [ -x "$GCLOUD_BIN/$BINARY_NAME" ]; then
    "$GCLOUD_BIN/$BINARY_NAME" components update --quiet 2>&1 | tail -1
  else
    echo "[$TOOL] Error: $GCLOUD_SDK exists but gcloud not found in $GCLOUD_BIN" >&2
    echo "[$TOOL] Remove $GCLOUD_SDK and re-run to reinstall" >&2
    exit 1
  fi
else
  # Fresh install via Google Cloud SDK installer (quiet)
  TMP="$(mktemp -d)"
  INSTALLER_URL="https://dl.google.com/dl/cloudsdk/channels/rapid/google-cloud-sdk.tar.gz"
  echo "[$TOOL] Downloading Google Cloud SDK..."
  curl -fsSL "$INSTALLER_URL" -o "$TMP/google-cloud-sdk.tar.gz"
  tar -xzf "$TMP/google-cloud-sdk.tar.gz" -C "$HOME"
  rm -rf "$TMP"

  # Run install script quietly (no prompts, no PATH modification, no usage reporting)
  "$GCLOUD_SDK/install.sh" --quiet --usage-reporting false --command-completion false --path-update false 2>&1 | tail -1

  export PATH="$GCLOUD_BIN:$PATH"
fi

# Symlink gcloud (and gsutil, bq) into user bin so it's in PATH without SDK-specific setup
BIN_DIR="$(get_install_dir "$BINARY_NAME")"
mkdir -p "$BIN_DIR" 2>/dev/null || true
for cmd in gcloud gsutil bq; do
  if [ -x "$GCLOUD_BIN/$cmd" ]; then
    ln -sf "$GCLOUD_BIN/$cmd" "$BIN_DIR/$cmd"
  fi
done

# Report
after="$(get_gcloud_version)"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
