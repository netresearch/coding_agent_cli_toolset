#!/usr/bin/env bash
# pins.sh - Shared library for reading/writing version pins
#
# Pins are stored in a user-local JSON file, not in git-tracked catalog files.
# Format:
#   Single-version tools: {"tool": "version"} or {"tool": "never"}
#   Multi-version tools:  {"tool": {"cycle": "version"}}
#
# Usage:
#   source "$DIR/lib/pins.sh"
#   pins_set "prettier" "3.5.0"
#   pins_get "prettier"               # → "3.5.0"
#   pins_set_cycle "python" "3.12" "never"
#   pins_get_cycle "python" "3.12"    # → "never"

PINS_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/cli-audit/pins.json"

# Ensure the pins file exists (creates directory and empty JSON object if needed)
_pins_ensure_file() {
    if [ ! -f "$PINS_FILE" ]; then
        mkdir -p "$(dirname "$PINS_FILE")"
        echo '{}' > "$PINS_FILE"
    fi
}

# Get pin for a single-version tool
# Returns: version string, "never", or empty if not pinned
pins_get() {
    local tool="$1"
    [ ! -f "$PINS_FILE" ] && return 0
    local val
    val="$(jq -r --arg t "$tool" '.[$t] // empty' "$PINS_FILE" 2>/dev/null)"
    # If the value is an object (multi-version), return empty — use pins_get_cycle instead
    if [ -n "$val" ] && echo "$val" | jq -e 'type == "object"' >/dev/null 2>&1; then
        return 0
    fi
    echo "$val"
}

# Get pin for a specific version cycle of a multi-version tool
# Returns: version string, "never", or empty if not pinned
pins_get_cycle() {
    local tool="$1"
    local cycle="$2"
    [ ! -f "$PINS_FILE" ] && return 0
    jq -r --arg t "$tool" --arg c "$cycle" '.[$t][$c] // empty' "$PINS_FILE" 2>/dev/null
}

# Set pin for a single-version tool
pins_set() {
    local tool="$1"
    local version="$2"
    _pins_ensure_file
    local tmp
    tmp=$(mktemp)
    jq --arg t "$tool" --arg v "$version" '.[$t] = $v' "$PINS_FILE" > "$tmp"
    mv "$tmp" "$PINS_FILE"
}

# Set pin for a specific version cycle of a multi-version tool
pins_set_cycle() {
    local tool="$1"
    local cycle="$2"
    local version="$3"
    _pins_ensure_file
    local tmp
    tmp=$(mktemp)
    jq --arg t "$tool" --arg c "$cycle" --arg v "$version" \
        '.[$t] = ((.[$t] // {}) + {($c): $v})' "$PINS_FILE" > "$tmp"
    mv "$tmp" "$PINS_FILE"
}

# Remove pin for a single-version tool
pins_remove() {
    local tool="$1"
    [ ! -f "$PINS_FILE" ] && return 0
    local tmp
    tmp=$(mktemp)
    jq --arg t "$tool" 'del(.[$t])' "$PINS_FILE" > "$tmp"
    mv "$tmp" "$PINS_FILE"
}

# Remove pin for a specific version cycle, cleaning up empty objects
pins_remove_cycle() {
    local tool="$1"
    local cycle="$2"
    [ ! -f "$PINS_FILE" ] && return 0
    local tmp
    tmp=$(mktemp)
    jq --arg t "$tool" --arg c "$cycle" \
        'del(.[$t][$c]) | if .[$t] == {} then del(.[$t]) else . end' \
        "$PINS_FILE" > "$tmp"
    mv "$tmp" "$PINS_FILE"
}

# Clear all pins
pins_reset_all() {
    _pins_ensure_file
    echo '{}' > "$PINS_FILE"
}

# List all pins (dump JSON for display)
pins_list() {
    [ ! -f "$PINS_FILE" ] && { echo '{}'; return 0; }
    jq '.' "$PINS_FILE" 2>/dev/null || echo '{}'
}
