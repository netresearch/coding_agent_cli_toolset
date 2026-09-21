#!/usr/bin/env bash
set -euo pipefail
trap '' PIPE
# Graceful interrupt handling
# shellcheck disable=SC2034  # written by the INT trap
INTERRUPTED=0
trap 'INTERRUPTED=1; echo; echo "⚠️  Interrupted. Partial summary:"; print_summary; exit 130' INT

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VERBOSE="${VERBOSE:-0}"
# Suppress Homebrew auto-update during upgrade runs to reduce noise
export HOMEBREW_NO_AUTO_UPDATE=1
OFFLINE="${OFFLINE:-0}"
CLI="${PYTHON:-python3}"

# Ignore pins: IGNORE_PINS=1 to show all tools regardless of pin status
IGNORE_PINS="${IGNORE_PINS:-0}"

# Duplicate-install count for the tool most recently passed to
# check_multi_installs(); consumed by process_tool to offer inline cleanup.
LAST_MULTI_COUNT=0
# Space-separated tool names seen with duplicate installs this run (for the
# summary hint); de-duplicated when counted.
GUIDE_DUP_LIST=""

# Installers leave <tool>.already-current / <tool>.held-back here
MARKER_DIR="${CLI_AUDIT_MARKER_DIR:-/tmp/.cli-audit}"

# Summary counters
SUMMARY_UPDATED=0
SUMMARY_SKIPPED=0
SUMMARY_FAILED=0
SUMMARY_REMOVED=0

print_summary() {
  local label="${1:-interrupted}"
  echo "================================================================================"
  echo "Summary${label:+ ($label)}"
  echo "================================================================================"
  printf "  Updated:   %d\n" "$SUMMARY_UPDATED"
  printf "  Removed:   %d\n" "$SUMMARY_REMOVED"
  printf "  Skipped:   %d\n" "$SUMMARY_SKIPPED"
  printf "  Failed:    %d\n" "$SUMMARY_FAILED"
  echo
  echo "Re-run: make audit"
  local dup_count=0
  if [ -n "${GUIDE_DUP_LIST// /}" ]; then
    dup_count="$(printf '%s\n' $GUIDE_DUP_LIST | sort -u | grep -c . || true)"
  fi
  if [ "$dup_count" -gt 0 ]; then
    printf "  → %d tool(s) with duplicate installs: 'make reconcile-all'\n" "$dup_count"
  fi
  echo "  → upgrade the package managers themselves: 'make upgrade-managed'"
}

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

# Load pin library (user-local version pins)
. "$DIR/lib/pins.sh"

# Load config query functions (for user preferences like auto_update)
. "$DIR/lib/config.sh"

# Load capability detection (for multi-installation detection)
. "$DIR/lib/capability.sh"

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
  local now
  now=$(date +%s) || true
  local snap_time
  snap_time=$(stat -c %Y "$SNAP_FILE" 2>/dev/null || stat -f %m "$SNAP_FILE" 2>/dev/null || echo 0) || true
  local age_hours=$(( (now - snap_time) / 3600 ))
  if [ $age_hours -gt $CACHE_MAX_AGE_HOURS ]; then
    echo "⚠️  Warning: Snapshot cache is ${age_hours}h old (threshold: ${CACHE_MAX_AGE_HOURS}h)" >&2
    return 2
  fi
  return 0
}

check_cache_age || true

# Helper: safely reload AUDIT_JSON, preserving previous value on failure
reload_audit_json() {
  local new_json
  new_json="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py 2>/dev/null)" || true
  # Only update if we got valid JSON (non-empty, starts with '[')
  if [ -n "$new_json" ] && [[ "$new_json" == "["* ]]; then
    AUDIT_JSON="$new_json"
  fi
}

# Refresh the snapshot's installed state (network-free) so the displayed
# "installed:" matches what the installers detect live as "before:". The refresh
# preserves the cached upstream "latest", so it stays offline and consistent with
# `make update` (no target regression, no make-update/make-upgrade disagreement).
echo "Refreshing installed status (no network)..."
(cd "$ROOT" && "$CLI" audit.py --update-local >/dev/null 2>&1) || true
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

# PATH without virtualenv/conda bin dirs: the dirs the Python audit treats as
# environments (pyvenv.cfg next to bin/, venv/conda name patterns)
installation_path() {
  local dir parent out=""
  local -a dirs=()
  IFS=: read -ra dirs <<<"$PATH"
  for dir in "${dirs[@]}"; do
    [ -n "$dir" ] || continue
    # PEP 405 venvs carry pyvenv.cfg next to bin/ (no dirname: PATH may lack it)
    parent="${dir%/}"
    parent="${parent%/*}"
    [ -f "$parent/pyvenv.cfg" ] && continue
    case "${dir%/}/" in
      */venv/bin/ | */.venv/bin/ | */env/bin/ | */venvs/* | */.venvs/* | */virtualenvs/* | */.virtualenvs/* | */envs/* | */conda/* | */miniconda* | */anaconda*) continue ;;
    esac
    out="${out:+$out:}$dir"
  done
  printf '%s' "$out"
}

# Probe the installed version directly from the binary — bypasses the
# snapshot round-trip. Used as a fallback in upgrade-success checks so a
# stale snapshot (e.g. after a transient endoflife failure) doesn't mask a
# genuinely successful install.
#
# Args: catalog_tool [version_cycle]
# Echoes version number (e.g. "3.14.4") on success, empty on failure.
probe_installed_version() {
  local catalog_tool="$1"
  local version_cycle="${2:-}"
  local binary pattern bin_path ver

  if [ -n "$version_cycle" ]; then
    pattern="$(catalog_get_property "$catalog_tool" "multi_version.binary_pattern" 2>/dev/null)"
    [ -z "$pattern" ] && pattern="${catalog_tool}{cycle}"
    binary="${pattern//\{cycle\}/$version_cycle}"
  else
    binary="$(catalog_get_property "$catalog_tool" "binary_name" 2>/dev/null)"
    [ -z "$binary" ] && binary="$catalog_tool"
  fi

  if [[ "$binary" == /* ]]; then
    [ -x "$binary" ] || return 1
    bin_path="$binary"
  else
    # An activated venv's copy is no installation
    bin_path="$(PATH="$(installation_path)" command -v "$binary" 2>/dev/null)" || return 1
  fi

  # Try --version first, then -v, capture both stdout and stderr. Extract
  # the first dotted version number we see.
  ver="$("$bin_path" --version 2>&1 || "$bin_path" -v 2>&1 || true)"
  printf '%s\n' "$ver" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1
}

# True while a pin still hides the tool: "never", the release the user chose
# to skip (s: pin == latest), the version the user chose to hold (p: pin ==
# installed), or for a cycle the cycle itself. A skipped release no longer
# hides the tool once a newer one is out.
# Args: pin latest installed [cycle]
pin_applies() {
  local pin="$1" latest="$2" installed="$3" cycle="${4:-}"
  [ -n "$pin" ] || return 1
  [ "$pin" = "never" ] && return 0
  [ -n "$cycle" ] && [ "$pin" = "$cycle" ] && return 0
  [ "$pin" = "$latest" ] || [ "$pin" = "$installed" ]
}

# Remove installer markers before an install, so a marker left by an earlier
# run (make upgrade-<tool>, an interrupted guide, another cycle of the same
# tool) cannot decide this run's verdict.
clear_upgrade_markers() {
  rm -f "$MARKER_DIR/${1}.already-current" "$MARKER_DIR/${1}.held-back"
}

# Classify the outcome of an install/upgrade run. Call after the re-audit.
# An install script that exits 0 has not necessarily changed anything: a
# shadowed binary, an unchanged package or a stale version string all exit 0.
# Args: script_ok catalog_tool tool installed latest [version_cycle]
# Echoes: updated | failed | unchanged | unverified | already-current | held-back
#   unverified:      version unchanged, but no upstream version to compare with
#   already-current: installer found the binary identical to the target release
#   held-back:       package manager has no newer version than the installed one
upgrade_verdict() {
  local script_ok="$1" catalog_tool="$2" tool="$3" installed="$4" latest="$5"
  local version_cycle="${6:-}" marker="" new_installed="" probed=""
  local marker_dir="$MARKER_DIR"
  [ -f "$marker_dir/${catalog_tool}.already-current" ] && marker="already-current"
  [ -f "$marker_dir/${catalog_tool}.held-back" ] && marker="held-back"
  rm -f "$marker_dir/${catalog_tool}.already-current" "$marker_dir/${catalog_tool}.held-back"

  if [ "$script_ok" != "1" ]; then
    echo "failed"
    return 0
  fi

  new_installed="$(json_field "$tool" installed)"
  # If the snapshot still reports the pre-install version, the refresh
  # may have hit a transient failure (endoflife timeout, flaky audit).
  # Probe the binary directly as a tiebreaker.
  if [ -z "$new_installed" ] || [ "$new_installed" = "$installed" ]; then
    probed="$(probe_installed_version "$catalog_tool" "$version_cycle" 2>/dev/null || true)"
    if [ -n "$probed" ] && [ "$probed" != "$installed" ]; then
      new_installed="$probed"
    fi
  fi

  if [ -n "$new_installed" ] && [ "$new_installed" != "$installed" ]; then
    echo "updated"
  elif [ -n "$marker" ]; then
    echo "$marker"
  elif [ -z "$new_installed" ]; then
    # Nothing detectable after an install: it did not happen
    echo "unchanged"
  elif [ -z "$latest" ]; then
    echo "unverified"
  elif [ -n "$new_installed" ] && { [[ "$latest" == "$new_installed".* ]] || [[ "$new_installed" == "$latest".* ]]; }; then
    # Short version form (3.13 vs 3.13.11): detection truncates, upgrade worked.
    # The dot boundary keeps 1.1 from matching 1.12.0.
    echo "updated"
  else
    echo "unchanged"
  fi
}

# Print the verdict of an upgrade and update the summary counters.
# Args: verdict tool installed latest
report_upgrade_verdict() {
  local verdict="$1" tool="$2" installed="$3" latest="$4"
  case "$verdict" in
    updated)
      SUMMARY_UPDATED=$((SUMMARY_UPDATED + 1))
      ;;
    failed)
      printf "    ⚠️  Upgrade failed (install script error)\n"
      SUMMARY_FAILED=$((SUMMARY_FAILED + 1))
      ;;
    unchanged)
      printf "    ⚠️  Upgrade did not take effect: still %s, target %s\n" "${installed:-<none>}" "${latest:-<unknown>}"
      SUMMARY_FAILED=$((SUMMARY_FAILED + 1))
      ;;
    already-current)
      # Upstream version string is stale (sd 1.1.0 reports 1.0.0). No pin:
      # the guide hides every pinned tool, which would also hide the next
      # real release.
      printf "    ✓ Binary already matches release %s (its version string is stale)\n" "$latest"
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      ;;
    unverified)
      printf "    ⚠️  No upstream version known; cannot tell whether %s changed\n" "${installed:-the install}"
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      ;;
    held-back)
      printf "    ⏸  Package manager has no newer version than %s (upstream: %s)\n" "${installed:-<none>}" "${latest:-<unknown>}"
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      ;;
  esac
}

# Print installed status line (reusable for auto-update and interactive prompts)
print_installed_status() {
  local installed="$1"
  local method="$2"
  if [ -z "$installed" ]; then
    printf "    installed: not installed\n"
  else
    printf "    installed: %s via %s\n" "$installed" "${method:-unknown}"
  fi
}

# Check for multiple installations and print warning if found
# Args: catalog_tool_name
# Returns: 0 always (informational only)
check_multi_installs() {
  local catalog_tool="$1"
  local binary_name
  binary_name="$(catalog_get_property "$catalog_tool" binary_name)"
  binary_name="${binary_name:-$catalog_tool}"
  # Cheap shell pre-check: only pay for the richer reconcile query when there
  # actually is more than one install (the common case is a single install).
  # Check every catalog candidate binary (e.g. pip AND pip3, fd AND fdfind) so
  # alternate-named duplicates aren't missed here.
  local cand_list
  cand_list="$(jq -r '.candidates[]? // empty' "$ROOT/catalog/$catalog_tool.json" 2>/dev/null)"
  [ -z "$cand_list" ] && cand_list="$binary_name"
  local all_installs=""
  local cand found
  while IFS= read -r cand; do
    [ -z "$cand" ] && continue
    found="$(detect_all_installations "$catalog_tool" "$cand" 2>/dev/null || true)"
    [ -n "$found" ] && all_installs+="${all_installs:+$'\n'}$found"
  done <<< "$cand_list"
  all_installs="$(printf '%s\n' "$all_installs" | grep -v '^[[:space:]]*$' | sort -u || true)"
  local install_count
  install_count="$(echo "$all_installs" | grep -c . || true)"
  LAST_MULTI_COUNT="$install_count"
  [ "$install_count" -le 1 ] && return 0
  GUIDE_DUP_LIST="$GUIDE_DUP_LIST $catalog_tool"

  # Duplicates exist — render version + active + preferred markers from the
  # reconcile plan (the single source of truth). Fall back to the basic listing
  # if reconcile produces nothing.
  local recon_json rendered
  recon_json="$(cd "$ROOT" && CLI_AUDIT_JSON=1 "$CLI" audit.py --reconcile "$catalog_tool" 2>/dev/null || true)"
  rendered="$(RECON_JSON="$recon_json" "$CLI" - <<'PY'
import os, json
try:
    doc = json.loads(os.environ.get("RECON_JSON", "").strip())
    plan = (doc.get("results") or [None])[0]
    installs = plan.get("installations") or []
except Exception:
    raise SystemExit(0)
if len(installs) < 2:
    raise SystemExit(0)
active_path = (plan.get("active") or {}).get("path")
pref_path = (plan.get("preferred") or {}).get("path")
lines = [f"    ⚠️  Multiple installations detected ({len(installs)}):"]
for i in installs:
    marks = []
    if i.get("active"):
        marks.append("→ active")
    if i.get("preferred"):
        marks.append("✓ keep")
    suffix = ("  " + "  ".join(marks)) if marks else ""
    lines.append(f"       • {i.get('version') or '?'}  {i.get('method')}  {i.get('path')}{suffix}")
if active_path and pref_path and active_path != pref_path:
    lines.append(f"       note: cleanup would change which {plan.get('tool')} runs (active → preferred).")
print("\n".join(lines))
PY
)"
  if [ -n "$rendered" ]; then
    printf '%s\n' "$rendered"
  else
    printf "    ⚠️  Multiple installations detected (%d):\n" "$install_count"
    echo "$all_installs" | while IFS=: read -r inst_method inst_path; do
      printf "       • %s: %s\n" "$inst_method" "$inst_path"
    done
  fi
  return 0
}

# Generic tool processing function - reads ALL metadata from catalog
process_tool() {
  local tool="$1"

  # Determine catalog tool name (handle multi-version tools like php@8.3)
  local catalog_tool="$tool"
  local is_multi_version=""
  local version_cycle=""
  if [[ "$tool" == *"@"* ]]; then
    local base_tool
    base_tool="$(json_field "$tool" base_tool)" || true
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
  local icon
  icon="$(json_field "$tool" state_icon)" || true
  local installed
  installed="$(json_field "$tool" installed)" || true
  local latest
  latest="$(json_field "$tool" latest_upstream)" || true
  local url
  url="$(json_field "$tool" latest_url)" || true
  local method
  method="$(json_field "$tool" installed_method)" || true
  local is_up_to_date
  is_up_to_date="$(json_bool "$tool" is_up_to_date)" || true

  # Get metadata from catalog (use base tool name for catalog queries)
  local display
  display="$(catalog_get_guide_property "$catalog_tool" display_name "$catalog_tool")" || true
  # For multi-version tools, append version cycle to display name
  if [ -n "$is_multi_version" ] && [ -n "$version_cycle" ]; then
    display="$display $version_cycle"
  fi
  local install_action
  install_action="$(catalog_get_guide_property "$catalog_tool" install_action "")" || true
  local description
  description="$(catalog_get_property "$catalog_tool" description)" || true
  local homepage
  homepage="$(catalog_get_property "$catalog_tool" homepage)" || true
  # Multi-version tools (python@3.13, php@8.3, etc.) store auto-update per cycle,
  # so 'a' on one cycle doesn't silently apply to other cycles. Non-multi-version
  # tools use the bare catalog name.
  local auto_update_key="$catalog_tool"
  if [ -n "$is_multi_version" ]; then
    auto_update_key="$tool"
  fi
  local auto_update
  auto_update="$(config_get_auto_update "$auto_update_key")" || true

  # Check if runtime requirements are satisfied (e.g., npm requires node)
  local missing_req
  missing_req="$(catalog_check_requires "$catalog_tool")" || true
  if [ -n "$missing_req" ]; then
    printf "\n==> ⏭️  %s\n" "$display"
    printf "    skipped: requires '%s' which is not installed\n" "$missing_req"
    return 0
  fi

  # Check if migration needed (deprecated install method)
  # But skip migration if native binary already exists and works
  local needs_migration=""
  if [ "$tool" = "claude" ] && { [ "$method" = "nvm" ] || [ "$method" = "npm" ]; }; then
    # Check if native binary exists and works
    if [ -x "$HOME/.local/bin/claude" ]; then
      local native_ver
      native_ver=$("$HOME/.local/bin/claude" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
      if [ -n "$native_ver" ]; then
        # Native exists - just clean up stale nvm, don't trigger full migration
        printf "\n==> %s %s\n" "✅" "$display"
        printf "    installed: %s (native at ~/.local/bin/claude)\n" "$native_ver"
        printf "    Cleaning up stale npm/nvm installation...\n"
        # Source cleanup function and run it
        if [ -f "$ROOT/scripts/install_claude.sh" ]; then
          (
            source "$ROOT/scripts/install_claude.sh" 2>/dev/null
            cleanup_npm_versions 2>/dev/null
          ) || true
        fi
        return 0
      fi
    fi
    needs_migration="true"
  fi

  # Check if up-to-date (but still migrate if needed)
  if [ -n "$is_up_to_date" ] && [ -n "$installed" ] && [ -z "$needs_migration" ]; then
    printf "\n==> %s %s\n" "$icon" "$display"
    printf "    installed: %s via %s\n" "$installed" "$method"
    printf "    target:    %s (same)\n" "$(osc8 "$url" "$latest")"
    check_multi_installs "$catalog_tool"
    SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
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
    reload_audit_json
    return 0
  fi

  # Check if auto_update is enabled - install without prompting.
  # For multi-version tools the key is cycle-qualified (e.g. python@3.13), so
  # each cycle opts in independently.
  if [ "$auto_update" = "true" ]; then
    # Auto-update keeps *existing* tools current; it must never bootstrap a
    # missing tool. Tools like pip are intentionally left to uv/bun rather than
    # installed on our behalf. When the tool isn't installed, report the skip
    # and return. Deliberate installs are offered only by the interactive
    # prompt below, which is reached when auto-update is not enabled.
    if [ -z "$installed" ]; then
      printf "\n==> ⏭️  %s [auto-update]\n" "$display"
      printf "    not installed; skipping (auto-update upgrades existing tools only)\n"
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      return 0
    fi
    printf "\n==> %s %s [auto-update]\n" "$icon" "$display"
    print_installed_status "$installed" "$method"
    # Show target; for self-managed tools (skip_upstream) show "self-managed" instead of <unknown>
    local target_display="${latest:-<unknown>}"
    local skip_upstream
    skip_upstream="$(catalog_get_property "$catalog_tool" skip_upstream)" || true
    if [ "$target_display" = "<unknown>" ] && [ "$skip_upstream" = "true" ]; then
      target_display="self-managed"
    fi
    printf "    target:    %s\n" "$(osc8 "$url" "$target_display")"
    check_multi_installs "$catalog_tool"
    printf "    auto-updating...\n"

    # Build the upgrade command from catalog metadata (use catalog_tool for
    # script name). The tool is guaranteed installed here, so this is always an
    # update unless the catalog defines an explicit install_action.
    local install_cmd="install_tool.sh $catalog_tool update"
    if [ -n "$install_action" ]; then
      install_cmd="install_tool.sh $catalog_tool $install_action"
    fi

    # Execute the install with version-specific environment variables
    local auto_update_success=0
    clear_upgrade_markers "$catalog_tool"
    if [ "$catalog_tool" = "python" ] || [ -n "$is_multi_version" ] && [ "$catalog_tool" = "python" ]; then
      UV_PYTHON_SPEC="$latest" "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    elif [ "$catalog_tool" = "ruby" ]; then
      RUBY_VERSION="$latest" "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    elif [ "$catalog_tool" = "php" ] && [ -n "$version_cycle" ]; then
      PHP_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    elif [ "$catalog_tool" = "node" ] && [ -n "$version_cycle" ]; then
      NODE_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    elif [ "$catalog_tool" = "go" ] && [ -n "$version_cycle" ]; then
      GO_VERSION="$version_cycle" "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    else
      "$ROOT"/scripts/$install_cmd && auto_update_success=1 || true
    fi

    # Re-audit with fresh collection for this specific tool
    CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
    reload_audit_json
    report_upgrade_verdict \
      "$(upgrade_verdict "$auto_update_success" "$catalog_tool" "$tool" "$installed" "$latest" "$version_cycle")" \
      "$tool" "$installed" "$latest"
    return 0
  fi

  # Prompt for installation/update
  printf "\n==> %s %s\n" "$icon" "$display"
  [ -n "$description" ] && printf "    %s\n" "$description"
  [ -n "$homepage" ] && printf "    Homepage: %s\n" "$(osc8 "$homepage" "$homepage")"
  print_installed_status "$installed" "$method"

  check_multi_installs "$catalog_tool"

  # Show target; for self-managed tools (skip_upstream) show "self-managed" instead of <unknown>
  local target_display_p="${latest:-<unknown>}"
  local skip_upstream_p
  skip_upstream_p="$(catalog_get_property "$catalog_tool" skip_upstream)" || true
  if [ "$target_display_p" = "<unknown>" ] && [ "$skip_upstream_p" = "true" ]; then
    target_display_p="self-managed"
  fi
  printf "    target:    %s\n" "$(osc8 "$url" "$target_display_p")"

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
    printf "      s = Skip only %s (ask again when newer patch available)\n" "$latest"
    if [ -n "$is_multi_version" ]; then
      printf "      p = Pin %s cycle to %s (don't upgrade)\n" "$version_cycle" "$installed"
    else
      printf "      p = Pin to %s (don't ask for upgrades)\n" "$installed"
    fi
    printf "      r = Remove/uninstall this tool\n"
    if [ "${LAST_MULTI_COUNT:-0}" -gt 1 ]; then
      printf "      c = Clean up duplicates (keep preferred, remove the rest)\n"
    fi
    if [ -n "$is_multi_version" ]; then
      printf "      P = Skip ALL outdated %s cycles\n" "$catalog_tool"
    fi
  else
    printf "      y = Install now\n"
    printf "      a = Always update (install now + auto-update in future)\n"
    printf "      N = Skip (default, ask again next time)\n"
    printf "      s = Skip only %s (ask again when newer patch available)\n" "$latest"
    if [ -n "$is_multi_version" ]; then
      printf "      p = Never install %s (skip entire %s.x cycle)\n" "$display" "$version_cycle"
      printf "      P = Skip ALL outdated %s cycles\n" "$catalog_tool"
    else
      printf "      p = Never install (permanently skip this tool)\n"
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
    if [ "${LAST_MULTI_COUNT:-0}" -gt 1 ]; then
      prompt_text="${prompt_text%] }/c] "
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
      clear_upgrade_markers "$catalog_tool"
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
      reload_audit_json

      local verdict
      verdict="$(upgrade_verdict "$upgrade_success" "$catalog_tool" "$tool" "$installed" "$latest" "$version_cycle")"
      report_upgrade_verdict "$verdict" "$tool" "$installed" "$latest"
      case "$verdict" in
        failed|unchanged|held-back)
          prompt_pin_version "$tool" "$installed"
          ;;
        updated)
          # Remove any existing pin to avoid stale pins
          local existing_pin
          existing_pin="$(pins_get "$tool")"
          if [ -n "$existing_pin" ] && [ "$existing_pin" != "never" ]; then
            "$ROOT"/scripts/unpin_version.sh "$tool" || true
          fi
          ;;
      esac
      ;;
    [Aa])
      # Install/upgrade AND enable auto-update for future. Use the cycle-qualified
      # key for multi-version tools so other cycles still prompt.
      printf "    Enabling auto-update for future upgrades...\n"
      "$ROOT"/scripts/set_auto_update.sh "$auto_update_key" true >/dev/null 2>&1 || true

      # Handle tool-specific version environment variables
      local upgrade_success_a=0
      clear_upgrade_markers "$catalog_tool"
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
      reload_audit_json

      local verdict_a
      verdict_a="$(upgrade_verdict "$upgrade_success_a" "$catalog_tool" "$tool" "$installed" "$latest" "$version_cycle")"
      report_upgrade_verdict "$verdict_a" "$tool" "$installed" "$latest"
      case "$verdict_a" in
        failed|unchanged)
          printf "    Auto-update is still enabled - will try again next time.\n"
          ;;
        *)
          printf "    ✓ Auto-update enabled. This tool will update automatically in future.\n"
          ;;
      esac
      if [ "$verdict_a" = "updated" ]; then
        # Remove any existing pin
        local existing_pin_a
        existing_pin_a="$(pins_get "$tool")"
        if [ -n "$existing_pin_a" ]; then
          "$ROOT"/scripts/unpin_version.sh "$tool" || true
        fi
      fi
      ;;
    [Ss])
      # Skip this specific patch version only
      printf "    Skipping only %s (will prompt again when newer patch available)\n" "$latest"
      "$ROOT"/scripts/pin_version.sh "$tool" "$latest" || true
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      ;;
    [p])
      if [ -n "$installed" ]; then
        # Pin to current version
        if [ -n "$is_multi_version" ]; then
          printf "    Pinning %s cycle to %s\n" "$version_cycle" "$installed"
        else
          printf "    Pinning to current version %s\n" "$installed"
        fi
        "$ROOT"/scripts/pin_version.sh "$tool" "$installed" || true
      else
        # Never install - pin to "never" for this version cycle
        if [ -n "$is_multi_version" ]; then
          printf "    Marking %s cycle as 'never install'\n" "$version_cycle"
        else
          printf "    Marking as 'never install' (permanently skip this tool)\n"
        fi
        "$ROOT"/scripts/pin_version.sh "$tool" "never" || true
      fi
      ;;
    [r])
      # Remove/uninstall this tool (only for installed tools)
      if [ -n "$installed" ]; then
        printf "    Removing %s...\n" "$tool"
        # Pass version cycle for multi-version tools so only that cycle is removed
        if [ -n "$is_multi_version" ] && [ -n "$version_cycle" ]; then
          if [ "$catalog_tool" = "node" ]; then
            NODE_VERSION="$version_cycle" "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
          elif [ "$catalog_tool" = "python" ]; then
            UV_PYTHON_SPEC="$version_cycle" "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
          elif [ "$catalog_tool" = "go" ]; then
            GO_VERSION="$version_cycle" "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
          elif [ "$catalog_tool" = "php" ]; then
            PHP_VERSION="$version_cycle" "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
          else
            "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
          fi
        else
          "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true
        fi

        # Re-audit to update snapshot
        CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
        reload_audit_json

        # Check if removal succeeded
        local still_installed
        still_installed="$(json_field "$tool" installed)" || true
        if [ -z "$still_installed" ]; then
          printf "    ✓ %s has been removed\n" "$tool"
          SUMMARY_REMOVED=$((SUMMARY_REMOVED + 1))
        else
          # Check if remaining installation is a system/apt binary that we can't remove
          local remaining_method
          remaining_method="$(json_field "$tool" installed_method)" || true
          if [ "$remaining_method" = "apt" ] || [ "$remaining_method" = "system" ]; then
            printf "    ✓ User-managed %s removed (system %s still present at %s — managed by OS)\n" \
              "$tool" "$still_installed" "$remaining_method"
            SUMMARY_REMOVED=$((SUMMARY_REMOVED + 1))
          else
            printf "    ⚠️  %s may not have been fully removed (still detected: %s via %s)\n" "$tool" "$still_installed" "${remaining_method:-unknown}"
            SUMMARY_FAILED=$((SUMMARY_FAILED + 1))
          fi
        fi
      else
        printf "    Tool is not installed, nothing to remove\n"
      fi
      ;;
    [Cc])
      # Clean up duplicate installations: keep the preferred, remove the rest.
      # The plan (keep/remove, active marker) was already shown by
      # check_multi_installs above. Confirm the destructive step, then apply.
      if [ "${LAST_MULTI_COUNT:-0}" -gt 1 ]; then
        local ans_c=""
        if [ -t 0 ]; then
          read -r -p "    Remove the non-preferred duplicate(s)? [y/N] " ans_c || true
        elif [ -r /dev/tty ]; then
          read -r -p "    Remove the non-preferred duplicate(s)? [y/N] " ans_c </dev/tty || true
        fi
        if [ "$ans_c" = "y" ] || [ "$ans_c" = "Y" ]; then
          if (cd "$ROOT" && "$CLI" audit.py --reconcile "$catalog_tool" --apply --yes); then
            printf "    ✓ Duplicates removed (kept preferred install)\n"
          else
            printf "    ⚠️  Cleanup did not complete (tool may be on the protect list)\n"
          fi
          CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
          reload_audit_json
        else
          printf "    Skipped cleanup\n"
        fi
      else
        printf "    No duplicate installations to clean up\n"
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
      SUMMARY_SKIPPED=$((SUMMARY_SKIPPED + 1))
      ;;
  esac
}

# Prompt user to pin version when upgrade is declined or fails
prompt_pin_version() {
  local tool="$1"
  local current_version="$2"

  # Nothing installed: there is no version to pin
  [ -z "$current_version" ] && return 0

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
  local installed
  installed="$(json_field "$tool" installed)" || true
  local method
  method="$(json_field "$tool" installed_method)" || true
  local description
  description="$(catalog_get_property "$catalog_tool" description)" || true
  local superseded_by
  superseded_by="$(catalog_get_superseded_by "$catalog_tool")" || true
  local deprecation_msg
  deprecation_msg="$(catalog_get_deprecation_message "$catalog_tool")" || true

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

        # Check if replacement is already installed
        local replacement_installed
        replacement_installed="$(json_field "$superseded_by" installed)" || true

        if [ -n "$replacement_installed" ]; then
          printf "    ✓ %s %s already installed (skipping install)\n" "$superseded_by" "$replacement_installed"
        else
          # Install the replacement
          "$ROOT"/scripts/install_tool.sh "$superseded_by" || true

          # Re-audit for replacement
          CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$superseded_by" >/dev/null 2>&1 || true

          # Check if replacement was installed
          reload_audit_json
          replacement_installed="$(json_field "$superseded_by" installed)"
          if [ -n "$replacement_installed" ]; then
            printf "    ✓ %s %s installed\n" "$superseded_by" "$replacement_installed"
          fi
        fi

        if [ -n "$replacement_installed" ]; then

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
            reload_audit_json

            local still_installed
            still_installed="$(json_field "$tool" installed)" || true
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
      reload_audit_json

      local still_there
      still_there="$(json_field "$tool" installed)" || true
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

    # Check if tool is pinned (read from user-local pins file)
    # Skip pin checks if IGNORE_PINS=1
    if [ "$IGNORE_PINS" != "1" ]; then
      pinned_version="$(pins_get "$catalog_name")"

      # For multi-version tools, check cycle-specific pin AND base tool pin
      if [ -n "$is_multi_version" ]; then
        # First check if the BASE tool (e.g., php) is pinned to "never" - skip ALL versions
        if [ "$pinned_version" = "never" ]; then
          continue
        fi
        # Then check version-specific pin
        version_cycle="${tool_name##*@}"
        multi_pin="$(pins_get_cycle "$catalog_name" "$version_cycle")"
        if [ "$multi_pin" = "never" ]; then
          continue
        fi
        # Skip while the cycle pin still applies
        if [ -n "$multi_pin" ] && pin_applies "$multi_pin" "$(json_field "$tool_name" latest_upstream)" \
          "$(json_field "$tool_name" installed)" "$version_cycle"; then
          continue
        fi
      else
        # Skip if pinned to "never" (permanently skip installation)
        if [ "$pinned_version" = "never" ]; then
          continue
        fi

        # Skip while the pin still applies (don't prompt for that release)
        if [ -n "$pinned_version" ] && pin_applies "$pinned_version" "$(json_field "$tool_name" latest_upstream)" \
          "$(json_field "$tool_name" installed)"; then
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

# Helper: sort tools alphabetically by name within a category
sort_tools_by_name() {
  printf '%s\n' $1 | sort
}

# Process tools grouped by category (in category order)
for category in $(printf '%s\n' "${!CATEGORY_TOOLS[@]}" | while read c; do echo "${CATEGORY_ORDER[$c]:-99} $c"; done | sort -n | awk '{print $2}'); do
  tools="${CATEGORY_TOOLS[$category]}"
  [ -z "$tools" ] && continue

  # Sort tools alphabetically by name
  tools="$(sort_tools_by_name "$tools")"

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
    printf "  Process this category? [Y/n/a=all categories/s=skip-all] "

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

# Print final summary
echo
print_summary ""
