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
  printf "    installed: %s via %s\n" "${installed:-<none>}" "${method:-unknown}"
  printf "    target:    %s\n" "$(osc8 "$url" "${latest:-<unknown>}")"

  # Build install command from catalog metadata
  local install_cmd="install_tool.sh $tool"
  [ -n "$install_action" ] && install_cmd="install_tool.sh $tool $install_action"
  printf "    will run: scripts/%s\n" "$install_cmd"

  # Prompt
  local prompt_text="Install/update? [y/N] "
  [ -z "$installed" ] && prompt_text="Install? [y/N] "

  local ans=""
  if [ -t 0 ]; then
    read -r -p "$prompt_text" ans || true
  elif [ -r /dev/tty ]; then
    read -r -p "$prompt_text" ans </dev/tty || true
  fi

  if [[ "$ans" =~ ^[Yy]$ ]]; then
    # Handle tool-specific version environment variables
    if [ "$tool" = "python" ]; then
      UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd || true
    elif [ "$tool" = "ruby" ]; then
      RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd || true
    else
      "$ROOT"/scripts/$install_cmd || true
    fi

    # Re-audit
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
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
