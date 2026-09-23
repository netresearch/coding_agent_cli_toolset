#!/usr/bin/env bash
# Run shell commands that come from the catalog: `version_command` and
# `bash_completion`. Both are shell code stored as JSON strings -- review them
# as code. They are not parsed here: the catalog's real entries use pipes,
# `&&`, `$(command -v ...)` and quoted `;`, so any first-word allowlist would
# reject legitimate tools while `&&` walked past it. What is refused is only
# what no entry needs and a reviewer easily misses inside a JSON string: a
# newline and a backtick.
#
# Sets no shell options, so any script or library may source it.

catalog_command_is_safe() {
  case "$1" in
    *$'\n'* | *'`'*) return 1 ;;
  esac
  return 0
}

# run_catalog_command CMD [TIMEOUT_SECONDS]
# Runs CMD in a child shell, so it cannot overwrite the caller's variables,
# bounded by timeout(1) or gtimeout(1) where either exists. A temporary
# PATH=... prefix on the call reaches the command. Default timeout: 5 s.
run_catalog_command() {
  local cmd="${1:-}" secs="${2:-5}"
  [ -n "$cmd" ] || return 1
  if ! catalog_command_is_safe "$cmd"; then
    echo "# Refusing catalog command containing a newline or backtick: ${cmd%%$'\n'*}" >&2
    return 1
  fi
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" bash -c "$cmd"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" bash -c "$cmd"
  else
    bash -c "$cmd"
  fi
}
