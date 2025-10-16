#!/usr/bin/env bash
# Generic installer for GitHub release binaries
# Reads tool metadata from catalog and installs binary
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
VERSION_URL="$(jq -r '.version_url // empty' "$CATALOG_FILE")"
DOWNLOAD_URL_TEMPLATE="$(jq -r '.download_url_template' "$CATALOG_FILE")"
FALLBACK_URL_TEMPLATE="$(jq -r '.fallback_url_template // empty' "$CATALOG_FILE")"
GITHUB_REPO="$(jq -r '.github_repo // empty' "$CATALOG_FILE")"

# Get current version (try multiple version command formats)
before="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && \
  ("$BINARY_NAME" --version 2>/dev/null || \
   "$BINARY_NAME" version --client 2>/dev/null | head -1 || \
   "$BINARY_NAME" version 2>/dev/null | head -1 || true))"

# Detect OS and architecture
OS="linux"
ARCH_RAW="$(uname -m)"
ARCH="$ARCH_RAW"

# Apply architecture mapping if present
if jq -e ".arch_map.\"$ARCH_RAW\"" "$CATALOG_FILE" >/dev/null 2>&1; then
  ARCH="$(jq -r ".arch_map.\"$ARCH_RAW\"" "$CATALOG_FILE")"
fi

# Determine installation directory
BIN_DIR="$(get_install_dir "$BINARY_NAME")"
get_install_cmd "$BIN_DIR"
mkdir -p "$BIN_DIR" 2>/dev/null || true

# Resolve latest version
LATEST=""
if [ -n "$VERSION_URL" ]; then
  LATEST="$(curl -fsSL "$VERSION_URL" 2>/dev/null || true)"
fi

# Fallback to GitHub releases if no version URL
if [ -z "$LATEST" ] && [ -n "$GITHUB_REPO" ]; then
  LATEST="$(curl -fsSIL -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' \
    "https://github.com/$GITHUB_REPO/releases/latest" 2>/dev/null | awk -F'/' '{print $NF}')"
fi

if [ -z "$LATEST" ]; then
  echo "[$TOOL] Error: Unable to resolve latest version" >&2
  echo "[$TOOL] before: ${before:-<none>}" >&2
  exit 1
fi

# Build download URL
DOWNLOAD_URL="${DOWNLOAD_URL_TEMPLATE//\{version\}/$LATEST}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{os\}/$OS}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{arch\}/$ARCH}"

# Download with retry and fallback
tmpfile="/tmp/$BINARY_NAME.$$"
rm -f "$tmpfile"

if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 -o "$tmpfile" "$DOWNLOAD_URL" 2>/dev/null; then
  if [ -n "$FALLBACK_URL_TEMPLATE" ]; then
    FALLBACK_URL="${FALLBACK_URL_TEMPLATE//\{version\}/$LATEST}"
    FALLBACK_URL="${FALLBACK_URL//\{os\}/$OS}"
    FALLBACK_URL="${FALLBACK_URL//\{arch\}/$ARCH}"
    curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 -o "$tmpfile" "$FALLBACK_URL"
  else
    echo "[$TOOL] Error: Download failed" >&2
    exit 1
  fi
fi

# Validate download
if ! [ -s "$tmpfile" ]; then
  echo "[$TOOL] Error: Downloaded file is empty" >&2
  rm -f "$tmpfile"
  exit 1
fi

# Clean up alternative installations (cargo, apt, brew) before installing
if [ -f "$HOME/.cargo/bin/$BINARY_NAME" ]; then
  echo "[$TOOL] Removing cargo-installed version at ~/.cargo/bin/$BINARY_NAME" >&2
  rm -f "$HOME/.cargo/bin/$BINARY_NAME"
fi

# Check if apt-installed and suggest removal
if command -v dpkg >/dev/null 2>&1 && dpkg -S "/usr/bin/$BINARY_NAME" >/dev/null 2>&1; then
  PKG="$(dpkg -S "/usr/bin/$BINARY_NAME" | cut -d: -f1)"
  echo "[$TOOL] Note: apt-installed version found in package '$PKG'" >&2
  echo "[$TOOL] Removing apt package to prevent conflicts..." >&2
  apt_remove_if_present "$PKG" || true
fi

# Install
chmod +x "$tmpfile"
$INSTALL -T "$tmpfile" "$BIN_DIR/$BINARY_NAME"
rm -f "$tmpfile"

# Report
after="$(command -v "$BINARY_NAME" >/dev/null 2>&1 && \
  ("$BINARY_NAME" --version 2>/dev/null || \
   "$BINARY_NAME" version --client 2>/dev/null | head -1 || \
   "$BINARY_NAME" version 2>/dev/null | head -1 || true))"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi
