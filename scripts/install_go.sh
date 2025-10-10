#!/usr/bin/env bash
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

TOOL="go"
before="$(have go && go version || true)"

if have brew; then
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

after="$(have go && go version || true)"
path="$(command -v go 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


