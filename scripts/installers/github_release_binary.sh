#!/usr/bin/env bash
# Generic installer for GitHub release binaries
# Reads tool metadata from catalog and installs binary
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

# Cleanup temp files on interrupt
_grb_cleanup() {
  rm -f "/tmp/${BINARY_NAME:-tool}.$$" 2>/dev/null || true
  rm -rf "/tmp/${BINARY_NAME:-tool}-extract.$$" 2>/dev/null || true
}
trap '_grb_cleanup; exit 130' INT TERM

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

# Validate tool name to prevent path traversal
if [[ "$TOOL" == *"/"* ]] || [[ "$TOOL" == *".."* ]]; then
  echo "Error: Invalid tool name: $TOOL" >&2
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
PRESERVE_DIR="$(jq -r '.preserve_directory // empty' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // empty' "$CATALOG_FILE")"
VERSION_FLAG="$(jq -r '.version_flag // empty' "$CATALOG_FILE")"

# Get current version
before=""
if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  if [ -n "$VERSION_COMMAND" ]; then
    # Use catalog-specified shell command
    before="$(timeout 2 bash -c "$VERSION_COMMAND" 2>/dev/null || true)"
  elif [ -n "$VERSION_FLAG" ]; then
    # Use catalog-specified version flag/subcommand
    before="$(timeout 2 "$BINARY_NAME" $VERSION_FLAG </dev/null 2>/dev/null | head -1 || true)"
  else
    # Fallback: try multiple version command formats
    before="$(timeout 2 "$BINARY_NAME" --version </dev/null 2>/dev/null || \
             timeout 2 "$BINARY_NAME" version --client </dev/null 2>/dev/null | head -1 || \
             timeout 2 "$BINARY_NAME" version </dev/null 2>/dev/null | head -1 || true)"
  fi
fi

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

# Try GitLab project if available
GITLAB_PROJECT="$(jq -r '.gitlab_project // empty' "$CATALOG_FILE")"
if [ -z "$LATEST" ] && [ -n "$GITLAB_PROJECT" ]; then
  ENCODED_PROJECT="${GITLAB_PROJECT//\//%2F}"
  LATEST="$(curl -fsSL "https://gitlab.com/api/v4/projects/${ENCODED_PROJECT}/releases?per_page=1" 2>/dev/null | \
    jq -r '.[0].tag_name // empty' 2>/dev/null || true)"
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

# Normalize version: strip tool name prefix if present
# Some projects tag releases as "toolname-version" (e.g., jq-1.8.1)
# but their download URLs expect just the version number
# Example: jq tags as "jq-1.8.1" but URL is "...jq-{version}/..." where version=1.8.1
if [[ "$LATEST" == "${BINARY_NAME}-"* ]]; then
  LATEST="${LATEST#${BINARY_NAME}-}"
fi

# Build download URL
# Support {version_nov} for version without 'v' prefix
# Support {arch_suffix} for tools like ninja that use empty suffix for x86_64
LATEST_NOV="${LATEST#v}"
DOWNLOAD_URL="${DOWNLOAD_URL_TEMPLATE//\{version\}/$LATEST}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{version_nov\}/$LATEST_NOV}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{os\}/$OS}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{arch\}/$ARCH}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{arch_suffix\}/$ARCH}"

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

# Extract if archive, otherwise use directly
BINARY_PATH="$tmpfile"
EXTRACT_DIR=""

if [[ "$DOWNLOAD_URL" == *.tar.gz ]] || [[ "$DOWNLOAD_URL" == *.tgz ]]; then
  # Extract tar.gz
  EXTRACT_DIR="/tmp/${BINARY_NAME}-extract.$$"
  mkdir -p "$EXTRACT_DIR"

  if ! tar -xzf "$tmpfile" -C "$EXTRACT_DIR" 2>/dev/null; then
    echo "[$TOOL] Error: Failed to extract tar.gz archive" >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  # Find the binary in extracted files
  BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" -executable 2>/dev/null | head -1)"

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    # Try without executable check (some archives don't preserve execute bit)
    BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" 2>/dev/null | head -1)"
  fi

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    echo "[$TOOL] Error: Binary '$BINARY_NAME' not found in archive" >&2
    echo "[$TOOL] Archive contents:" >&2
    find "$EXTRACT_DIR" -type f 2>/dev/null | head -10 >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  rm -f "$tmpfile"
elif [[ "$DOWNLOAD_URL" == *.tar.xz ]]; then
  # Extract tar.xz
  EXTRACT_DIR="/tmp/${BINARY_NAME}-extract.$$"
  mkdir -p "$EXTRACT_DIR"

  if ! tar -xJf "$tmpfile" -C "$EXTRACT_DIR" 2>/dev/null; then
    echo "[$TOOL] Error: Failed to extract tar.xz archive" >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  # Find the binary in extracted files
  BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" -executable 2>/dev/null | head -1)"

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    # Try without executable check (some archives don't preserve execute bit)
    BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" 2>/dev/null | head -1)"
  fi

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    echo "[$TOOL] Error: Binary '$BINARY_NAME' not found in archive" >&2
    echo "[$TOOL] Archive contents:" >&2
    find "$EXTRACT_DIR" -type f 2>/dev/null | head -10 >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  rm -f "$tmpfile"
elif [[ "$DOWNLOAD_URL" == *.zip ]]; then
  # Extract zip
  EXTRACT_DIR="/tmp/${BINARY_NAME}-extract.$$"
  mkdir -p "$EXTRACT_DIR"

  if ! unzip -q "$tmpfile" -d "$EXTRACT_DIR" 2>/dev/null; then
    echo "[$TOOL] Error: Failed to extract zip archive" >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  # Find the binary in extracted files
  BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" -executable 2>/dev/null | head -1)"

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    BINARY_PATH="$(find "$EXTRACT_DIR" -type f -name "$BINARY_NAME" 2>/dev/null | head -1)"
  fi

  if [ -z "$BINARY_PATH" ] || [ ! -f "$BINARY_PATH" ]; then
    echo "[$TOOL] Error: Binary '$BINARY_NAME' not found in archive" >&2
    echo "[$TOOL] Archive contents:" >&2
    find "$EXTRACT_DIR" -type f 2>/dev/null | head -10 >&2
    rm -rf "$tmpfile" "$EXTRACT_DIR"
    exit 1
  fi

  rm -f "$tmpfile"
fi

# Note: We intentionally do NOT remove existing installations from apt/brew/cargo
# The new version in ~/.local/bin will take precedence via PATH ordering
# This allows:
# - No sudo password prompts
# - No disruption to package manager state
# - Clean fallback if ~/.local/bin version is removed
# - System packages can still satisfy dependencies for other tools

# Check if binary is already at target version by comparing SHA256 hashes
# This catches cases where upstream version string is wrong (e.g., sd v1.1.0 reports 1.0.0)
BINARY_ALREADY_CURRENT=""
if [ -f "$BIN_DIR/$BINARY_NAME" ] && [ -f "$BINARY_PATH" ]; then
  OLD_HASH="$(sha256sum "$BIN_DIR/$BINARY_NAME" 2>/dev/null | awk '{print $1}')"
  NEW_HASH="$(sha256sum "$BINARY_PATH" 2>/dev/null | awk '{print $1}')"
  if [ -n "$OLD_HASH" ] && [ -n "$NEW_HASH" ] && [ "$OLD_HASH" = "$NEW_HASH" ]; then
    BINARY_ALREADY_CURRENT="true"
  fi
fi

# Install
if [ -n "$PRESERVE_DIR" ] && [ -n "$EXTRACT_DIR" ]; then
  # Tool requires full directory structure (e.g., GAM with bundled Python)
  LIB_DIR="$(dirname "$BIN_DIR")/lib"
  mkdir -p "$LIB_DIR"

  # Remove old installation
  rm -rf "$LIB_DIR/$PRESERVE_DIR"

  # Move entire directory to ~/.local/lib
  mv "$EXTRACT_DIR/$PRESERVE_DIR" "$LIB_DIR/"

  # Create symlink in bin directory
  ln -sf "$LIB_DIR/$PRESERVE_DIR/$BINARY_NAME" "$BIN_DIR/$BINARY_NAME"
else
  # Standard binary installation
  chmod +x "$BINARY_PATH"
  $INSTALL -T "$BINARY_PATH" "$BIN_DIR/$BINARY_NAME"
fi

# Cleanup
rm -f "$tmpfile"
if [ -n "$EXTRACT_DIR" ] && [ -d "$EXTRACT_DIR" ]; then
  rm -rf "$EXTRACT_DIR"
fi

# Report
after=""
if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  if [ -n "$VERSION_COMMAND" ]; then
    after="$(timeout 2 bash -c "$VERSION_COMMAND" 2>/dev/null || true)"
  elif [ -n "$VERSION_FLAG" ]; then
    after="$(timeout 2 "$BINARY_NAME" $VERSION_FLAG </dev/null 2>/dev/null | head -1 || true)"
  else
    after="$(timeout 2 "$BINARY_NAME" --version </dev/null 2>/dev/null || \
             timeout 2 "$BINARY_NAME" version --client </dev/null 2>/dev/null | head -1 || \
             timeout 2 "$BINARY_NAME" version </dev/null 2>/dev/null | head -1 || true)"
  fi
fi
# Normalize verbose version output
before="$(normalize_version_output "${before:-}")"
after="$(normalize_version_output "${after:-}")"
path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi
if [ "$BINARY_ALREADY_CURRENT" = "true" ]; then
  printf "[%s] note:   binary already matches target release %s (upstream version string may be stale)\n" "$TOOL" "$LATEST"
  # Signal already-current status to callers (e.g., guide.sh)
  mkdir -p /tmp/.cli-audit
  echo "$LATEST" > "/tmp/.cli-audit/${TOOL}.already-current"
fi

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
