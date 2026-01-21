#!/usr/bin/env bash
# cleanup.sh - Interactive guide for removing installed tools
set -euo pipefail
trap '' PIPE

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
CLI="${PYTHON:-python3}"

# Load catalog query functions
. "$DIR/lib/catalog.sh"

echo "Gathering installed tools from snapshot..."
AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

# JSON helper
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

# Category definitions
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

# Process a single tool
process_tool() {
  local tool="$1"

  # Get tool info
  local installed="$(json_field "$tool" installed)"
  local method="$(json_field "$tool" installed_method)"

  # Skip if not installed
  [ -z "$installed" ] && return 0

  # Determine catalog tool name
  local catalog_tool="$tool"
  if [[ "$tool" == *"@"* ]]; then
    catalog_tool="${tool%%@*}"
  fi

  local description="$(catalog_get_property "$catalog_tool" description)"

  printf "\n==> %s\n" "$tool"
  [ -n "$description" ] && printf "    %s\n" "$description"
  printf "    installed: %s via %s\n" "$installed" "${method:-unknown}"
  printf "    Options:\n"
  printf "      K = Keep (default)\n"
  printf "      r = Remove/uninstall\n"

  local ans=""
  if [ -t 0 ]; then
    read -r -p "Keep or remove? [K/r] " ans || true
  elif [ -r /dev/tty ]; then
    read -r -p "Keep or remove? [K/r] " ans </dev/tty || true
  fi

  case "$ans" in
    [Rr])
      printf "    Removing %s...\n" "$tool"
      "$ROOT"/scripts/install_tool.sh "$catalog_tool" uninstall || true

      # Re-audit
      CLI_AUDIT_JSON=1 CLI_AUDIT_COLLECT=1 CLI_AUDIT_MERGE=1 "$CLI" audit.py "$tool" >/dev/null 2>&1 || true
      AUDIT_JSON="$(cd "$ROOT" && CLI_AUDIT_JSON=1 CLI_AUDIT_RENDER=1 "$CLI" audit.py || true)"

      local still_installed="$(json_field "$tool" installed)"
      if [ -z "$still_installed" ]; then
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

# Build list of installed tools by category
declare -A CATEGORY_TOOLS

# Parse AUDIT_JSON to get installed tools
while read -r tool; do
  [ -z "$tool" ] && continue

  installed="$(json_field "$tool" installed)"
  [ -z "$installed" ] && continue

  # Determine catalog tool name
  catalog_name="$tool"
  if [[ "$tool" == *"@"* ]]; then
    catalog_name="${tool%%@*}"
  fi

  if catalog_has_tool "$catalog_name"; then
    category="$(catalog_get_property "$catalog_name" category)"
    category="${category:-general}"
    CATEGORY_TOOLS[$category]="${CATEGORY_TOOLS[$category]:-} $tool"
  fi
done < <(echo "$AUDIT_JSON" | "$CLI" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for item in data:
        print(item.get('tool', ''))
except: pass
")

# Count total installed tools
total_installed=0
for cat in "${!CATEGORY_TOOLS[@]}"; do
  count=$(echo ${CATEGORY_TOOLS[$cat]} | wc -w)
  ((total_installed += count)) || true
done

if [ $total_installed -eq 0 ]; then
  echo ""
  echo "No installed tools found in snapshot."
  echo "Run 'make update' first to collect tool information."
  exit 0
fi

echo ""
echo "Found $total_installed installed tools across ${#CATEGORY_TOOLS[@]} categories."
echo ""

# Process by category
AUTO_YES_ALL=""
for category in $(printf '%s\n' "${!CATEGORY_TOOLS[@]}" | while read c; do echo "${CATEGORY_ORDER[$c]:-99} $c"; done | sort -n | awk '{print $2}'); do
  tools="${CATEGORY_TOOLS[$category]}"
  [ -z "$tools" ] && continue

  tool_count=$(echo $tools | wc -w)
  icon="${CATEGORY_ICON[$category]:-📦}"
  desc="${CATEGORY_DESC[$category]:-$category}"

  printf "\n"
  printf "================================================================================\n"
  printf "%s %s (%d installed)\n" "$icon" "$desc" "$tool_count"
  printf "================================================================================\n"

  if [ "$AUTO_YES_ALL" != "1" ]; then
    printf "  Tools: %s\n" "$(echo $tools | tr ' ' ', ')"
    printf "  Review this category? [Y/n/a=all/s=skip-all] "

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

  for tool in $tools; do
    process_tool "$tool"
  done
done

echo ""
echo "Cleanup complete. Re-run: make audit"
