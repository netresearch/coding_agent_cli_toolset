#!/usr/bin/env bash
# Dispatch tool@cycle make targets (e.g. make uninstall-node@24) to the
# dedicated multi-version installer with the tool's version env var set.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Test hook: point at stubbed installers
INSTALLER_DIR="${INSTALLER_DIR:-$DIR}"

SPEC="${1:-}"
ACTION="${2:-install}"

if [ -z "$SPEC" ] || [ "${SPEC#*@}" = "$SPEC" ]; then
  echo "Usage: $0 TOOL@CYCLE [install|update|uninstall]" >&2
  echo "Example: $0 node@24 uninstall" >&2
  exit 2
fi

TOOL="${SPEC%%@*}"
CYCLE="${SPEC#*@}"

if [ -z "$TOOL" ] || [ -z "$CYCLE" ]; then
  echo "Error: Invalid spec '$SPEC' (expected TOOL@CYCLE, e.g. node@24)" >&2
  exit 2
fi

case "$TOOL" in
  node)
    NODE_VERSION="$CYCLE" exec "$INSTALLER_DIR/install_node.sh" "$ACTION"
    ;;
  ruby)
    RUBY_VERSION="$CYCLE" exec "$INSTALLER_DIR/install_ruby.sh" "$ACTION"
    ;;
  go)
    GO_VERSION="$CYCLE" exec "$INSTALLER_DIR/install_go.sh" "$ACTION"
    ;;
  python)
    UV_PYTHON_SPEC="$CYCLE" exec "$INSTALLER_DIR/install_python.sh" "$ACTION"
    ;;
  *)
    echo "Error: '$TOOL' has no version-cycle support (supported: node, ruby, go, python)" >&2
    exit 1
    ;;
esac
