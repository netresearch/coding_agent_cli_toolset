#!/usr/bin/env bash
# reset_pins.sh - Remove version pins from ~/.config/cli-audit/pins.json
#
# Default: wipe every pin.
# --stale: only remove pins the user almost certainly doesn't want anymore:
#          patch-level pins where installed != pin and pin is not a
#          cycle-string (i.e. fossil skip-markers and overridden holds).
#          "never" pins and cycle-holds (pin == cycle) are preserved.
#          Tools not present in the snapshot are preserved.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

# Load pin library
. "$DIR/lib/pins.sh"

MODE="all"
DRY_RUN=0
SNAP_FILE="${CLI_AUDIT_SNAPSHOT_FILE:-$ROOT/tools_snapshot.json}"

usage() {
  cat <<EOF
Usage: $0 [--stale] [--dry-run]

  (no flags)   Remove ALL pins.
  --stale      Remove only stale patch-level pins (installed != pin AND
               pin != cycle AND pin != "never"). Reads the current audit
               snapshot ($SNAP_FILE) to decide what "stale" means.
  --dry-run    Print what would be removed without writing.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --stale) MODE="stale" ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [ ! -f "$PINS_FILE" ]; then
  echo "No pins file ($PINS_FILE)."
  exit 0
fi

if [ "$MODE" = "all" ]; then
  current="$(jq -r 'to_entries[] | if (.value | type) == "object" then "\(.key): \(.value | to_entries | map("\(.key)=\(.value)") | join(", "))" else "\(.key): \(.value)" end' "$PINS_FILE" 2>/dev/null || true)"
  if [ -z "$current" ]; then
    echo "No pins found."
    exit 0
  fi
  echo "Resetting all version pins..."
  while IFS= read -r line; do
    echo "  Removing pin: $line"
  done <<< "$current"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "(dry-run, no changes made)"
    exit 0
  fi
  echo ""
  pins_reset_all
  echo "✓ All pins removed"
  echo ""
  echo "All tools will now appear in upgrade prompts."
  exit 0
fi

# --stale mode needs the snapshot.
if [ ! -f "$SNAP_FILE" ]; then
  echo "Snapshot not found at $SNAP_FILE. Run 'make update' first." >&2
  exit 1
fi

# Walk the pins file and decide per-entry. jq does the shape work; the
# loop here formats the decision and emits the updated JSON.
mapfile -t actions < <(
  jq -r --slurpfile snap "$SNAP_FILE" '
    # Build a map (tool_name -> installed) from the snapshot tools array.
    ($snap[0].tools // []) as $tools
    | ([ $tools[] | select(.tool) | {key: .tool, value: (.installed // "")} ] | from_entries) as $installed
    | to_entries[]
    | .key as $tool
    | if (.value | type) == "object" then
        .value | to_entries[] | .key as $cycle | .value as $pin
        | "\($tool)@\($cycle)\t\($cycle)\t\($pin)\t\($installed["\($tool)@\($cycle)"] // "")"
      else
        .key as $name | .value as $pin
        | "\($name)\t\t\($pin)\t\($installed[$name] // "")"
      end
  ' "$PINS_FILE"
)

to_remove=()  # "tool\tcycle" pairs (cycle blank for flat)
to_keep=()
for line in "${actions[@]}"; do
  IFS=$'\t' read -r row_name cycle pin installed <<< "$line"
  tool="${row_name%@*}"
  # Classify.
  if [ "$pin" = "never" ]; then
    to_keep+=("$row_name: PIN:never (kept)")
    continue
  fi
  if [ -n "$cycle" ] && [ "$pin" = "$cycle" ]; then
    to_keep+=("$row_name: CYCLE:$pin (kept)")
    continue
  fi
  if [ -z "$installed" ]; then
    # Nothing installed — pin is intent-to-stay-at-absent; leave it.
    to_keep+=("$row_name: PIN:$pin (kept — not installed)")
    continue
  fi
  if [ "$installed" = "$pin" ]; then
    to_keep+=("$row_name: PIN:$pin (kept — honored)")
    continue
  fi
  # Stale patch-level pin.
  to_remove+=("$row_name: PIN:$pin → installed $installed (removing)")
  if [ -n "$cycle" ]; then
    printf 'REMOVE\t%s\t%s\n' "$tool" "$cycle" >> /tmp/.cli-audit-stale-pins.$$
  else
    printf 'REMOVE\t%s\t\n' "$tool" >> /tmp/.cli-audit-stale-pins.$$
  fi
done

trap 'rm -f /tmp/.cli-audit-stale-pins.$$' EXIT

if [ "${#to_keep[@]}" -gt 0 ]; then
  echo "Preserved:"
  printf '  %s\n' "${to_keep[@]}"
  echo ""
fi

if [ "${#to_remove[@]}" -eq 0 ]; then
  echo "No stale pins found."
  exit 0
fi

echo "Stale pins to remove:"
printf '  %s\n' "${to_remove[@]}"
echo ""

if [ "$DRY_RUN" -eq 1 ]; then
  echo "(dry-run, no changes made)"
  exit 0
fi

if [ ! -s /tmp/.cli-audit-stale-pins.$$ ]; then
  exit 0
fi

while IFS=$'\t' read -r _ tool cycle; do
  if [ -n "$cycle" ]; then
    pins_remove_cycle "$tool" "$cycle"
  else
    pins_remove "$tool"
  fi
done < /tmp/.cli-audit-stale-pins.$$

echo "✓ Removed ${#to_remove[@]} stale pin(s)."
