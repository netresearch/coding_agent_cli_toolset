#!/usr/bin/env bash
# Installer for Docker CLI plugins (e.g., compose, buildx)
# Installs plugins to ~/.docker/cli-plugins/
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

# Parse catalog
BINARY_NAME="$(jq -r '.binary_name' "$CATALOG_FILE")"
GITHUB_REPO="$(jq -r '.github_repo // empty' "$CATALOG_FILE")"
PLUGIN_NAME="$(jq -r '.plugin_name // .name' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"

# Docker CLI plugins go to ~/.docker/cli-plugins/
PLUGIN_DIR="$HOME/.docker/cli-plugins"
mkdir -p "$PLUGIN_DIR"

# Get current version
before=""
if [ -n "$VERSION_COMMAND" ]; then
  before="$(eval "$VERSION_COMMAND" 2>/dev/null || true)"
elif [ -f "$PLUGIN_DIR/docker-$PLUGIN_NAME" ]; then
  before="$(docker $PLUGIN_NAME version 2>/dev/null | head -1 || true)"
fi

# Detect OS and architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH_RAW="$(uname -m)"

# Map architecture to Docker's naming convention
case "$ARCH_RAW" in
  x86_64)  ARCH="x86_64" ;;
  aarch64) ARCH="aarch64" ;;
  arm64)   ARCH="aarch64" ;;
  armv7l)  ARCH="armv7" ;;
  armv6l)  ARCH="armv6" ;;
  *)       ARCH="$ARCH_RAW" ;;
esac

# Resolve latest version from GitHub
LATEST=""
if [ -n "$GITHUB_REPO" ]; then
  LATEST="$(curl -fsSIL -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' \
    "https://github.com/$GITHUB_REPO/releases/latest" 2>/dev/null | awk -F'/' '{print $NF}')"
fi

if [ -z "$LATEST" ]; then
  echo "[$TOOL] Error: Unable to resolve latest version" >&2
  echo "[$TOOL] before: ${before:-<none>}" >&2
  exit 1
fi

# Build download URL
# Docker Compose uses: docker-compose-{os}-{arch}
DOWNLOAD_URL="https://github.com/$GITHUB_REPO/releases/download/$LATEST/docker-$PLUGIN_NAME-$OS-$ARCH"

# Download
tmpfile="/tmp/docker-$PLUGIN_NAME.$$"
rm -f "$tmpfile"

echo "[$TOOL] Downloading $DOWNLOAD_URL"
if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 -o "$tmpfile" "$DOWNLOAD_URL" 2>/dev/null; then
  echo "[$TOOL] Error: Download failed from $DOWNLOAD_URL" >&2
  rm -f "$tmpfile"
  exit 1
fi

# Validate download
if ! [ -s "$tmpfile" ]; then
  echo "[$TOOL] Error: Downloaded file is empty" >&2
  rm -f "$tmpfile"
  exit 1
fi

# Install to Docker CLI plugins directory
chmod +x "$tmpfile"
mv "$tmpfile" "$PLUGIN_DIR/docker-$PLUGIN_NAME"

# Report
after=""
if [ -n "$VERSION_COMMAND" ]; then
  after="$(eval "$VERSION_COMMAND" 2>/dev/null || true)"
else
  after="$(docker $PLUGIN_NAME version 2>/dev/null | head -1 || true)"
fi

printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
printf "[%s] path:   %s\n" "$TOOL" "$PLUGIN_DIR/docker-$PLUGIN_NAME"

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
