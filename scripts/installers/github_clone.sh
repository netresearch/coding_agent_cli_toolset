#!/usr/bin/env bash
# Generic installer for GitHub repository clones
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME [ACTION]" >&2
  exit 1
fi

ACTION="${2:-install}"

CATALOG_FILE="$DIR/../catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "[$TOOL] Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

# Parse catalog
GITHUB_REPO="$(jq -r '.github_repo // ""' "$CATALOG_FILE")"
CLONE_PATH="$(jq -r '.clone_path // ""' "$CATALOG_FILE")"
BRANCH="$(jq -r '.branch // "master"' "$CATALOG_FILE")"

if [ -z "$GITHUB_REPO" ]; then
  echo "[$TOOL] Error: github_repo not specified in catalog" >&2
  exit 1
fi

if [ -z "$CLONE_PATH" ]; then
  echo "[$TOOL] Error: clone_path not specified in catalog" >&2
  exit 1
fi

# Expand tilde in clone path
CLONE_PATH="${CLONE_PATH/#\~/$HOME}"

# Ensure git is available
if ! command -v git >/dev/null 2>&1; then
  echo "[$TOOL] Error: git not found. Please install git first." >&2
  exit 1
fi

# Parse optional version detection settings
BINARY_NAME="$(jq -r '.binary_name // ""' "$CATALOG_FILE")"
VERSION_COMMAND="$(jq -r '.version_command // ""' "$CATALOG_FILE")"

# Helper: get version using best available method
get_version() {
  local clone_path="$1"
  local binary_name="$2"
  local version_cmd="$3"

  # Try binary --version first (if binary exists in PATH or clone_path/bin)
  if [ -n "$binary_name" ]; then
    local bin_path=""
    if command -v "$binary_name" >/dev/null 2>&1; then
      bin_path="$(command -v "$binary_name")"
    elif [ -x "$clone_path/bin/$binary_name" ]; then
      bin_path="$clone_path/bin/$binary_name"
    fi
    if [ -n "$bin_path" ]; then
      local ver="$("$bin_path" --version 2>/dev/null | head -1 | grep -oE '[0-9]+(\.[0-9]+)*' | head -1 || true)"
      if [ -n "$ver" ]; then
        echo "$ver"
        return
      fi
    fi
  fi

  # Try version_command from catalog
  if [ -n "$version_cmd" ]; then
    local ver="$(eval "$version_cmd" 2>/dev/null || true)"
    if [ -n "$ver" ]; then
      echo "$ver"
      return
    fi
  fi

  # Fall back to git short hash
  if [ -d "$clone_path/.git" ]; then
    (cd "$clone_path" && git rev-parse --short HEAD 2>/dev/null || echo "<unknown>")
  fi
}

# Get current version/commit if already cloned
before=""
if [ -d "$CLONE_PATH/.git" ]; then
  before="$(get_version "$CLONE_PATH" "$BINARY_NAME" "$VERSION_COMMAND")"
fi

# Clone or update
if [ ! -d "$CLONE_PATH" ]; then
  echo "[$TOOL] Cloning from https://github.com/$GITHUB_REPO" >&2
  mkdir -p "$(dirname "$CLONE_PATH")"
  git clone --depth=1 --branch="$BRANCH" "https://github.com/$GITHUB_REPO.git" "$CLONE_PATH" || {
    echo "[$TOOL] Error: git clone failed" >&2
    exit 1
  }
else
  echo "[$TOOL] Updating repository at $CLONE_PATH" >&2
  cd "$CLONE_PATH"
  git fetch origin "$BRANCH" --depth=1 || {
    echo "[$TOOL] Error: git fetch failed" >&2
    exit 1
  }
  git reset --hard "origin/$BRANCH" || {
    echo "[$TOOL] Error: git reset failed" >&2
    exit 1
  }
  cd - >/dev/null
fi

# Get new version/commit
after=""
if [ -d "$CLONE_PATH/.git" ]; then
  after="$(get_version "$CLONE_PATH" "$BINARY_NAME" "$VERSION_COMMAND")"
fi

# Report
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n" "$TOOL" "${after:-<unknown>}"
printf "[%s] path:   %s\n" "$TOOL" "$CLONE_PATH"

# Refresh snapshot after successful installation
refresh_snapshot "$TOOL"
