#!/usr/bin/env bash
# Catalog query functions for reading tool metadata
# Assumes: Scripts are run from app root, catalog is at $ROOT/catalog

# Get all tools with a specific tag
catalog_get_tools_by_tag() {
  local tag="$1"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq required for catalog operations" >&2
    return 1
  fi

  for json in "$catalog_dir"/*.json; do
    [ -f "$json" ] || continue
    if jq -e --arg tag "$tag" '.tags[]? | select(. == $tag)' "$json" >/dev/null 2>&1; then
      jq -r '.name' "$json"
    fi
  done
}

# Get all available tags
catalog_get_all_tags() {
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq required for catalog operations" >&2
    return 1
  fi

  find "$catalog_dir" -name "*.json" -exec jq -r '.tags[]? // empty' {} \; 2>/dev/null | sort -u
}

# Check if tool has catalog entry
catalog_has_tool() {
  local tool="$1"
  local catalog_dir="$ROOT/catalog"
  [ -f "$catalog_dir/$tool.json" ]
}

# Get tool property from catalog
catalog_get_property() {
  local tool="$1"
  local property="$2"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq required for catalog operations" >&2
    return 1
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    jq -r ".$property // empty" "$json"
  fi
}

# Get pinned version for a specific version cycle (multi-version tools)
# Reads from user-local pins file, not catalog
catalog_get_pinned_version() {
  local tool="$1"
  local version_cycle="$2"

  # Source pins library if not already loaded
  if ! type pins_get_cycle &>/dev/null; then
    local lib_dir
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    . "$lib_dir/pins.sh"
  fi

  pins_get_cycle "$tool" "$version_cycle"
}

# Get pin for a single-version tool
# Reads from user-local pins file, not catalog
catalog_get_pin() {
  local tool="$1"

  # Source pins library if not already loaded
  if ! type pins_get &>/dev/null; then
    local lib_dir
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    . "$lib_dir/pins.sh"
  fi

  pins_get "$tool"
}

# Check if tool is deprecated
catalog_is_deprecated() {
  local tool="$1"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    return 1
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    local deprecated="$(jq -r '.deprecated // false' "$json")"
    [ "$deprecated" = "true" ]
  else
    return 1
  fi
}

# Get the tool that supersedes a deprecated tool
catalog_get_superseded_by() {
  local tool="$1"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    return
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    jq -r '.superseded_by // empty' "$json"
  fi
}

# Get deprecation message for a tool
catalog_get_deprecation_message() {
  local tool="$1"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    return
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    jq -r '.deprecation_message // empty' "$json"
  fi
}

# Get all deprecated tools
catalog_get_deprecated_tools() {
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq required for catalog operations" >&2
    return 1
  fi

  for json in "$catalog_dir"/*.json; do
    [ -f "$json" ] || continue
    if jq -e '.deprecated == true' "$json" >/dev/null 2>&1; then
      jq -r '.name' "$json"
    fi
  done
}

# Check if tool's runtime requirements are satisfied
# Returns 0 if all required tools are available, 1 otherwise
catalog_check_requires() {
  local tool="$1"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    return 0  # Can't check, assume OK
  fi

  local json="$catalog_dir/$tool.json"
  [ -f "$json" ] || return 0

  local requires
  requires="$(jq -r '.requires[]? // empty' "$json" 2>/dev/null)"
  [ -z "$requires" ] && return 0

  for req in $requires; do
    # Check if the required tool's binary is available
    local req_binary
    if [ -f "$catalog_dir/$req.json" ]; then
      req_binary="$(jq -r '.binary_name // .name' "$catalog_dir/$req.json")"
    else
      req_binary="$req"
    fi
    if ! command -v "$req_binary" >/dev/null 2>&1; then
      # Also check nvm for node (nvm may not be loaded in this shell)
      if [ "$req_binary" = "node" ] && [ -d "${NVM_DIR:-$HOME/.nvm}/versions/node" ]; then
        local nvm_nodes
        nvm_nodes="$(ls "${NVM_DIR:-$HOME/.nvm}/versions/node/" 2>/dev/null | head -1)"
        if [ -n "$nvm_nodes" ]; then
          continue  # node available via nvm
        fi
      fi
      echo "$req"
      return 1
    fi
  done
  return 0
}

# Get guide-specific metadata from catalog
catalog_get_guide_property() {
  local tool="$1"
  local property="$2"
  local default="${3:-}"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    echo "$default"
    return
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    local value="$(jq -r ".guide.$property // empty" "$json")"
    if [ -n "$value" ] && [ "$value" != "null" ]; then
      echo "$value"
    else
      echo "$default"
    fi
  else
    echo "$default"
  fi
}
