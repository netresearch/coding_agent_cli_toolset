#!/usr/bin/env bash
# Install or remove a tool's bash completion (catalog-driven).
# Usage: install_completion.sh TOOL [install|remove]
#        install_completion.sh --all
#
#   install  Ensure the bash-completion framework, then install TOOL's
#            completion (no-op if TOOL declares no bash_completion).
#   remove   Remove TOOL's installed completion file.
#   --all    Backfill completions for every catalog tool that declares one;
#            tools that are not installed are skipped automatically (their
#            generator command fails validation).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/completion.sh
. "$DIR/lib/completion.sh"

# Bulk backfill mode.
if [ "${1:-}" = "--all" ]; then
  command -v jq >/dev/null 2>&1 || { echo "Error: jq required" >&2; exit 1; }
  ensure_bash_completion_framework || true
  installed=0
  skipped=0
  for f in "$(completion_catalog_dir)"/*.json; do
    [ -f "$f" ] || continue
    jq -e '.bash_completion' "$f" >/dev/null 2>&1 || continue
    tool="$(basename "$f" .json)"
    if install_completion "$tool" >/dev/null 2>&1; then
      echo "[completion] $tool: installed"
      installed=$((installed + 1))
    else
      skipped=$((skipped + 1))
    fi
  done
  echo "[completion] done: $installed installed, $skipped skipped (not installed or no valid completion)"
  exit 0
fi

TOOL="${1:-}"
ACTION="${2:-install}"

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL [install|remove]  |  $0 --all" >&2
  exit 1
fi

# Validate tool name to prevent path traversal
if [[ "$TOOL" == *"/"* ]] || [[ "$TOOL" == *".."* ]]; then
  echo "Error: Invalid tool name: $TOOL" >&2
  exit 1
fi

case "$ACTION" in
  install)
    ensure_bash_completion_framework || true
    install_completion "$TOOL"
    ;;
  remove)
    remove_completion "$TOOL"
    ;;
  *)
    echo "Usage: $0 TOOL [install|remove]" >&2
    exit 1
    ;;
esac
