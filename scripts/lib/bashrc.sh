#!/usr/bin/env bash
# Idempotent management of delimited "managed blocks" in a shell rc file.
# Shared helper: insert a block once, remove it cleanly without disturbing the
# surrounding user content.
#
# Delimiters are derived from a short, stable MARKER_ID so multiple independent
# blocks can coexist in the same file.

# bashrc_ensure_block FILE MARKER_ID CONTENT
#   Append the delimited block if (and only if) it is not already present.
bashrc_ensure_block() {
  local file="$1" id="$2" content="$3"
  local begin="# >>> cli-audit: ${id} >>>"
  local end="# <<< cli-audit: ${id} <<<"
  [ -f "$file" ] || touch "$file"
  if grep -qF "$begin" "$file" 2>/dev/null; then
    return 0
  fi
  {
    printf '\n%s\n' "$begin"
    printf '%s\n' "$content"
    printf '%s\n' "$end"
  } >>"$file"
}

# bashrc_remove_block FILE MARKER_ID
#   Delete only the delimited region; leave all other lines untouched.
#   Hardened against an unbalanced block: if the begin marker has no matching
#   end marker (manual tampering / a write interrupted mid-block), the region is
#   restored intact rather than deleting everything that follows the begin
#   marker.
bashrc_remove_block() {
  local file="$1" id="$2"
  local begin="# >>> cli-audit: ${id} >>>"
  local end="# <<< cli-audit: ${id} <<<"
  [ -f "$file" ] || return 0
  grep -qF "$begin" "$file" 2>/dev/null || return 0
  local tmp
  tmp="$(mktemp)"
  awk -v b="$begin" -v e="$end" '
    !skip && $0 == b { skip=1; buf=$0 ORS; next }
    skip {
      buf = buf $0 ORS
      if ($0 == e) { skip=0; buf="" }
      next
    }
    { print }
    END { if (skip) printf "%s", buf }
  ' "$file" >"$tmp"
  cat "$tmp" >"$file"
  rm -f "$tmp"
}
