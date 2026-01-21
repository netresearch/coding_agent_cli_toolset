#!/usr/bin/env bash
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

TOOL="go"

# Support version-specific installation via GO_VERSION env var
# e.g., GO_VERSION=1.24 installs go1.24 alongside existing go
TARGET_CYCLE="${GO_VERSION:-}"

# Determine binary name and version check
if [ -n "$TARGET_CYCLE" ]; then
  BINARY="go${TARGET_CYCLE}"
  DISPLAY_NAME="go@${TARGET_CYCLE}"
else
  BINARY="go"
  DISPLAY_NAME="go"
fi

# Get current version of the specific binary
get_go_version() {
  local bin="$1"
  if have "$bin"; then
    "$bin" version 2>/dev/null | head -1 || true
  fi
}

before="$(get_go_version "$BINARY")"

# Version-specific Go installation (e.g., go1.24 alongside go1.25)
if [ -n "$TARGET_CYCLE" ]; then
  if ! have go; then
    echo "Error: Base Go installation required for multi-version support" >&2
    echo "Install base Go first, then specific versions" >&2
    exit 1
  fi

  # golang.org/dl uses full version names (go1.24.12, not go1.24)
  # Look up the latest patch version for this major.minor cycle
  FULL_VERSION=""
  if [[ "$TARGET_CYCLE" =~ ^[0-9]+\.[0-9]+$ ]]; then
    # It's just major.minor, need to find latest patch
    echo "Looking up latest Go ${TARGET_CYCLE}.x version..."
    FULL_VERSION=$(curl -s "https://go.dev/dl/?mode=json" 2>/dev/null | \
      grep -oE "go${TARGET_CYCLE}\.[0-9]+" | head -1 | sed 's/go//' || true)
  elif [[ "$TARGET_CYCLE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # It's already a full version
    FULL_VERSION="$TARGET_CYCLE"
  fi

  if [ -z "$FULL_VERSION" ]; then
    echo "Error: Could not determine full version for Go ${TARGET_CYCLE}" >&2
    echo "Available versions: https://go.dev/dl/" >&2
    exit 1
  fi

  # The binary will be named go1.24.12 (full version)
  FULL_BINARY="go${FULL_VERSION}"

  echo "Installing ${FULL_BINARY} via go install golang.org/dl/${FULL_BINARY}@latest..."
  if go install "golang.org/dl/${FULL_BINARY}@latest"; then
    # The go1.XX.YY command needs to download its SDK on first run
    if have "$FULL_BINARY"; then
      echo "Downloading Go ${FULL_VERSION} SDK..."
      "$FULL_BINARY" download || true

      # Create symlink from go1.24 -> go1.24.12 for convenience
      GOBIN="$(go env GOPATH)/bin"
      if [ -x "$GOBIN/$FULL_BINARY" ] && [ ! -e "$GOBIN/$BINARY" ]; then
        ln -sf "$FULL_BINARY" "$GOBIN/$BINARY" 2>/dev/null || true
        echo "Created symlink: $BINARY -> $FULL_BINARY"
      fi
    fi
  else
    echo "Failed to install ${FULL_BINARY}" >&2
  fi

# Standard single-version Go installation
elif have brew; then
  # Use homebrew for installation/upgrade
  if have go; then brew upgrade go || brew install go || true; else brew install go || true; fi
else
  # Manual installation from official Go downloads
  # Determine OS and architecture
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) GOARCH="amd64" ;;
    aarch64|arm64) GOARCH="arm64" ;;
    armv6*) GOARCH="armv6l" ;;
    *) GOARCH="amd64" ;;
  esac

  # Get latest version from Go download page
  TMP="$(mktemp -d)"
  VERSION_URL="https://go.dev/VERSION?m=text"
  if curl -fsSL "$VERSION_URL" -o "$TMP/version.txt" 2>/dev/null; then
    # VERSION file contains lines like "go1.25.2" - take first line
    TARGET_VERSION="$(head -n1 "$TMP/version.txt" | tr -d '\n\r')"
    if [ -n "$TARGET_VERSION" ]; then
      # Download archive
      ARCHIVE="${TARGET_VERSION}.${OS}-${GOARCH}.tar.gz"
      DOWNLOAD_URL="https://go.dev/dl/${ARCHIVE}"

      echo "Downloading ${ARCHIVE}..."
      if curl -fsSL "$DOWNLOAD_URL" -o "$TMP/${ARCHIVE}"; then
        # Remove existing installation
        if [ -d "/usr/local/go" ]; then
          echo "Removing existing /usr/local/go..."
          sudo rm -rf /usr/local/go
        fi

        # Extract new version
        echo "Extracting to /usr/local/go..."
        sudo tar -C /usr/local -xzf "$TMP/${ARCHIVE}"

        # Ensure /usr/local/go/bin is in PATH
        if [ ! -f "/usr/local/bin/go" ]; then
          sudo ln -sf /usr/local/go/bin/go /usr/local/bin/go 2>/dev/null || true
          sudo ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt 2>/dev/null || true
        fi
      else
        echo "Failed to download ${DOWNLOAD_URL}"
        echo "Please install Go manually from https://go.dev/dl/"
      fi
    else
      echo "Failed to determine latest Go version"
      echo "Please install Go from https://go.dev/dl/"
    fi
  else
    echo "Failed to fetch Go version information"
    echo "Please install Go from https://go.dev/dl/"
  fi
  rm -rf "$TMP" 2>/dev/null || true
fi

after="$(get_go_version "$BINARY")"
path="$(command -v "$BINARY" 2>/dev/null || true)"
printf "[%s] before: %s\n" "$DISPLAY_NAME" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$DISPLAY_NAME" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$DISPLAY_NAME" "$path"; fi


