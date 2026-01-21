#!/usr/bin/env bash
set -euo pipefail
trap '' PIPE

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VERBOSE="${VERBOSE:-0}"
OFFLINE="${OFFLINE:-0}"
CLI="${PYTHON:-python3}"

# Ignore pins: IGNORE_PINS=1 to show all tools regardless of pin status
IGNORE_PINS="${IGNORE_PINS:-0}"

# Category filter: CATEGORY=python,go or --category=python
CATEGORY_FILTER="${CATEGORY:-}"
for arg in "$@"; do
  case "$arg" in
    --category=*) CATEGORY_FILTER="${arg#--category=}" ;;
    --categories)
      echo "Available categories: python, node, go, rust, ruby, php, shell, git, devops, platform, ai, general"
      exit 0
      ;;
  esac
done

# Load catalog query functions
. "$DIR/lib/catalog.sh"

# Load config query functions (for user preferences like auto_update)
. "$DIR/lib/config.sh"

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
AUDIT_OUTPUT="$(cd "$ROOT" && CLI_AUDIT_RENDER=1 CLI_AUDIT_LINKS=0 CLI_AUDIT_EMOJI=0 "$CLI" audit.py || true)"
AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

# Category definitions: order, icon, description
declare -A CATEGORY_ORDER=(
  [python]=1 [node]=2 [go]=3 [rust]=4 [ruby]=5 [php]=6 [shell]=7
  [git]=10 [devops]=11 [platform]=12 [ai]=13 [general]=20
)
declare -A CATEGORY_ICON=(
  [python]="🐍" [node]="📦" [go]="🔵" [rust]="🦀" [ruby]="💎" [php]="🐘" [shell]="🐚"
  [git]="📝" [devops]="🔧" [platform]="☁️" [ai]="🤖" [general]="🔨"
)
declare -A CATEGORY_DESC=(
  [python]="Python Development"
  [node]="Node.js Development"
  [go]="Go Development"
  [rust]="Rust Development"
  [ruby]="Ruby Development"
  [php]="PHP Development"
  [shell]="Shell Scripting"
  [git]="Git & Version Control"
  [devops]="DevOps & Infrastructure"
  [platform]="Platform CLIs"
  [ai]="AI & LLM Tools"
  [general]="General CLI Utilities"
)

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

  # Determine catalog tool name (handle multi-version tools like php@8.3)
  local catalog_tool="$tool"
  local is_multi_version=""
  local version_cycle=""
  if [[ "$tool" == *"@"* ]]; then
    local base_tool="$(json_field "$tool" base_tool)"
    version_cycle="$(json_field "$tool" version_cycle)"
    if [ -n "$base_tool" ]; then
      catalog_tool="$base_tool"
      is_multi_version="true"
    else
      catalog_tool="${tool%%@*}"
      version_cycle="${tool##*@}"
      is_multi_version="true"
    fi
  fi

  # Get tool data from audit JSON (use full tool name for JSON queries)
  local icon="$(json_field "$tool" state_icon)"
  local installed="$(json_field "$tool" installed)"
  local latest="$(json_field "$tool" latest_upstream)"
  local url="$(json_field "$tool" latest_url)"
  local method="$(json_field "$tool" installed_method)"
  local is_up_to_date="$(json_bool "$tool" is_up_to_date)"

  # Get metadata from catalog (use base tool name for catalog queries)
  local display="$(catalog_get_guide_property "$catalog_tool" display_name "$catalog_tool")"
  # For multi-version tools, append version cycle to display name
  if [ -n "$is_multi_version" ] && [ -n "$version_cycle" ]; then
    display="$display $version_cycle"
  fi
  local install_action="$(catalog_get_guide_property "$catalog_tool" install_action "")"
  local description="$(catalog_get_property "$catalog_tool" description)"
  local homepage="$(catalog_get_property "$catalog_tool" homepage)"
  local auto_update="$(config_get_auto_update "$catalog_tool")"

  # Check if migration needed (deprecated install method)
  local needs_migration=""
  if [ "$tool" = "claude" ] && { [ "$method" = "nvm" ] || [ "$method" = "npm" ]; }; then
    needs_migration="true"
  fi

  # Check if up-to-date (but still migrate if needed)
  if [ -n "$is_up_to_date" ] && [ -n "$installed" ] && [ -z "$needs_migration" ]; then
    printf "\n==> %s %s\n" "$icon" "$display"
    printf "    installed: %s via %s\n" "$installed" "$method"
    printf "    target:    %s (same)\n" "$(osc8 "$url" "$latest")"
    printf "    up-to-date; skipping.\n"
    return 0
  fi

  # Handle migration case (version matches but install method deprecated)
  if [ -n "$needs_migration" ] && [ -n "$is_up_to_date" ]; then
    printf "\n==> ⚠️  %s [migration needed]\n" "$display"
    printf "    installed: %s via %s (deprecated)\n" "$installed" "$method"
    printf "    target:    %s (native installer)\n" "$(osc8 "$url" "$latest")"
    printf "    migrating to native installer...\n"

    "$ROOT"/scripts/install_tool.sh "$tool" upgrade || true

    # Re-audit
    CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"
    return 0
  fi

  # Check if auto_update is enabled - install without prompting
  # BUT: multi-version tools always prompt (more significant operation)
  if [ "$auto_update" = "true" ] && [ -z "$is_multi_version" ]; then
    printf "\n==> %s %s [auto-update]\n" "$icon" "$display"
    printf "    installed: %s via %s\n" "${installed:-<none>}" "${method:-unknown}"
    printf "    target:    %s\n" "$(osc8 "$url" "${latest:-<unknown>}")"
    printf "    auto-updating...\n"

    # Build install command from catalog metadata (use catalog_tool for script name)
    local install_cmd="install_tool.sh $catalog_tool"
    if [ -n "$install_action" ]; then
      install_cmd="install_tool.sh $catalog_tool $install_action"
    elif [ -n "$installed" ]; then
      install_cmd="install_tool.sh $catalog_tool update"
    fi

    # Execute the install with version-specific environment variables
    if [ "$catalog_tool" = "python" ] || [ -n "$is_multi_version" ] && [ "$catalog_tool" = "python" ]; then
      UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd || true
    elif [ "$catalog_tool" = "ruby" ]; then
      RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd || true
    elif [ "$catalog_tool" = "php" ] && [ -n "$version_cycle" ]; then
      PHP_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd || true
    elif [ "$catalog_tool" = "node" ] && [ -n "$version_cycle" ]; then
      NODE_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd || true
    elif [ "$catalog_tool" = "go" ] && [ -n "$version_cycle" ]; then
      GO_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd || true
    else
      "$ROOT"/scripts/$install_cmd || true
    fi

    # Re-audit with fresh collection for this specific tool
    CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"
    return 0
  fi

  # Prompt for installation/update
  printf "\n==> %s %s\n" "$icon" "$display"
  [ -n "$description" ] && printf "    %s\n" "$description"
  [ -n "$homepage" ] && printf "    Homepage: %s\n" "$(osc8 "$homepage" "$homepage")"
  printf "    installed: %s via %s\n" "${installed:-<none>}" "${method:-unknown}"
  printf "    target:    %s\n" "$(osc8 "$url" "${latest:-<unknown>}")"

  # Build install command from catalog metadata (use catalog_tool for script name)
  local install_cmd="install_tool.sh $catalog_tool"
  if [ -n "$install_action" ]; then
    install_cmd="install_tool.sh $catalog_tool $install_action"
  elif [ -n "$installed" ]; then
    # Tool is already installed, use "update" action
    install_cmd="install_tool.sh $catalog_tool update"
  fi
  printf "    will run: scripts/%s\n" "$install_cmd"

  # Prompt with options explained
  # Default: Y for updates (tool installed), N for installs (new tool)
  printf "    Options:\n"
  if [ -n "$installed" ]; then
    printf "      Y = Upgrade now (default)\n"
    printf "      a = Always update (upgrade now + auto-update in future)\n"
    printf "      n = Skip (ask again next time)\n"
    printf "      s = Skip version %s (ask again if newer available)\n" "$latest"
    printf "      p = Pin to %s (don't ask for upgrades)\n" "$installed"
    printf "      r = Remove/uninstall this tool\n"
    if [ -n "$is_multi_version" ]; then
      printf "      P = Skip all %s versions (never install any)\n" "$catalog_tool"
    fi
  else
    printf "      y = Install now\n"
    printf "      a = Always update (install now + auto-update in future)\n"
    printf "      N = Skip (default, ask again next time)\n"
    printf "      s = Skip version %s (ask again if newer available)\n" "$latest"
    printf "      p = Never install (permanently skip this version)\n"
    if [ -n "$is_multi_version" ]; then
      printf "      P = Skip all %s versions (never install any)\n" "$catalog_tool"
    fi
  fi

  # Different defaults: Y for update, N for install
  local prompt_text
  if [ -n "$installed" ]; then
    if [ -n "$is_multi_version" ]; then
      prompt_text="Upgrade? [Y/a/n/s/p/r/P] "
    else
      prompt_text="Upgrade? [Y/a/n/s/p/r] "
    fi
  else
    if [ -n "$is_multi_version" ]; then
      prompt_text="Install? [y/a/N/s/p/P] "
    else
      prompt_text="Install? [y/a/N/s/p] "
    fi
  fi

  local ans=""
  if [ -t 0 ]; then
    read -r -p "$prompt_text" ans || true
  elif [ -r /dev/tty ]; then
    read -r -p "$prompt_text" ans </dev/tty || true
  fi

  # Handle default based on install vs update
  # Empty answer = default (Y for update, N for install)
  if [ -z "$ans" ]; then
    if [ -n "$installed" ]; then
      ans="y"  # Default to yes for updates
    else
      ans="n"  # Default to no for installs
    fi
  fi

  case "$ans" in
    [Yy])
      # Handle tool-specific version environment variables
      local upgrade_success=0
      if [ "$catalog_tool" = "python" ]; then
        UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      elif [ "$catalog_tool" = "ruby" ]; then
        RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      elif [ "$catalog_tool" = "php" ] && [ -n "$version_cycle" ]; then
        PHP_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      elif [ "$catalog_tool" = "node" ] && [ -n "$version_cycle" ]; then
        NODE_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      elif [ "$catalog_tool" = "go" ] && [ -n "$version_cycle" ]; then
        GO_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      else
        "$ROOT"/scripts/$install_cmd && upgrade_success=1 || true
      fi

      # Re-audit with fresh collection for this specific tool (updates snapshot silently)
      CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true

      # Reload full audit JSON from updated snapshot (needed for subsequent tools)
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

      # Check if upgrade succeeded by comparing versions
      local new_installed="$(json_field "$tool" installed)"
      if [ "$upgrade_success" = "0" ]; then
        # Install script failed
        printf "\n    ⚠️  Upgrade failed (install script error)\n"
        prompt_pin_version "$tool" "$installed"
      elif [ "$new_installed" = "$installed" ] && [ "$new_installed" != "$latest" ]; then
        # Version didn't change and not at target
        # BUT: if installed is a prefix of latest (e.g., 3.13 vs 3.13.11), consider it success
        # This happens when version detection returns short form but upgrade actually worked
        if [[ "$latest" == "$new_installed"* ]] || [[ "$new_installed" == "$latest"* ]]; then
          : # Prefix match - upgrade likely succeeded, don't warn
        else
          printf "\n    ⚠️  Upgrade did not succeed (version unchanged)\n"
          prompt_pin_version "$tool" "$installed"
        fi
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
    [Aa])
      # Install/upgrade AND enable auto-update for future (use catalog_tool for settings)
      printf "    Enabling auto-update for future upgrades...\n"
      "$ROOT"/scripts/set_auto_update.sh "$catalog_tool" true >/dev/null 2>&1 || true

      # Handle tool-specific version environment variables
      local upgrade_success_a=0
      if [ "$catalog_tool" = "python" ]; then
        UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      elif [ "$catalog_tool" = "ruby" ]; then
        RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      elif [ "$catalog_tool" = "php" ] && [ -n "$version_cycle" ]; then
        PHP_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      elif [ "$catalog_tool" = "node" ] && [ -n "$version_cycle" ]; then
        NODE_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      elif [ "$catalog_tool" = "go" ] && [ -n "$version_cycle" ]; then
        GO_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      else
        "$ROOT"/scripts/$install_cmd && upgrade_success_a=1 || true
      fi

      # Re-audit with fresh collection for this specific tool
      CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

      # Check if upgrade succeeded
      local new_installed_a="$(json_field "$tool" installed)"
      if [ "$upgrade_success_a" = "0" ]; then
        printf "\n    ⚠️  Upgrade failed (install script error)\n"
        printf "    Auto-update is still enabled - will try again next time.\n"
      elif [ "$new_installed_a" = "$installed" ] && [ "$new_installed_a" != "$latest" ]; then
        # Version didn't change - but check for prefix match (e.g., 3.13 vs 3.13.11)
        if [[ "$latest" == "$new_installed_a"* ]] || [[ "$new_installed_a" == "$latest"* ]]; then
          printf "    ✓ Auto-update enabled. This tool will update automatically in future.\n"
        else
          printf "\n    ⚠️  Upgrade did not succeed (version unchanged)\n"
          printf "    Auto-update is still enabled - will try again next time.\n"
        fi
      else
        printf "    ✓ Auto-update enabled. This tool will update automatically in future.\n"
        # Remove any existing pin
        if catalog_has_tool "$tool"; then
          local existing_pin_a="$(catalog_get_property "$tool" pinned_version)"
          if [ -n "$existing_pin_a" ]; then
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
    [p])
      if [ -n "$installed" ]; then
        # Pin to current version
        printf "    Pinning to current version %s\n" "$installed"
        "$ROOT"/scripts/pin_version.sh "$tool" "$installed" || true
      else
        # Never install - pin to "never" for this specific version
        printf "    Marking as 'never install' (permanently skip this version)\n"
        "$ROOT"/scripts/pin_version.sh "$tool" "never" || true
      fi
      ;;
    [r])
      # Remove/uninstall this tool (only for installed tools)
      if [ -n "$installed" ]; then
        printf "    Removing %s...\n" "$tool"
        "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true

        # Re-audit to update snapshot
        CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
        AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

        # Check if removal succeeded
        local still_installed="$(json_field "$tool" installed)"
        if [ -z "$still_installed" ]; then
          printf "    ✓ %s has been removed\n" "$tool"
        else
          printf "    ⚠️  %s may not have been fully removed (still detected: %s)\n" "$tool" "$still_installed"
        fi
      else
        printf "    Tool is not installed, nothing to remove\n"
      fi
      ;;
    [P])
      # Skip ALL versions of this runtime (only for multi-version tools)
      if [ -n "$is_multi_version" ]; then
        printf "    Marking ALL %s versions as 'never install'\n" "$catalog_tool"
        "$ROOT"/scripts/pin_version.sh "$catalog_tool" "never" || true
      else
        # Fallback to regular pin for non-multi-version tools
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

# Process a deprecated tool with migration options
process_deprecated_tool() {
  local tool="$1"

  # Determine catalog tool name
  local catalog_tool="$tool"
  if [[ "$tool" == *"@"* ]]; then
    catalog_tool="${tool%%@*}"
  fi

  # Get tool data
  local installed="$(json_field "$tool" installed)"
  local method="$(json_field "$tool" installed_method)"
  local description="$(catalog_get_property "$catalog_tool" description)"
  local superseded_by="$(catalog_get_superseded_by "$catalog_tool")"
  local deprecation_msg="$(catalog_get_deprecation_message "$catalog_tool")"

  # Get replacement tool info
  local replacement_desc=""
  if [ -n "$superseded_by" ] && catalog_has_tool "$superseded_by"; then
    replacement_desc="$(catalog_get_property "$superseded_by" description)"
  fi

  printf "\n==> ⚠️  %s %s → DEPRECATED\n" "$tool" "$installed"
  [ -n "$description" ] && printf "    %s\n" "$description"
  [ -n "$deprecation_msg" ] && printf "    ⚠️  %s\n" "$deprecation_msg"
  if [ -n "$superseded_by" ]; then
    printf "    Superseded by: %s\n" "$superseded_by"
    [ -n "$replacement_desc" ] && printf "      └─ %s\n" "$replacement_desc"
  fi
  printf "    installed: %s via %s\n" "$installed" "${method:-unknown}"

  printf "    Options:\n"
  if [ -n "$superseded_by" ]; then
    printf "      M = Migrate to %s (recommended)\n" "$superseded_by"
  fi
  printf "      K = Keep %s (no further updates)\n" "$tool"
  printf "      r = Remove %s\n" "$tool"

  local prompt_text
  if [ -n "$superseded_by" ]; then
    prompt_text="Action? [M/K/r] "
  else
    prompt_text="Action? [K/r] "
  fi

  local ans=""
  if [ -t 0 ]; then
    read -r -p "$prompt_text" ans || true
  elif [ -r /dev/tty ]; then
    read -r -p "$prompt_text" ans </dev/tty || true
  fi

  # Default to K (keep)
  [ -z "$ans" ] && ans="K"

  case "$ans" in
    [Mm])
      if [ -n "$superseded_by" ]; then
        printf "    Migrating to %s...\n" "$superseded_by"

        # Install the replacement
        "$ROOT"/scripts/install_tool.sh "$superseded_by" || true

        # Re-audit for replacement
        CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$superseded_by" >/dev/null 2>&1 || true

        # Check if replacement was installed
        AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"
        local replacement_installed="$(json_field "$superseded_by" installed)"

        if [ -n "$replacement_installed" ]; then
          printf "    ✓ %s %s installed\n" "$superseded_by" "$replacement_installed"

          # Ask about removing the old tool
          printf "    Remove deprecated %s? [Y/n] " "$tool"
          local remove_ans=""
          if [ -t 0 ]; then
            read -r remove_ans || true
          elif [ -r /dev/tty ]; then
            read -r remove_ans </dev/tty || true
          fi

          if [ -z "$remove_ans" ] || [[ "$remove_ans" =~ ^[Yy]$ ]]; then
            printf "    Removing %s...\n" "$tool"
            "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
            CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
            AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

            local still_installed="$(json_field "$tool" installed)"
            if [ -z "$still_installed" ]; then
              printf "    ✓ Migration complete: %s → %s\n" "$tool" "$superseded_by"
            else
              printf "    ⚠️  %s may not have been fully removed\n" "$tool"
            fi
          else
            printf "    Keeping %s alongside %s\n" "$tool" "$superseded_by"
          fi
        else
          printf "    ⚠️  Failed to install %s\n" "$superseded_by"
        fi
      else
        printf "    No replacement available, keeping %s\n" "$tool"
      fi
      ;;
    [Kk])
      printf "    Keeping %s (deprecated, no further updates)\n" "$tool"
      ;;
    [Rr])
      printf "    Removing %s...\n" "$tool"
      "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
      CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

      local still_there="$(json_field "$tool" installed)"
      if [ -z "$still_there" ]; then
        printf "    ✓ %s has been removed\n" "$tool"
      else
        printf "    ⚠️  %s may not have been fully removed\n" "$tool"
      fi
      ;;
    *)
      printf "    Keeping %s\n" "$tool"
      ;;
  esac
}

# Build tool list from audit output, grouped by category
declare -A CATEGORY_TOOLS
# Track deprecated tools separately (for migration prompts)
DEPRECATED_TOOLS=""
while read -r line; do
  [[ "$line" =~ ^state ]] && continue
  tool_name="$(echo "$line" | awk -F'|' '{gsub(/^ +| +$/,"",$2); print $2}')"
  [ -z "$tool_name" ] && continue

  # Determine catalog tool name (handle multi-version tools like php@8.3)
  catalog_name="$tool_name"
  is_multi_version=""
  if [[ "$tool_name" == *"@"* ]]; then
    # Multi-version tool: get base_tool from JSON, or extract from name
    base_tool="$(json_field "$tool_name" base_tool)"
    if [ -n "$base_tool" ]; then
      catalog_name="$base_tool"
      is_multi_version="true"
    else
      # Fallback: extract base name before @
      catalog_name="${tool_name%%@*}"
      is_multi_version="true"
    fi
  fi

  # Only process tools with catalog entries (check base tool for multi-version)
  if catalog_has_tool "$catalog_name"; then
    # Check if tool is deprecated
    if catalog_is_deprecated "$catalog_name"; then
      # Deprecated tool: only track if installed (for migration prompt)
      installed="$(json_field "$tool_name" installed)"
      if [ -n "$installed" ]; then
        DEPRECATED_TOOLS="$DEPRECATED_TOOLS $tool_name"
      fi
      # Skip deprecated tools in main loop (don't suggest installing them)
      continue
    fi

    # Check if tool is pinned (use catalog name for pin check)
    # Skip pin checks if IGNORE_PINS=1
    if [ "$IGNORE_PINS" != "1" ]; then
      pinned_version="$(catalog_get_property "$catalog_name" pinned_version)"

      # For multi-version tools, check pinned_versions object AND base tool pin
      if [ -n "$is_multi_version" ]; then
        # First check if the BASE tool (e.g., php) is pinned to "never" - skip ALL versions
        if [ "$pinned_version" = "never" ]; then
          continue
        fi
        # Then check version-specific pin
        version_cycle="${tool_name##*@}"
        multi_pin="$(catalog_get_pinned_version "$catalog_name" "$version_cycle")"
        if [ "$multi_pin" = "never" ]; then
          continue
        fi
        # Skip if this specific version cycle is pinned to a version
        if [ -n "$multi_pin" ]; then
          continue
        fi
      else
        # Skip if pinned to "never" (permanently skip installation)
        if [ "$pinned_version" = "never" ]; then
          continue
        fi

        # Skip if pinned to any specific version (don't prompt for upgrades)
        if [ -n "$pinned_version" ]; then
          continue
        fi
      fi
    fi  # end IGNORE_PINS check

    # Skip installed tools with upstream_method="skip" (package-manager-only tools)
    # These can't be tracked for upgrades, but we still show them if not installed
    upstream_method="$(json_field "$tool_name" upstream_method)"
    installed="$(json_field "$tool_name" installed)"
    if [ "$upstream_method" = "skip" ] && [ -n "$installed" ]; then
      continue
    fi

    # Get category from catalog (use catalog name)
    category="$(catalog_get_property "$catalog_name" category)"
    category="${category:-general}"

    # Add to category group
    CATEGORY_TOOLS[$category]="${CATEGORY_TOOLS[$category]:-} $tool_name"
  fi
done <<< "$AUDIT_OUTPUT"

# Helper: check if category matches filter
category_matches_filter() {
  local cat="$1"
  [ -z "$CATEGORY_FILTER" ] && return 0  # No filter = match all
  echo ",$CATEGORY_FILTER," | grep -q ",$cat," && return 0
  return 1
}

# Helper: sort tools with runtime first, then multi-version, then others
# Priority: base runtime (0) < multi-version (1-99 by version desc) < other tools (100)
sort_tools_runtime_first() {
  local tools="$1"
  local category="$2"

  # Runtimes that should appear first in their category
  local runtimes="python node php go ruby rust"

  for tool in $tools; do
    local sort_key="999"  # Default: other tools sort last

    # Check if tool is a base runtime
    for rt in $runtimes; do
      if [ "$tool" = "$rt" ]; then
        sort_key="000"
        break
      fi
    done

    # Check if tool is a multi-version runtime (e.g., python@3.14)
    if [ "$sort_key" = "999" ] && [[ "$tool" == *"@"* ]]; then
      local base="${tool%%@*}"
      local version="${tool##*@}"
      for rt in $runtimes; do
        if [ "$base" = "$rt" ]; then
          # Sort by version descending (higher versions first)
          # Convert version to sortable number (3.14 -> 986, 3.13 -> 987)
          local major="${version%%.*}"
          local minor="${version#*.}"
          minor="${minor%%.*}"
          # Invert so higher versions sort first
          sort_key=$(printf "%03d" $((999 - major * 10 - minor)))
          break
        fi
      done
    fi

    echo "$sort_key $tool"
  done | sort | awk '{print $2}'
}

# Process tools grouped by category (in category order)
for category in $(printf '%s\n' "${!CATEGORY_TOOLS[@]}" | while read c; do echo "${CATEGORY_ORDER[$c]:-99} $c"; done | sort -n | awk '{print $2}'); do
  tools="${CATEGORY_TOOLS[$category]}"
  [ -z "$tools" ] && continue

  # Sort tools: runtime first, then multi-version (desc), then others
  tools="$(sort_tools_runtime_first "$tools" "$category")"

  # Skip if category doesn't match filter
  if ! category_matches_filter "$category"; then
    continue
  fi

  # Count tools in category
  tool_count=$(echo $tools | wc -w)

  # Print category header
  icon="${CATEGORY_ICON[$category]:-📦}"
  desc="${CATEGORY_DESC[$category]:-$category}"

  printf "\n"
  printf "================================================================================\n"
  printf "%s %s (%d tool%s)\n" "$icon" "$desc" "$tool_count" "$([ $tool_count -eq 1 ] && echo '' || echo 's')"
  printf "================================================================================\n"

  # Category-level prompt (skip if auto-yes mode)
  if [ "${AUTO_YES_ALL:-}" != "1" ]; then
    printf "  Tools: %s\n" "$(echo $tools | tr ' ' ', ' | sed 's/^, //')"
    printf "  Process this category? [Y/n/a=all/s=skip-all] "

    cat_ans=""
    if [ -t 0 ]; then
      read -r cat_ans || true
    elif [ -r /dev/tty ]; then
      read -r cat_ans </dev/tty || true
    fi

    case "$cat_ans" in
      [Nn])
        printf "  Skipping %s category\n" "$desc"
        continue
        ;;
      [Aa]|all)
        printf "  Processing all remaining categories\n"
        AUTO_YES_ALL=1
        ;;
      [Ss]|skip-all)
        printf "  Skipping all remaining categories\n"
        break
        ;;
    esac
  fi

  # Process each tool in category
  for tool in $tools; do
    process_tool "$tool"
  done
done

# Process deprecated tools (if any installed)
DEPRECATED_TOOLS="$(echo $DEPRECATED_TOOLS | xargs)"  # trim whitespace
if [ -n "$DEPRECATED_TOOLS" ]; then
  dep_count=$(echo $DEPRECATED_TOOLS | wc -w)

  printf "\n"
  printf "================================================================================\n"
  printf "⚠️  Deprecated Tools (%d installed)\n" "$dep_count"
  printf "================================================================================\n"

  # Category-level prompt
  if [ "${AUTO_YES_ALL:-}" != "1" ]; then
    printf "  Tools: %s\n" "$(echo $DEPRECATED_TOOLS | tr ' ' ',')"
    printf "  These tools are no longer maintained and have recommended replacements.\n"
    printf "  Review deprecated tools? [Y/n] "

    dep_ans=""
    if [ -t 0 ]; then
      read -r dep_ans || true
    elif [ -r /dev/tty ]; then
      read -r dep_ans </dev/tty || true
    fi

    case "$dep_ans" in
      [Nn])
        printf "  Skipping deprecated tools\n"
        ;;
      *)
        for tool in $DEPRECATED_TOOLS; do
          process_deprecated_tool "$tool"
        done
        ;;
    esac
  else
    # AUTO_YES_ALL mode - still process deprecated tools
    for tool in $DEPRECATED_TOOLS; do
      process_deprecated_tool "$tool"
    done
  fi
fi

echo
echo "All done. Re-run: make audit"
