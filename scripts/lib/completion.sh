#!/usr/bin/env bash
# Bash-completion installation for cataloged tools.
#
# Catalog-driven: a tool's catalog JSON may declare an optional "bash_completion"
# object with EXACTLY ONE of:
#   { "command": "<shell command that prints a bash completion script to stdout>" }
#   { "source_path": "<file, relative to the tool's clone_path, to copy>" }
#
# Completion scripts are written to the XDG user completions directory, named
# after the tool's COMMAND (binary_name) so the bash-completion framework
# lazy-loads them when that command is tab-completed.

# Resolve this lib's directory and the repo layout.
_COMPLETION_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/bashrc.sh
. "$_COMPLETION_LIB_DIR/bashrc.sh"

completion_dir() {
  printf '%s/bash-completion/completions' "${XDG_DATA_HOME:-$HOME/.local/share}"
}

# completion_catalog_dir -> the catalog directory (overridable for tests via
# CLI_AUDIT_CATALOG_DIR; defaults to the repo catalog).
completion_catalog_dir() {
  printf '%s' "${CLI_AUDIT_CATALOG_DIR:-$_COMPLETION_LIB_DIR/../../catalog}"
}

# _completion_catalog_file TOOL -> path to catalog JSON (echoes nothing if absent).
# Always returns 0: callers capture it in an assignment, and a non-zero status
# there would abort a `set -e` caller before their own "no catalog" guard runs.
_completion_catalog_file() {
  local tool="$1"
  local f
  f="$(completion_catalog_dir)/${tool}.json"
  [ -f "$f" ] || return 0
  printf '%s' "$f"
}

# _completion_name TOOL -> the command name the completion file must be named
# after (binary_name from the catalog, falling back to the tool name).
_completion_name() {
  local tool="$1" catalog="$2" name
  name="$(jq -r '.binary_name // ""' "$catalog" 2>/dev/null)"
  [ -n "$name" ] && [ "$name" != "null" ] && { printf '%s' "$name"; return; }
  printf '%s' "$tool"
}

# _completion_run CMD -> run a generator command, bounded by `timeout` when the
# platform provides one (GNU coreutils; absent from a stock macOS, where
# gtimeout may exist via Homebrew). Falls back to a plain run rather than
# failing, so completion generation still works without coreutils.
_completion_run() {
  local cmd="$1"
  if command -v timeout >/dev/null 2>&1; then
    timeout 30 bash -c "$cmd"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout 30 bash -c "$cmd"
  else
    bash -c "$cmd"
  fi
}

# _completion_looks_valid FILE -> 0 if the file looks like a bash completion
# script. Requires a real completion signature — the `complete` builtin WITH a
# flag (-F/-o/-C/-W/…), a `compgen` call, or a `COMPREPLY` assignment. A bare
# word "complete" in help/scan output is intentionally NOT enough: some tools
# treat an unknown "completion" subcommand as an argument and echo help or even
# run (e.g. a linter scanning a path named "complete"), whose output contains
# the word "complete" but is not a completion script.
_completion_looks_valid() {
  local f="$1"
  [ -s "$f" ] || return 1
  grep -qE 'complete[[:space:]]+-|compgen[[:space:]]|COMPREPLY' "$f"
}

# Ensure the bash-completion framework is present and loadable in interactive
# shells. Best-effort: warns and returns non-zero on failure, never aborts.
ensure_bash_completion_framework() {
  # 1) Ensure the framework files exist (apt, best-effort).
  if [ ! -r /usr/share/bash-completion/bash_completion ] && [ ! -r /etc/bash_completion ]; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "[completion] Installing bash-completion framework..." >&2
      sudo apt-get update -qq 2>/dev/null || true
      sudo apt-get install -y -qq bash-completion 2>/dev/null || {
        echo "[completion] Warning: could not install bash-completion package" >&2
        return 1
      }
    else
      echo "[completion] Warning: bash-completion framework not found and no apt-get" >&2
      return 1
    fi
  fi

  # 2) Ensure interactive shells load it (guarded; no-op if already loaded by
  #    /etc/bash.bashrc). The block sources the framework only when its
  #    initializer function is not yet defined.
  # The interactive guard is essential: the distro bash_completion script has no
  # guard of its own and enables `extglob`/`progcomp` at top level. Without
  # `$- == *i*` a non-interactive shell that sources ~/.bashrc (e.g. `ssh host
  # somescript`) would silently get extended globbing, changing how patterns
  # like !(…) / @(…) parse. Also skipped in POSIX mode, as distro rc files do.
  local content
  content='if [[ $- == *i* ]] && ! shopt -oq posix && ! declare -F _init_completion >/dev/null 2>&1; then
  for _f in /usr/share/bash-completion/bash_completion /etc/bash_completion; do
    [ -r "$_f" ] && { . "$_f"; break; }
  done
  unset _f
fi'
  bashrc_ensure_block "$HOME/.bashrc" "bash-completion" "$content"
}

# install_completion TOOL
#   Install the tool's bash completion into the XDG completions dir.
#   No-op (returns 0) when the tool declares no bash_completion.
#   Best-effort: returns non-zero on failure but never aborts a caller.
install_completion() {
  local tool="$1"
  command -v jq >/dev/null 2>&1 || { echo "[completion] jq required" >&2; return 1; }

  local catalog
  catalog="$(_completion_catalog_file "$tool")"
  [ -n "$catalog" ] || return 0

  local bc
  bc="$(jq -c '.bash_completion // empty' "$catalog" 2>/dev/null)"
  [ -n "$bc" ] || return 0

  local cmd src
  cmd="$(jq -r '.bash_completion.command // ""' "$catalog" 2>/dev/null)"
  src="$(jq -r '.bash_completion.source_path // ""' "$catalog" 2>/dev/null)"

  local tmp
  tmp="$(mktemp)"

  if [ -n "$cmd" ] && [ "$cmd" != "null" ]; then
    # Generate to stdout. stderr is discarded so tool noise never lands in the
    # completion file; validation below rejects anything that isn't completion.
    # stdin MUST be detached: a generator that falls through to reading stdin
    # would otherwise hang the whole install indefinitely, since stdin is
    # inherited from make/the user's terminal. </dev/null is portable and does
    # the real work; the timeout is extra insurance for a generator that blocks
    # on something else, and is only used where available (macOS ships no
    # GNU `timeout` — hard-coding it made every generator fail there).
    _completion_run "$cmd" >"$tmp" 2>/dev/null </dev/null || true
  elif [ -n "$src" ] && [ "$src" != "null" ]; then
    local clone_path base full
    clone_path="$(jq -r '.clone_path // ""' "$catalog" 2>/dev/null)"
    clone_path="${clone_path/#\~/$HOME}"
    base="$clone_path"
    if [ -z "$base" ]; then
      echo "[completion] $tool: source_path needs a clone_path in catalog" >&2
      rm -f "$tmp"
      return 1
    fi
    full="$base/$src"
    if [ -f "$full" ]; then
      cp "$full" "$tmp"
    fi
  else
    rm -f "$tmp"
    return 0
  fi

  if ! _completion_looks_valid "$tmp"; then
    echo "[completion] $tool: generated output is not a valid completion; skipping" >&2
    rm -f "$tmp"
    return 1
  fi

  local name dir
  name="$(_completion_name "$tool" "$catalog")"
  dir="$(completion_dir)"
  # Both steps must be checked: the trailing echo would otherwise mask a failure
  # behind a 0 return, reporting "installed" with nothing written.
  if ! mkdir -p "$dir" 2>/dev/null; then
    echo "[completion] $tool: cannot create $dir" >&2
    rm -f "$tmp"
    return 1
  fi
  if ! mv "$tmp" "$dir/$name" 2>/dev/null; then
    echo "[completion] $tool: failed to install into $dir" >&2
    rm -f "$tmp"
    return 1
  fi
  echo "[completion] $tool: installed completion ($name)" >&2
}

# remove_completion TOOL
remove_completion() {
  local tool="$1"
  local catalog name dir
  catalog="$(_completion_catalog_file "$tool")"
  [ -n "$catalog" ] || return 0
  name="$(_completion_name "$tool" "$catalog")"
  dir="$(completion_dir)"
  if [ -f "$dir/$name" ]; then
    rm -f "$dir/$name"
    echo "[completion] $tool: removed completion ($name)" >&2
  fi
}

# post_install_completion TOOL
#   Convenience hook for the install lifecycle: ensure the framework once, then
#   install the tool's completion. Entirely best-effort; always returns 0 so it
#   can never fail the surrounding tool install.
post_install_completion() {
  local tool="$1"
  local catalog bc
  catalog="$(_completion_catalog_file "$tool")"
  [ -n "$catalog" ] || return 0
  bc="$(jq -c '.bash_completion // empty' "$catalog" 2>/dev/null)"
  [ -n "$bc" ] || return 0
  ensure_bash_completion_framework || true
  install_completion "$tool" || true
  return 0
}
