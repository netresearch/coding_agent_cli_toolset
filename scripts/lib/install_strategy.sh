#!/usr/bin/env bash
# Shared installation strategy logic for all install scripts

# Determine installation directory based on INSTALL_STRATEGY
# Usage: get_install_dir TOOL_NAME
# Returns: Directory path where tool should be installed
get_install_dir() {
  local tool_name="${1:-}"
  local strategy="${INSTALL_STRATEGY:-USER}"
  local prefix="${PREFIX:-$HOME/.local}"
  local bin_dir=""

  # Check for per-tool target_dir override from catalog
  if [ -n "$tool_name" ] && [ -n "${CATALOG_FILE:-}" ] && [ -f "${CATALOG_FILE:-}" ]; then
    local target_dir
    target_dir="$(jq -r '.target_dir // empty' "$CATALOG_FILE" 2>/dev/null || true)"
    if [ -n "$target_dir" ]; then
      case "$target_dir" in
        go_bin)
          # Go binary convention: update in place, fresh install to best-guess GOPATH/bin
          local current_path
          current_path="$(command -v "$tool_name" 2>/dev/null || true)"
          if [ -n "$current_path" ]; then
            # Already installed - keep it where it is
            echo "$(dirname "$current_path")"
          else
            # Fresh install - best-guess Go bin folder:
            # 1. GOPATH/bin if GOPATH is set
            # 2. `go env GOPATH`/bin if go is available
            # 3. ~/go/bin (Go's default GOPATH)
            if [ -n "${GOPATH:-}" ]; then
              echo "$GOPATH/bin"
            elif command -v go >/dev/null 2>&1; then
              echo "$(go env GOPATH 2>/dev/null)/bin"
            else
              echo "$HOME/go/bin"
            fi
          fi
          return
          ;;
        *)
          # Generic target_dir: expand ~ and $HOME
          target_dir="${target_dir/#\~/$HOME}"
          target_dir="${target_dir//\$\{HOME\}/$HOME}"
          target_dir="${target_dir//\$HOME/$HOME}"
          echo "$target_dir"
          return
          ;;
      esac
    fi
  fi

  case "$strategy" in
    CURRENT)
      # Keep tool where it is currently installed
      if [ -n "$tool_name" ]; then
        local current_path
        current_path="$(command -v "$tool_name" 2>/dev/null || true)"
        if [ -n "$current_path" ]; then
          bin_dir="$(dirname "$current_path")"
        else
          # Not installed, fall back to USER
          bin_dir="$prefix/bin"
        fi
      else
        # No specific tool, fall back to USER
        bin_dir="$prefix/bin"
      fi
      ;;
    GLOBAL)
      bin_dir="/usr/local/bin"
      ;;
    PROJECT)
      bin_dir="./.local/bin"
      ;;
    USER|*)
      bin_dir="$prefix/bin"
      ;;
  esac

  echo "$bin_dir"
}

# Get install command based on target directory
# Usage: get_install_cmd BIN_DIR
# Sets: INSTALL and RM variables
# shellcheck disable=SC2034  # INSTALL and RM are globals consumed by the calling installer
get_install_cmd() {
  local bin_dir="$1"

  if [ "$bin_dir" = "/usr/local/bin" ]; then
    if [ -w "$bin_dir" ]; then
      INSTALL="install -m 0755"
      RM="rm -f"
    else
      INSTALL="sudo install -m 0755"
      RM="sudo rm -f"
    fi
  else
    INSTALL="install -m 0755"
    RM="rm -f"
  fi
}

# Fetch a GitHub REST API path and print the JSON body.
# Tries `gh api` first (authenticated, higher rate limit) and falls back to an
# unauthenticated curl call. `gh` prints the HTTP error body (e.g. a 401 for a
# stale GITHUB_TOKEN exported from .env) to stdout and exits non-zero, so its
# output is only trusted when it succeeded.
# Usage: github_api_get "repos/OWNER/REPO/tags?per_page=100"
# Returns: 0 with JSON on stdout, 1 when neither source answered
github_api_get() {
  local api_path="${1:?api path required}"
  local body=""

  if command -v gh >/dev/null 2>&1; then
    if body="$(gh api "$api_path" 2>/dev/null)"; then
      printf '%s' "$body"
      return 0
    fi
    echo "# gh api $api_path failed; falling back to unauthenticated GitHub API" >&2
  fi

  body="$(curl --proto '=https' --proto-redir '=https' -fsSL \
    --retry 3 --retry-delay 1 --connect-timeout 10 \
    -H "Accept: application/vnd.github+json" \
    -H "User-Agent: cli-audit" \
    "https://api.github.com/$api_path")" || return 1
  printf '%s' "$body"
}

# Refresh snapshot for a specific tool after installation
# Usage: refresh_snapshot TOOL_NAME
# Updates local_state.json and tools_snapshot.json with latest version of installed tool
refresh_snapshot() {
  local tool_name="${1:-}"

  if [ -z "$tool_name" ]; then
    echo "# Warning: No tool name provided to refresh_snapshot" >&2
    return 1
  fi

  # Path to project root (scripts/lib -> scripts -> root)
  local project_root
  project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  local audit_script="$project_root/audit.py"

  if [ ! -f "$audit_script" ]; then
    echo "# Warning: audit.py not found at $audit_script" >&2
    return 1
  fi

  echo "# Refreshing snapshot for $tool_name..." >&2

  # Brief delay to ensure binary is fully updated and PATH is refreshed
  sleep 0.5

  # Run audit in merge mode for this specific tool
  # Uses --update-local for fast local-only detection (no network calls)
  # Falls back to legacy mode if split files aren't available
  if CLI_AUDIT_UPDATE_LOCAL=1 CLI_AUDIT_MERGE=1 python3 "$audit_script" "$tool_name" >/dev/null 2>&1; then
    echo "# ✓ Snapshot updated for $tool_name" >&2
    return 0
  fi

  # Fallback to legacy mode
  CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 python3 "$audit_script" "$tool_name" >/dev/null 2>&1 || {
    echo "# Warning: Failed to refresh snapshot for $tool_name" >&2
    return 1
  }

  echo "# ✓ Snapshot updated for $tool_name" >&2
  return 0
}
