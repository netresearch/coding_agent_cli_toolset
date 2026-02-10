#!/usr/bin/env bash
# Main orchestrator for tool installation
# Reads catalog and delegates to appropriate installer or reconciliation system
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source reconciliation libraries
. "$DIR/lib/reconcile.sh"

TOOL="${1:-}"
ACTION="${2:-install}"

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME [ACTION]" >&2
  echo "Actions: install, update, reconcile, status, uninstall" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"

# Check if tool has catalog entry
if [ ! -f "$CATALOG_FILE" ]; then
  echo "[$TOOL] Error: No catalog entry found" >&2
  echo "[$TOOL] Available tools: $(find "$DIR/../catalog" -name '*.json' -exec basename {} .json \; | tr '\n' ' ')" >&2
  exit 1
fi

# Check if jq is available
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not found" >&2
  exit 1
fi

# Read install method from catalog
INSTALL_METHOD="$(jq -r '.install_method' "$CATALOG_FILE")"

if [ -z "$INSTALL_METHOD" ] || [ "$INSTALL_METHOD" = "null" ]; then
  echo "[$TOOL] Error: No install_method specified in catalog" >&2
  exit 1
fi

# Handle uninstall universally - remove ALL installations found
if [ "$ACTION" = "uninstall" ]; then
  # For dedicated_script tools, delegate to their own uninstall handler first
  if [ "$INSTALL_METHOD" = "dedicated_script" ]; then
    script_name="$(jq -r '.script // ""' "$CATALOG_FILE" 2>/dev/null || true)"
    if [ -n "$script_name" ] && [ -f "$DIR/$script_name" ]; then
      "$DIR/$script_name" uninstall || true
    fi
  fi

  binary_name="$(jq -r '.binary_name // ""' "$CATALOG_FILE" 2>/dev/null || echo "$TOOL")"
  binary_name="${binary_name:-$TOOL}"

  # Detect remaining installations
  all_installs="$(detect_all_installations "$TOOL" "$binary_name" 2>/dev/null || true)"
  install_count="$(echo "$all_installs" | grep -c . || echo 0)"

  if [ "$install_count" -eq 0 ]; then
    echo "[$TOOL] Successfully removed"
    exit 0
  fi

  if [ "$install_count" -gt 1 ]; then
    echo "[$TOOL] Found $install_count installations:"
    echo "$all_installs" | while IFS=: read -r method path; do
      echo "  • $method: $path"
    done
    echo "[$TOOL] Removing all installations..."
  fi

  # Remove each installation (skip system binaries - those can't/shouldn't be removed)
  echo "$all_installs" | while IFS=: read -r method path; do
    [ -z "$method" ] && continue
    # Extract base method (remove version info like "npm(v25.3.0)")
    base_method="${method%%(*}"
    # Skip system binaries with a clear message
    if [ "$base_method" = "system" ]; then
      echo "[$TOOL] Skipping system binary: $path (managed by OS)" >&2
      continue
    fi
    remove_installation "$TOOL" "$base_method" "$binary_name"
  done

  # Verify removal (ignore system entries in the check)
  remaining="$(detect_all_installations "$TOOL" "$binary_name" 2>/dev/null || true)"
  remaining_nonsystem="$(echo "$remaining" | grep -v "^system:" || true)"
  remaining_count="$(echo "$remaining_nonsystem" | grep -c . || echo 0)"
  if [ "$remaining_count" -eq 0 ]; then
    echo "[$TOOL] Successfully removed all installations"
  else
    echo "[$TOOL] Warning: $remaining_count installation(s) could not be removed:"
    echo "$remaining_nonsystem" | while IFS=: read -r method path; do
      echo "  • $method: $path"
    done
  fi
  exit 0
fi

# Check if tool uses reconciliation system (install_method == "auto")
if [ "$INSTALL_METHOD" = "auto" ]; then
  # Use reconciliation system
  case "$ACTION" in
    install|update|reconcile)
      # Pass the actual action to reconcile_tool
      reconcile_tool "$CATALOG_FILE" "$ACTION"
      exit $?
      ;;
    status)
      reconcile_tool "$CATALOG_FILE" "status"
      exit $?
      ;;
    *)
      echo "[$TOOL] Error: Unknown action: $ACTION" >&2
      exit 1
      ;;
  esac
fi

# Traditional path: delegate to appropriate installer
INSTALLER_SCRIPT="$DIR/installers/${INSTALL_METHOD}.sh"

if [ ! -f "$INSTALLER_SCRIPT" ]; then
  echo "[$TOOL] Error: Installer not found: $INSTALLER_SCRIPT" >&2
  echo "[$TOOL] install_method: $INSTALL_METHOD" >&2
  exit 1
fi

if [ ! -x "$INSTALLER_SCRIPT" ]; then
  echo "[$TOOL] Error: Installer not executable: $INSTALLER_SCRIPT" >&2
  exit 1
fi

# Execute installer with all remaining arguments
shift  # Remove TOOL from $@
exec "$INSTALLER_SCRIPT" "$TOOL" "$@"
