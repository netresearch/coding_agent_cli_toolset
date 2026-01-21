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
catalog_get_pinned_version() {
  local tool="$1"
  local version_cycle="$2"
  local catalog_dir="$ROOT/catalog"

  if ! command -v jq >/dev/null 2>&1; then
    return
  fi

  local json="$catalog_dir/$tool.json"
  if [ -f "$json" ]; then
    jq -r --arg cycle "$version_cycle" '.pinned_versions[$cycle] // empty' "$json"
  fi
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
