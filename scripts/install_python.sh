#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

ACTION="${1:-install}"

ensure_uv() { :; }

ensure_python_distro() {
  if ! have python3 && have apt-get; then sudo apt-get update && sudo apt-get install -y python3 python3-pip; fi
}

# Create/update a default dev venv using uv if available
uv_setup_default_venv() {
  if command -v uv >/dev/null 2>&1; then
    # Select Python spec: default to latest 3.x; allow override via UV_PYTHON_SPEC (e.g., 3.13)
    local PY_SPEC
    PY_SPEC="${UV_PYTHON_SPEC:-3}"
    # If a fully pinned X.Y.Z isn't available, fall back to X.Y
    local ALT_SPEC
    ALT_SPEC="$PY_SPEC"
    case "$PY_SPEC" in
      *.*.*) ALT_SPEC="${PY_SPEC%.*}" ;;
      *) ALT_SPEC="$PY_SPEC" ;;
    esac
    # Resolve the exact interpreter path, allowing pre-releases when stable is not yet available
    local PY_PATH
    PY_PATH="$(uv python find "$PY_SPEC" 2>/dev/null || true)"
    if [ -z "$PY_PATH" ]; then
      PY_PATH="$(uv python find "$ALT_SPEC" 2>/dev/null || true)"
    fi
    if [ -z "$PY_PATH" ]; then
      uv python install "$PY_SPEC" >/dev/null 2>&1 || uv python install "$ALT_SPEC" >/dev/null 2>&1 || true
      PY_PATH="$(uv python find "$PY_SPEC" 2>/dev/null || true)"
      if [ -z "$PY_PATH" ]; then
        PY_PATH="$(uv python find "$ALT_SPEC" 2>/dev/null || true)"
      fi
    fi
    mkdir -p "$HOME/.venvs" || true
    # Recreate the default venv to ensure it uses the requested interpreter
    if [ -n "$PY_PATH" ] && [ -x "$PY_PATH" ]; then
      uv venv --python "$PY_PATH" --clear "$HOME/.venvs/dev" >/dev/null 2>&1 || true
    else
      uv venv -p "$PY_SPEC" --clear "$HOME/.venvs/dev" >/dev/null 2>&1 || \
        uv venv -p "$ALT_SPEC" --clear "$HOME/.venvs/dev" >/dev/null 2>&1 || \
        { rm -rf "$HOME/.venvs/dev" >/dev/null 2>&1 || true; uv venv "$HOME/.venvs/dev" >/dev/null 2>&1 || true; }
    fi
  else
    ensure_python_distro
    python3 -m venv "$HOME/.venvs/dev" >/dev/null 2>&1 || true
  fi
}

# Install or upgrade Python CLI tools using uv (fallback pipx/apt)
install_or_update_py_cli() {
  local cmd="$1" # install|upgrade
  local tools=(black isort flake8 bandit httpie pre-commit poetry semgrep)
  if command -v uv >/dev/null 2>&1; then
    for p in "${tools[@]}"; do
      # Prefer uv tool (pipx replacement)
      if [ "$cmd" = install ]; then
        uv tool install -q "$p" >/dev/null 2>&1 || true
      else
        uv tool upgrade -q "$p" >/dev/null 2>&1 || uv tool install -q "$p" >/dev/null 2>&1 || true
      fi
    done
  else
    ensure_python_distro
    python3 -m pip install --user -U pip >/dev/null 2>&1 || true
    python3 -m pip install --user -U pipx >/dev/null 2>&1 || true
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
    for p in "${tools[@]}"; do
      if [ "$cmd" = install ]; then
        pipx install "$p" >/dev/null 2>&1 || true
      else
        pipx upgrade "$p" >/dev/null 2>&1 || pipx install "$p" >/dev/null 2>&1 || true
      fi
    done
  fi
}

install_py_stack() {
  ensure_uv || true
  uv_setup_default_venv || true
  install_or_update_py_cli install
}

update_py_stack() {
  ensure_uv || true
  uv_setup_default_venv || true
  install_or_update_py_cli upgrade
}

uninstall_py_tools() {
  local tools=(black isort flake8 bandit httpie pre-commit poetry semgrep)
  if command -v uv >/dev/null 2>&1; then
    for p in "${tools[@]}"; do uv tool uninstall "$p" >/dev/null 2>&1 || true; done
  else
    for p in "${tools[@]}"; do pipx uninstall "$p" >/dev/null 2>&1 || true; done
  fi
}

reconcile_py_tools() { install_py_stack; }

case "$ACTION" in
  install) install_py_stack ;;
  update) update_py_stack ;;
  uninstall) uninstall_py_tools ;;
  reconcile) reconcile_py_tools ;;
  *) echo "Usage: $0 {install|update|uninstall|reconcile}" ; exit 2 ;;
esac

echo "python: $ACTION complete (or attempted)."


