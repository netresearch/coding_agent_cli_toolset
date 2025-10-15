#!/usr/bin/env bash
set -euo pipefail
# Avoid aborting on SIGPIPE if any downstream reader closes early
trap '' PIPE

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
VERBOSE="${VERBOSE:-0}"
OFFLINE="${OFFLINE:-0}"

CLI="${PYTHON:-python3}"

run_audit() {
  (cd "$ROOT" && CLI_AUDIT_OFFLINE="$OFFLINE" CLI_AUDIT_LINKS=0 CLI_AUDIT_EMOJI=0 CLI_AUDIT_TIMEOUT_SECONDS="${CLI_AUDIT_TIMEOUT_SECONDS:-3}" "$CLI" cli_audit.py)
}

get_field() {
  # usage: get_field TOOL field_index
  # fields: 1:state 2:tool 3:installed 4:installed_method 5:latest 6:upstream_method
  local tool="$1" idx="$2"
  awk -F'[|]' -v t="$tool" -v i="$idx" 'NR>1 && $2==t {gsub(/^ +| +$/,"",$i); print $i; exit}' <<< "$AUDIT_OUTPUT"
}

prompt_action() {
  local title="$1" current="$2" method="$3" latest="$4" planned="$5" tool="$6"
  printf "\n"
  printf "==> %s\n" "$title"
  printf "    installed: %s via %s\n" "${current:-<none>}" "${method:-unknown}"
  printf "    target:    %s via %s\n" "${latest:-<unknown>}" "${planned:-unknown}"
  # Preview command to be executed
  case "$tool" in
    rust)        printf "    will run: scripts/install_tool.sh rust reconcile\n" ;;
    core)        printf "    will run: scripts/install_core.sh update\n" ;;
    python)      printf "    will run: scripts/install_tool.sh python update\n" ;;
    pip|pipx|poetry|httpie|semgrep)
                  printf "    will run: uv tool install --force --upgrade %s\n" "$tool" ;;
    node)        printf "    will run: scripts/install_tool.sh node reconcile\n" ;;
    go)          printf "    will run: scripts/install_tool.sh go\n" ;;
    docker)      printf "    will run: scripts/install_tool.sh docker\n" ;;
    docker-compose) printf "    will run: echo 'Ensure Docker is up to date (Compose v2 plugin)'\n" ;;
    aws)         printf "    will run: scripts/install_tool.sh aws\n" ;;
    kubectl)     printf "    will run: scripts/install_tool.sh kubectl\n" ;;
    terraform)   printf "    will run: scripts/install_tool.sh terraform\n" ;;
    ansible)     printf "    will run: scripts/install_tool.sh ansible update\n" ;;
    *)           printf "    will run: scripts/install_core.sh reconcile %s\n" "$tool" ;;
  esac
  local ans
  # Determine appropriate prompt based on context
  local prompt_text="Install/update? [y/N] "
  # Check if this is a migration (version matches but method differs)
  if [ "$current" = "$latest" ] && [ "$method" != "$planned" ]; then
    prompt_text="Migrate installation method? [y/N] "
  elif [ -z "$current" ] || [ "$current" = "<none>" ]; then
    prompt_text="Install? [y/N] "
  fi
  # Read from the real TTY to avoid broken pipes when stdout/stderr are piped
  if [ -t 0 ]; then
    read -r -p "$prompt_text" ans || true
  else
    # Fallback: read from /dev/tty if available
    if [ -r /dev/tty ]; then
      read -r -p "$prompt_text" ans </dev/tty || true
    else
      ans=""
    fi
  fi
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    return 0
  fi
  return 1
}

ensure_perms() {
  chmod +x "$ROOT"/scripts/*.sh || true
  chmod +x "$ROOT"/scripts/lib/*.sh || true
}

ensure_perms

# Check cache age and warn if stale
SNAP_FILE="${CLI_AUDIT_SNAPSHOT_FILE:-$ROOT/tools_snapshot.json}"
CACHE_MAX_AGE_HOURS="${CACHE_MAX_AGE_HOURS:-24}"

check_cache_age() {
  if [ ! -f "$SNAP_FILE" ]; then
    echo "⚠️  Warning: Snapshot cache missing ($SNAP_FILE)" >&2
    echo "   Run 'make update' first to populate the cache." >&2
    return 1
  fi

  # Get snapshot age in hours
  local now=$(date +%s)
  local snap_time=$(stat -c %Y "$SNAP_FILE" 2>/dev/null || stat -f %m "$SNAP_FILE" 2>/dev/null || echo 0)
  local age_seconds=$((now - snap_time))
  local age_hours=$((age_seconds / 3600))

  if [ $age_hours -gt $CACHE_MAX_AGE_HOURS ]; then
    echo "⚠️  Warning: Snapshot cache is ${age_hours} hours old (threshold: ${CACHE_MAX_AGE_HOURS}h)" >&2
    echo "   Consider running 'make update' for fresh version data." >&2
    return 2
  fi

  return 0
}

check_cache_age || true

echo "Gathering current tool status from snapshot..."
# Use RENDER mode ONLY - no collection, no network calls
# Expected workflow: 'make update' populates cache, 'make upgrade' uses it
# All data comes from existing snapshot - instant read
AUDIT_OUTPUT="$(cd "$ROOT" && CLI_AUDIT_RENDER=1 CLI_AUDIT_LINKS=0 CLI_AUDIT_EMOJI=0 "$CLI" cli_audit.py || true)"
# Also get JSON from snapshot (no network calls, instant)
AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
if [ "$VERBOSE" = "1" ]; then
  # Pretty print the audit output for context
  printf "%s\n" "$AUDIT_OUTPUT" | "$CLI" smart_column.py -s '|' -t --right 3,5 --header || printf "%s\n" "$AUDIT_OUTPUT"
fi

# Helpers to read JSON and render links
json_field() {
  # usage: json_field TOOL KEY
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "")
data = data.strip()
tool = sys.argv[1]
key = sys.argv[2]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            v = item.get(key, "")
            if v is None:
                v = ""
            print(v)
            break
except Exception:
    print("")
PY
}

json_bool() {
  # usage: json_bool TOOL KEY   -> prints 1 if true, else empty
  local tool="$1" key="$2"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" "$key" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool = sys.argv[1]
key = sys.argv[2]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            v = item.get(key)
            if isinstance(v, bool) and v:
                print("1")
            break
except Exception:
    pass
PY
}

json_duplicates() {
  # usage: json_duplicates TOOL -> prints duplicate count (or empty if 0/1)
  local tool="$1"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool = sys.argv[1]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            all_installs = item.get("all_installations", [])
            if len(all_installs) > 1:
                print(len(all_installs))
            break
except Exception:
    pass
PY
}

json_all_installations() {
  # usage: json_all_installations TOOL -> prints "version|method|path" lines for each installation
  local tool="$1"
  AUDIT_JSON="$AUDIT_JSON" "$CLI" - "$tool" <<'PY'
import sys, json, os
data = os.environ.get("AUDIT_JSON", "").strip()
tool = sys.argv[1]
try:
    arr = json.loads(data)
    for item in arr:
        if item.get("tool") == tool:
            all_installs = item.get("all_installations", [])
            for inst in all_installs:
                version = inst.get("version", "")
                method = inst.get("method", "")
                path = inst.get("path", "")
                print(f"{version}|{method}|{path}")
            break
except Exception:
    pass
PY
}

prompt_duplicate_removal() {
  # usage: prompt_duplicate_removal TOOL ICON
  local tool="$1" icon="$2"
  local dup_count="$(json_duplicates "$tool")"

  if [ -z "$dup_count" ] || [ "$dup_count" -le 1 ]; then
    return 0  # No duplicates, nothing to do
  fi

  printf "\n"
  printf "⚠️  Warning: %s %s has %s conflicting installations:\n" "$icon" "$tool" "$dup_count"

  local idx=1
  while IFS='|' read -r version method path; do
    printf "    [%d] %s via %s  (%s)\n" "$idx" "$version" "$method" "$path"
    ((idx++)) || true
  done < <(json_all_installations "$tool")

  printf "    Multiple installations can cause version conflicts and PATH issues.\n"
  printf "    Recommendation: Keep only the preferred installation method.\n"

  local ans
  printf "Remove conflicting installations? [y/N] "
  if [ -t 0 ]; then
    read -r -p "" ans || true
  else
    if [ -r /dev/tty ]; then
      read -r -p "" ans </dev/tty || true
    else
      ans=""
    fi
  fi

  if [[ "$ans" =~ ^[Yy]$ ]]; then
    # Get preferred installation (the first one selected by audit)
    local preferred_path="$(json_field "$tool" installed_path_selected)"
    printf "    Keeping: %s (preferred)\n" "$preferred_path"

    # Remove all other installations
    while IFS='|' read -r version method path; do
      if [ "$path" != "$preferred_path" ]; then
        printf "    Removing: %s via %s...\n" "$path" "$method"
        # Remove based on method
        if [[ "$method" == *"pipx"* ]]; then
          pipx uninstall "$tool" >/dev/null 2>&1 || true
        elif [[ "$method" == *"uv tool"* ]]; then
          uv tool uninstall "$tool" >/dev/null 2>&1 || true
        elif [[ "$method" == *"pip"* ]] || [[ "$method" == *"user"* ]]; then
          python3 -m pip uninstall -y "$tool" >/dev/null 2>&1 || true
          rm -f "$path" >/dev/null 2>&1 || true
        else
          # Generic removal - try to remove the binary
          rm -f "$path" >/dev/null 2>&1 || true
        fi
      fi
    done < <(json_all_installations "$tool")

    printf "    Cleanup complete. Re-auditing...\n"
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
    return 0
  fi

  return 1
}

osc8() {
  local url="$1"; shift
  local text="$*"
  if [ -n "$url" ]; then
    printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$url" "$text"
  else
    printf '%s' "$text"
  fi
}

display_method() {
  # Convert upstream_method (version lookup source) to user-friendly display
  # For tools tracked via GitHub, show the actual installation method
  local tool="$1" upstream="$2"
  case "$upstream" in
    github)
      # For GitHub-tracked tools, show the actual preferred installation method
      case "$tool" in
        rust) echo "rustup" ;;
        uv) echo "official installer" ;;
        python) echo "uv python" ;;
        node) echo "nvm" ;;
        go) echo "official installer" ;;
        *) echo "$upstream" ;;
      esac
      ;;
    *)
      # For other sources, upstream_method already indicates installation method
      echo "$upstream"
      ;;
  esac
}

# Rust first (for cargo-based tools) - use JSON for accuracy
RUST_ICON="$(json_field rust state_icon)"
RUST_INSTALLED="$(json_field rust installed)"
RUST_METHOD="$(json_field rust installed_method)"
RUST_LATEST="$(json_field rust latest_upstream)"
RUST_URL="$(json_field rust latest_url)"
RUST_PLANNED_METHOD="$(display_method rust "$(json_field rust upstream_method)")"
if [ -n "$(json_bool rust is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$RUST_ICON" "Rust (cargo)"
  printf "    installed: %s via %s\n" "${RUST_INSTALLED:-<none>}" "${RUST_METHOD:-unknown}"
  printf "    target:    %s via %s\n" "$(osc8 "$RUST_URL" "${RUST_LATEST:-<unknown>}")" "$RUST_PLANNED_METHOD"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${RUST_ICON} Rust (cargo)" "$RUST_INSTALLED" "$RUST_METHOD" "$(osc8 "$RUST_URL" "$RUST_LATEST")" "$RUST_PLANNED_METHOD" rust; then
    "$ROOT"/scripts/install_tool.sh rust reconcile || true
  fi
fi

# UV (ensure official binary) + Python stack (before Node/core tools)
UV_ICON="$(json_field uv state_icon)"
UV_CURR="$(json_field uv installed)"
UV_METHOD="$(json_field uv installed_method)"
UV_LATEST="$(json_field uv latest_upstream)"
UV_URL="$(json_field uv latest_url)"
UV_PLANNED="$(display_method uv "$(json_field uv upstream_method)")"
if [ -n "$(json_bool uv is_up_to_date)" ] && [ -n "$UV_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$UV_ICON" "uv"
  printf "    installed: %s via %s\n" "${UV_CURR:-<none>}" "$UV_METHOD"
  printf "    target:    %s via %s\n" "$(osc8 "$UV_URL" "${UV_LATEST:-<unknown>}")" "$UV_PLANNED"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${UV_ICON} uv" "$UV_CURR" "$UV_METHOD" "$(osc8 "$UV_URL" "$UV_LATEST")" "$UV_PLANNED" core; then
    "$ROOT"/scripts/install_tool.sh uv reconcile || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

# Python stack (after ensuring uv)
PY_ICON="$(json_field python state_icon)"
PY_CURR="$(json_field python installed)"
PY_LATEST="$(json_field python latest_upstream)"
PY_URL="$(json_field python latest_url)"
PY_METHOD="$(json_field python installed_method)"
PY_PLANNED="$(display_method python "$(json_field python upstream_method)")"
if [ -n "$(json_bool python is_up_to_date)" ]; then
  printf "\n"
  printf "==> %s %s\n" "$PY_ICON" "Python stack"
  printf "    installed: %s via %s\n" "${PY_CURR:-<none>}" "$PY_METHOD"
  printf "    target:    %s via %s\n" "$(osc8 "$PY_URL" "${PY_LATEST:-<unknown>}")" "$PY_PLANNED"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${PY_ICON} Python stack" "$PY_CURR" "$PY_METHOD" "$(osc8 "$PY_URL" "$PY_LATEST")" "$PY_PLANNED" python; then
    UV_PYTHON_SPEC="$PY_LATEST" "$ROOT"/scripts/install_tool.sh python update || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

# Node stack (Node + package managers)
NODE_ICON="$(json_field node state_icon)"
NODE_CURR="$(json_field node installed)"
NODE_LATEST="$(json_field node latest_upstream)"
NODE_URL="$(json_field node latest_url)"
NODE_METHOD="$(json_field node installed_method)"
NODE_PLANNED="$(display_method node "$(json_field node upstream_method)")"
# Treat stack as up-to-date only if node, npm, pnpm, and yarn are all up-to-date
NODE_ALL_OK=""
if [ -n "$(json_bool node is_up_to_date)" ] && [ -n "$(json_bool npm is_up_to_date)" ] && [ -n "$(json_bool pnpm is_up_to_date)" ] && [ -n "$(json_bool yarn is_up_to_date)" ]; then
  NODE_ALL_OK="1"
fi
if [ -n "$NODE_ALL_OK" ]; then
  printf "\n"; printf "==> %s %s\n" "$NODE_ICON" "Node.js stack"; printf "    installed: %s via %s\n" "${NODE_CURR:-<none>}" "$NODE_METHOD"; printf "    target:    %s via %s\n" "$(osc8 "$NODE_URL" "${NODE_LATEST:-<unknown>}")" "$NODE_PLANNED"; printf "    up-to-date; skipping.\n"
else
  if prompt_action "${NODE_ICON} Node.js stack" "$NODE_CURR" "$NODE_METHOD" "$(osc8 "$NODE_URL" "$NODE_LATEST")" "$NODE_PLANNED" node; then
    "$ROOT"/scripts/install_tool.sh node reconcile || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

# Offer explicit package manager updates only when not up-to-date
if [ -z "$(json_bool npm is_up_to_date)" ]; then
  if prompt_action "$(json_field npm state_icon) npm (global)" "$(json_field npm installed)" "$(json_field npm installed_method)" "$(osc8 "$(json_field npm latest_url)" "$(json_field npm latest_upstream)")" "$(json_field npm upstream_method)" npm; then
    corepack enable >/dev/null 2>&1 || true
    npm install -g npm@latest >/dev/null 2>&1 || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi
if [ -z "$(json_bool pnpm is_up_to_date)" ]; then
  if prompt_action "$(json_field pnpm state_icon) pnpm" "$(json_field pnpm installed)" "$(json_field pnpm installed_method)" "$(osc8 "$(json_field pnpm latest_url)" "$(json_field pnpm latest_upstream)")" "$(json_field pnpm upstream_method)" pnpm; then
    corepack prepare pnpm@latest --activate >/dev/null 2>&1 || npm install -g pnpm@latest >/dev/null 2>&1 || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi
if [ -z "$(json_bool yarn is_up_to_date)" ]; then
  if prompt_action "$(json_field yarn state_icon) yarn" "$(json_field yarn installed)" "$(json_field yarn installed_method)" "$(osc8 "$(json_field yarn latest_url)" "$(json_field yarn latest_upstream)")" "$(json_field yarn upstream_method)" yarn; then
    # Prefer stable tag for Yarn (Berry)
    corepack prepare yarn@stable --activate >/dev/null 2>&1 || npm install -g yarn@latest >/dev/null 2>&1 || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

# Go stack – show sanitized version and planned source (before core tools that use go)
GO_ICON="$(json_field go state_icon)"
GO_CURR_RAW="$(command -v go >/dev/null 2>&1 && go version 2>/dev/null | awk '{print $3}' || echo)"
GO_CURR="${GO_CURR_RAW#go}"
GO_LATE="$(json_field go latest_upstream)"
GO_URL="$(json_field go latest_url)"
GO_PLANNED="$(display_method go "$(json_field go upstream_method)")"
if [ -n "${GO_CURR}" ]; then GO_METHOD="go"; else GO_METHOD="none"; fi
if [ -n "$(json_bool go is_up_to_date)" ]; then
  printf "\n"; printf "==> %s %s\n" "$GO_ICON" "Go toolchain"; printf "    installed: %s via %s\n" "$GO_CURR" "$GO_METHOD"; printf "    target:    %s via %s\n" "$(osc8 "$GO_URL" "${GO_LATE:-<unknown>}")" "$GO_PLANNED"; printf "    up-to-date; skipping.\n"
else
  if prompt_action "${GO_ICON} Go toolchain" "$GO_CURR" "$GO_METHOD" "$(osc8 "$GO_URL" "$GO_LATE")" "$GO_PLANNED" go; then
    "$ROOT"/scripts/install_tool.sh go || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

# Prefer uv for Python CLI tools: offer migration from pipx/user when detected
if command -v uv >/dev/null 2>&1 || "$ROOT"/scripts/install_tool.sh uv reconcile >/dev/null 2>&1; then
  # Include all Python console CLIs we track (expandable). ansible is handled separately below.
  for t in pip pipx poetry httpie pre-commit bandit semgrep black isort flake8; do
    # First check for duplicate installations and offer cleanup
    prompt_duplicate_removal "$t" "$(json_field "$t" state_icon)" || true

    METHOD="$(json_field "$t" installed_method)"
    if [ -n "$METHOD" ] && [ -z "$(json_bool "$t" is_up_to_date)" ]; then
      : # keep normal outdated prompts elsewhere
    fi
    # Migrate only when pipx is the current method
    if [ -n "$METHOD" ] && printf "%s" "$METHOD" | grep -Eqi "pipx|pip/user|pip"; then
      ICON="$(json_field "$t" state_icon)"
      CURR="$(json_field "$t" installed)"
      LATE="$(json_field "$t" latest_upstream)"
      URL="$(json_field "$t" latest_url)"
      TITLE="$ICON $t (migrate to uv tool)"
      if prompt_action "$TITLE" "$CURR" "$METHOD" "$(osc8 "$URL" "$LATE")" "uv tool" "$t"; then
        # Install via uv tool, then remove pipx version to avoid shim conflicts
        uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
        if command -v pipx >/dev/null 2>&1; then pipx uninstall "$t" >/dev/null 2>&1 || true; fi
        # Remove user pip scripts that might shadow uv tools
        rm -f "$HOME/.local/bin/$t" >/dev/null 2>&1 || true
        AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
      fi
    fi
  done
fi

# Core tools (fd, fzf, rg, jq, yq, bat, delta, just, and npm/cargo/go tools)
# Note: Python tools (semgrep, pre-commit, etc.) are handled separately in migration/Python utilities loops
# Note: C-specific tools (cscope) removed as not relevant to this project
CORE_TOOLS=(fd fzf ripgrep jq yq bat delta just curlie dive trivy gitleaks git-absorb git-branchless git-lfs eslint prettier shfmt shellcheck golangci-lint fx glab gam ctags entr parallel ast-grep direnv git gh tfsec ninja)
for t in "${CORE_TOOLS[@]}"; do
  ICON="$(json_field "$t" state_icon)"
  CURR="$(json_field "$t" installed)"
  LATE="$(json_field "$t" latest_upstream)"
  URL="$(json_field "$t" latest_url)"
  CURR_METHOD="$(json_field "$t" installed_method)"
  # For display purposes only - shows where version info comes from (github, pypi, etc.)
  UPSTREAM_METHOD="$(json_field "$t" upstream_method)"
  # Only skip if version is up-to-date (method is already correct if it's working at right version)
  if [ -n "$(json_bool "$t" is_up_to_date)" ] && [ -n "$CURR" ]; then
    printf "\n"; printf "==> %s %s\n" "$ICON" "$t"; printf "    installed: %s via %s\n" "${CURR:-<none>}" "$CURR_METHOD"; printf "    target:    %s (same)\n" "$(osc8 "$URL" "${LATE:-<unknown>}")"; printf "    up-to-date; skipping.\n"; continue
  fi
  # Prompt for update or migration
  if prompt_action "${ICON} $t" "$CURR" "$CURR_METHOD" "$(osc8 "$URL" "$LATE")" "$CURR_METHOD" "$t"; then
    "$ROOT"/scripts/install_core.sh reconcile "$t" || true
    # Re-audit the single tool to reflect updated status inline
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
done

# Python utilities (managed via pipx): prompt individually if outdated/missing
for t in pip pipx poetry httpie semgrep black; do
  if [ -z "$(json_bool "$t" is_up_to_date)" ]; then
    ICON="$(json_field "$t" state_icon)"
    CURR="$(json_field "$t" installed)"
    LATE="$(json_field "$t" latest_upstream)"
    URL="$(json_field "$t" latest_url)"
    if prompt_action "${ICON} $t" "$CURR" "$(json_field "$t" installed_method)" "$(osc8 "$URL" "$LATE")" "$(json_field "$t" upstream_method)" "$t"; then
      # Capture version before installation
      local before_ver="$CURR"
      local before_path="$(command -v "$t" 2>/dev/null || echo)"

      if command -v uv >/dev/null 2>&1; then
        uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
      else
        "$ROOT"/scripts/install_tool.sh uv reconcile || true
        if command -v uv >/dev/null 2>&1; then
          uv tool install --force --upgrade "$t" >/dev/null 2>&1 || true
        else
          if command -v pipx >/dev/null 2>&1; then
            pipx upgrade "$t" >/dev/null 2>&1 || pipx install "$t" >/dev/null 2>&1 || true
          else
            if [ "$t" = pip ]; then
              python3 -m pip install --user -U pip >/dev/null 2>&1 || true
            elif [ "$t" = pipx ]; then
              python3 -m pip install --user -U pipx >/dev/null 2>&1 || true
            else
              python3 -m pip install --user -U "$t" >/dev/null 2>&1 || true
            fi
          fi
        fi
      fi

      # Re-audit and show result
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
      local after_ver="$(json_field "$t" installed)"
      local after_method="$(json_field "$t" installed_method)"
      local after_path="$(json_field "$t" installed_path_selected)"

      printf "[%s] before: %s\n" "$t" "${before_ver:-<none>}"
      printf "[%s] after:  %s\n" "$t" "${after_ver:-<none>}"
      printf "[%s] path:   %s\n" "$t" "${after_path:-<not found>}"
    fi
  fi
done

# Docker CLI client
DK_ICON="$(json_field docker state_icon)"
DK_CURR="$(json_field docker installed)"
DK_LATEST="$(json_field docker latest_upstream)"
DK_URL="$(json_field docker latest_url)"
DK_METHOD="$(json_field docker installed_method)"
if [ -n "$(json_bool docker is_up_to_date)" ] && [ -n "$DK_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$DK_ICON" "Docker CLI"
  printf "    installed: %s via %s\n" "${DK_CURR:-<none>}" "$DK_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$DK_URL" "${DK_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${DK_ICON} Docker CLI (client)" "$DK_CURR" "$DK_METHOD" "$(osc8 "$DK_URL" "$DK_LATEST")" "$DK_METHOD" docker; then
    echo "Note: This updates the Docker CLI client. Docker Engine (server) is managed separately."
    echo "      If using Docker Desktop, the engine is updated via Docker Desktop updates."
    "$ROOT"/scripts/install_tool.sh docker || true
  fi
fi

# Docker Compose (plugin)
DC_ICON="$(json_field docker-compose state_icon)"
DC_CURR="$(json_field docker-compose installed)"
DC_LATEST="$(json_field docker-compose latest_upstream)"
DC_URL="$(json_field docker-compose latest_url)"
DC_METHOD="$(json_field docker-compose installed_method)"
if [ -n "$(json_bool docker-compose is_up_to_date)" ] && [ -n "$DC_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$DC_ICON" "Docker Compose"
  printf "    installed: %s via %s\n" "${DC_CURR:-<none>}" "$DC_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$DC_URL" "${DC_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${DC_ICON} Docker Compose" "$DC_CURR" "$DC_METHOD" "$(osc8 "$DC_URL" "$DC_LATEST")" "$DC_METHOD" docker-compose; then
    echo "Note: Docker Compose v2 is bundled as Docker plugin; ensure Docker is up to date."
  fi
fi

# AWS CLI (ask if missing or outdated)
AWS_ICON="$(json_field aws state_icon)"
AWS_CURR="$(json_field aws installed)"
AWS_LATEST="$(json_field aws latest_upstream)"
AWS_URL="$(json_field aws latest_url)"
AWS_METHOD="$(json_field aws installed_method)"
if [ -n "$(json_bool aws is_up_to_date)" ] && [ -n "$AWS_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$AWS_ICON" "AWS CLI"
  printf "    installed: %s via %s\n" "${AWS_CURR:-<none>}" "$AWS_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$AWS_URL" "${AWS_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${AWS_ICON} AWS CLI" "$AWS_CURR" "$AWS_METHOD" "$(osc8 "$AWS_URL" "$AWS_LATEST")" "$AWS_METHOD" aws; then
    "$ROOT"/scripts/install_tool.sh aws || true
  fi
fi

# kubectl
K8S_ICON="$(json_field kubectl state_icon)"
K8S_CURR="$(json_field kubectl installed)"
K8S_LATEST="$(json_field kubectl latest_upstream)"
K8S_URL="$(json_field kubectl latest_url)"
K8S_METHOD="$(json_field kubectl installed_method)"
if [ -n "$(json_bool kubectl is_up_to_date)" ] && [ -n "$K8S_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$K8S_ICON" "kubectl"
  printf "    installed: %s via %s\n" "${K8S_CURR:-<none>}" "$K8S_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$K8S_URL" "${K8S_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${K8S_ICON} kubectl" "$K8S_CURR" "$K8S_METHOD" "$(osc8 "$K8S_URL" "$K8S_LATEST")" "$K8S_METHOD" kubectl; then
    "$ROOT"/scripts/install_tool.sh kubectl || true
  fi
fi

# Terraform
TF_ICON="$(json_field terraform state_icon)"
TF_CURR="$(json_field terraform installed)"
TF_LATEST="$(json_field terraform latest_upstream)"
TF_URL="$(json_field terraform latest_url)"
TF_METHOD="$(json_field terraform installed_method)"
if [ -n "$(json_bool terraform is_up_to_date)" ] && [ -n "$TF_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$TF_ICON" "Terraform"
  printf "    installed: %s via %s\n" "${TF_CURR:-<none>}" "$TF_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$TF_URL" "${TF_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${TF_ICON} Terraform" "$TF_CURR" "$TF_METHOD" "$(osc8 "$TF_URL" "$TF_LATEST")" "$TF_METHOD" terraform; then
    "$ROOT"/scripts/install_tool.sh terraform || true
  fi
fi

# Ansible
ANS_ICON="$(json_field ansible state_icon)"
ANS_CURR="$(json_field ansible installed)"
ANS_LATEST="$(json_field ansible latest_upstream)"
ANS_URL="$(json_field ansible latest_url)"
ANS_METHOD="$(json_field ansible installed_method)"
if [ -n "$(json_bool ansible is_up_to_date)" ] && [ -n "$ANS_CURR" ]; then
  printf "\n"
  printf "==> %s %s\n" "$ANS_ICON" "Ansible"
  printf "    installed: %s via %s\n" "${ANS_CURR:-<none>}" "$ANS_METHOD"
  printf "    target:    %s (same)\n" "$(osc8 "$ANS_URL" "${ANS_LATEST:-<unknown>}")"
  printf "    up-to-date; skipping.\n"
else
  if prompt_action "${ANS_ICON} Ansible" "$ANS_CURR" "$ANS_METHOD" "$(osc8 "$ANS_URL" "$ANS_LATEST")" "$ANS_METHOD" ansible; then
    "$ROOT"/scripts/install_tool.sh ansible update || true
    AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" cli_audit.py || true)"
  fi
fi

echo
echo "All done. Re-run: make audit"



