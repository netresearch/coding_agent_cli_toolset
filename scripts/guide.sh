#!/usr/bin/env bash
set -euo pipefail
trap '' PIPE

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VERBOSE="${VERBOSE:-0}"
OFFLINE="${OFFLINE:-0}"
CLI="${PYTHON:-python3}"

# Load catalog query functions
. "$DIR/lib/catalog.sh"

ensure_perms() {
  chmod +x "$ROOT"/scripts/*.sh 2>/dev/null || true
  chmod +x "$ROOT"/scripts/lib/*.sh 2>/dev/null || true
}

ensure_perms

# Check cache age
SNAP_FILE="${CLI_AUDIT_SNAPSHOT_FILE:-$ROOT/tools_snapshot.json}"
CACHE_MAX_AGE_HOURS="${CACHE_MAX_AGE_HOURS:-24}"

check_cache_age() {
  [ ! -f "$SNAP_FILE" ] && { echo "⚠️  Warning: Snapshot cache missing" >&2; return 1; }
  local now=$(date +%s)
  local snap_time=$(stat -c %Y "$SNAP_FILE" 2>/dev/null || stat -f %m "$SNAP_FILE" 2>/dev/null || echo 0)
  local age_hours=$(( (now - snap_time) / 3600 ))
  if [ $age_hours -gt $CACHE_MAX_AGE_HOURS ]; then
    echo "⚠️  Warning: Snapshot cache is ${age_hours}h old (threshold: ${CACHE_MAX_AGE_HOURS}h)" >&2
    return 2
  fi
  return 0
}

check_cache_age || true

echo "Gathering current tool status from snapshot..."
AUDIT_OUTPUT="$(cd "$ROOT" && CLI_AUDIT_RENDER=1 CLI_AUDIT_LINKS=0 CLI_AUDIT_EMOJI=0 "$CLI" cli_audit.py || true)"
AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"

if [ "$VERBOSE" = "1" ]; then
  printf "%s\n" "$AUDIT_OUTPUT" | "$CLI" smart_column.py -s '|' -t --right 3,5 --header || printf "%s\n" "$AUDIT_OUTPUT"
fi

# JSON helper functions
json_field() {
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool, key = sys.argv[1], sys.argv[2]
try:
    for item in json.loads(data):
        if item.get("tool") == tool:
            print(item.get(key, ""))
            break
except: pass
PY
}

json_bool() {
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool, key = sys.argv[1], sys.argv[2]
try:
    for item in json.loads(data):
        if item.get("tool") == tool and item.get(key):
            print("1")
            break
except: pass
PY
}

osc8() {
  local url="$1"; shift
  local text="$*"
  [ -n "$url" ] && printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$url" "$text" || printf '%s' "$text"
}

# Generic tool processing function - reads ALL metadata from catalog
process_tool() {
  local tool="$1"

  # Get tool data from audit JSON
  local icon="$(json_field "$tool" state_icon)"
  local installed="$(json_field "$tool" installed)"
  local latest="$(json_field "$tool" latest_upstream)"
  local url="$(json_field "$tool" latest_url)"
  local method="$(json_field "$tool" installed_method)"
  local is_up_to_date="$(json_bool "$tool" is_up_to_date)"

  # Get metadata from catalog (with defaults)
  local display="$(catalog_get_guide_property "$tool" display_name "$tool")"
  local install_action="$(catalog_get_guide_property "$tool" install_action "")"
  local description="$(catalog_get_property "$tool" description)"
  local homepage="$(catalog_get_property "$tool" homepage)"

  # Check if up-to-date
  if [ -n "$is_up_to_date" ] && [ -n "$installed" ]; then
    printf "\n==> %s %s\n" "$icon" "$display"
    printf "    installed: %s via %s\n" "$installed" "$method"
    printf "    target:    %s (same)\n" "$(osc8 "$url" "$latest")"
    printf "    up-to-date; skipping.\n"
    return 0
  fi

  # Prompt for installation/update
  printf "\n==> %s %s\n" "$icon" "$display"
  [ -n "$description" ] && printf "    %s\n" "$description"
  [ -n "$homepage" ] && printf "    Homepage: %s\n" "$(osc8 "$homepage" "$homepage")"
  printf "    installed: %s via %s\n" "${installed:-<none>}" "${method:-unknown}"
  printf "    target:    %s\n" "$(osc8 "$url" "${latest:-<unknown>}")"

  # Build install command from catalog metadata
  local install_cmd="install_tool.sh $tool"
  if [ -n "$install_action" ]; then
    install_cmd="install_tool.sh $tool $install_action"
  elif [ -n "$installed" ]; then
    # Tool is already installed, use "update" action
    install_cmd="install_tool.sh $tool update"
  fi
  printf "    will run: scripts/%s\n" "$install_cmd"

  # Prompt with options explained
  printf "    Options:\n"
  printf "      y = Install/upgrade now\n"
  printf "      N = Skip (ask again next time)\n"
  if [ -n "$installed" ]; then
    printf "      s = Skip version %s (ask again if newer available)\n" "$latest"
    printf "      p = Pin to %s (don't ask for upgrades)\n" "$installed"
  else
    printf "      s = Skip version %s (ask again if newer available)\n" "$latest"
    printf "      p = Never install (permanently skip this tool)\n"
  fi

  local prompt_text="Install/update? [y/N/s/p] "

  local ans=""
  if [ -t 0 ]; then
    read -r -p "$prompt_text" ans || true
  elif [ -r /dev/tty ]; then
    read -r -p "$prompt_text" ans </dev/tty || true
  fi

  case "$ans" in
    [Yy])
      # Handle tool-specific version environment variables
      local upgrade_success=0
      if [ "$tool" = "python" ]; then
        UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      elif [ "$tool" = "ruby" ]; then
        RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      else
        "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      fi

      # Re-audit
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"

      # Check if upgrade succeeded by comparing versions
      local new_installed="$(json_field "$tool" installed)"
      if [ "$upgrade_success" = "0" ] || [ "$new_installed" = "$installed" ]; then
        # Upgrade failed or version didn't change
        printf "
    ⚠️  Upgrade did not succeed (version unchanged)
"
        prompt_pin_version "$tool" "$installed"
      else
        # Upgrade succeeded - remove any existing pin to avoid stale pins
        if catalog_has_tool "$tool"; then
          local existing_pin="$(catalog_get_property "$tool" pinned_version)"
          if [ -n "$existing_pin" ] && [ "$existing_pin" != "never" ]; then
            "$ROOT"/scripts/unpin_version.sh "$tool" || true
          fi
        fi
      fi
      ;;
    [Ss])
      # Skip this specific version
      printf "    Skipping version %s (will prompt again if newer version available)\n" "$latest"
      "$ROOT"/scripts/pin_version.sh "$tool" "$latest" || true
      ;;
    [Pp])
      if [ -n "$installed" ]; then
        # Pin to current version
        printf "    Pinning to current version %s\n" "$installed"
        "$ROOT"/scripts/pin_version.sh "$tool" "$installed" || true
      else
        # Never install - pin to "never"
        printf "    Marking as 'never install' (permanently skip this tool)\n"
        "$ROOT"/scripts/pin_version.sh "$tool" "never" || true
      fi
      ;;
    *)
      # User declined (N or empty)
      ;;
  esac
}

# Prompt user to pin version when upgrade is declined or fails
prompt_pin_version() {
  local tool="$1"
  local current_version="$2"

  [ -z "$current_version" ] && current_version="<current>"

  printf "    Pin to version %s to stop upgrade prompts? [y/N] " "$current_version"

  local pin_ans=""
  if [ -t 0 ]; then
    read -r pin_ans || true
  elif [ -r /dev/tty ]; then
    read -r pin_ans </dev/tty || true
  fi

  if [[ "$pin_ans" =~ ^[Yy]$ ]]; then
    "$ROOT"/scripts/pin_version.sh "$tool" "$current_version" || true
  fi
}

# Build tool list from audit output with catalog entries
TOOLS_TO_PROCESS=()
while read -r line; do
  [[ "$line" =~ ^state ]] && continue
  tool_name="$(echo "$line" | awk -F'|' '{gsub(/^ +| +$/,"",$2); print $2}')"
  [ -z "$tool_name" ] && continue

  # Only process tools with catalog entries
  if catalog_has_tool "$tool_name"; then
    # Check if tool is pinned to a version >= latest available or "never"
    pinned_version="$(catalog_get_property "$tool_name" pinned_version)"

    # Skip if pinned to "never" (permanently skip installation)
    if [ "$pinned_version" = "never" ]; then
      continue
    fi

    latest_version="$(json_field "$tool_name" latest_version)"

    if [ -n "$pinned_version" ] && [ -n "$latest_version" ]; then
      # Compare versions: skip if latest <= pinned
      # Simple numeric comparison for semantic versions
      if "$CLI" - "$pinned_version" "$latest_version" <<'PY'
import sys
try:
    pinned, latest = sys.argv[1], sys.argv[2]
    # Strip 'v' prefix if present
    pinned = pinned.lstrip('v')
    latest = latest.lstrip('v')
    # Split into parts and compare
    p_parts = [int(x) for x in pinned.split('.')[:3]]
    l_parts = [int(x) for x in latest.split('.')[:3]]
    # Pad with zeros if needed
    while len(p_parts) < 3: p_parts.append(0)
    while len(l_parts) < 3: l_parts.append(0)
    # Exit 0 (success) if latest <= pinned (should skip)
    sys.exit(0 if tuple(l_parts) <= tuple(p_parts) else 1)
except Exception:
    # On error, don't skip (exit 1)
    sys.exit(1)
PY
      then
        # Skip this tool - pinned version is >= latest available
        continue
      fi
    fi

    TOOLS_TO_PROCESS+=("$tool_name")
  fi
done <<< "$AUDIT_OUTPUT"

# Sort tools by processing order from catalog
declare -A TOOL_LIST
for tool in "${TOOLS_TO_PROCESS[@]}"; do
  order="$(catalog_get_guide_property "$tool" order "1000")"
  TOOL_LIST[$order]="${TOOL_LIST[$order]:-} $tool"
done

# Process tools in order
for order in $(printf '%s\n' "${!TOOL_LIST[@]}" | sort -n); do
  for tool in ${TOOL_LIST[$order]}; do
    process_tool "$tool"
  done
done

echo
echo "All done. Re-run: make audit"
