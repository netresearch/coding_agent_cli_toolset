#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

TOOL="ansible"
before="$(command -v ansible >/dev/null 2>&1 && ansible --version | head -n1 || true)"
# Prefer uv tool for installation; remove/purge OS-level packages first
apt_purge_if_present ansible ansible-core ansible-base python3-ansible python3-ansible-core python3-ansible-base || true
BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
# Remove conflicting user installs that shadow pipx shims
if command -v python3 >/dev/null 2>&1; then
  if python3 -m pip show --user ansible >/dev/null 2>&1 || python3 -m pip show --user ansible-core >/dev/null 2>&1; then
    python3 -m pip uninstall -y ansible ansible-core || true
  fi
fi
rm -f "$HOME/.local/bin/ansible" "$HOME/.local/bin/ansible-community" "$HOME/.local/bin/ansible-playbook" >/dev/null 2>&1 || true

if command -v uv >/dev/null 2>&1; then
  # Install or upgrade via uv tool
  uv tool install --force --upgrade ansible || true
  # Ensure core CLI shims are present (ansible, ansible-playbook, etc.)
  uv tool install --force --upgrade ansible-core || true
  # Clean up pipx install if present to avoid shim conflicts
  if have pipx; then pipx uninstall ansible >/dev/null 2>&1 || true; fi
else
  if have pipx; then
    pipx upgrade ansible || pipx install ansible || true
    pipx ensurepath || true
    # Ensure ansible-community shim points to pipx venv binary
    EXPECTED_BIN="$HOME/.local/share/pipx/venvs/ansible/bin/ansible-community"
    if [ -e "$BIN_DIR/ansible-community" ]; then
      target="$(readlink -f "$BIN_DIR/ansible-community" 2>/dev/null || echo)"
      if [ "$target" != "$EXPECTED_BIN" ] && [ -x "$EXPECTED_BIN" ]; then
        rm -f "$BIN_DIR/ansible-community" || true
        ln -sf "$EXPECTED_BIN" "$BIN_DIR/ansible-community" || true
      fi
    fi
    # Recreate missing pipx shims for ansible commands if they were removed
    VENV_BIN="$HOME/.local/share/pipx/venvs/ansible/bin"
    for name in ansible ansible-playbook ansible-community; do
      src="$VENV_BIN/$name"
      dest="$BIN_DIR/$name"
      if [ -x "$src" ]; then
        current="$(readlink -f "$dest" 2>/dev/null || echo)"
        if [ ! -e "$dest" ] || [ "$current" != "$src" ]; then
          ln -sf "$src" "$dest" || true
        fi
      fi
    done
  else
    if have python3; then python3 -m pip install --user -U ansible || true; else if have apt-get; then sudo apt-get update && sudo apt-get install -y ansible; fi; fi
  fi
fi
after="$(command -v ansible >/dev/null 2>&1 && ansible --version | head -n1 || true)"
path="$(command -v ansible 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


