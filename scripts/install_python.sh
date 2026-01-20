#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

ACTION="${1:-install}"

ensure_uv() { :; }

ensure_python_distro() {
  if ! have python3 && have apt-get; then sudo apt-get update && sudo apt-get install -y python3 python3-pip; fi
}

# Get current Python version managed by uv
get_uv_python_version() {
  if command -v uv >/dev/null 2>&1; then
    # Get the highest installed Python version
    uv python list --only-installed 2>/dev/null | grep -E "^cpython-[0-9]" | head -1 | sed 's/cpython-\([0-9.]*\).*/\1/' || true
  fi
}

# Get version of a specific Python (e.g., python3.13)
get_specific_python_version() {
  local major_minor="$1"  # e.g., "3.13" or "3.13.11"
  local short_ver="${major_minor%.*}"  # e.g., "3.13" from "3.13.11"

  # If it's a full version like "3.13.11", extract major.minor
  if [[ "$short_ver" == *.* ]]; then
    : # Already major.minor
  else
    short_ver="$major_minor"
  fi

  local binary="python${short_ver}"

  # Try to find and run the specific binary
  if command -v "$binary" >/dev/null 2>&1; then
    "$binary" --version 2>&1 | sed 's/Python //' || true
  else
    # Try via uv python list
    if command -v uv >/dev/null 2>&1; then
      uv python list --only-installed 2>/dev/null | grep -E "^cpython-${short_ver}" | head -1 | sed 's/cpython-\([0-9.]*\).*/\1/' || true
    fi
  fi
}

# Get the binary path for a specific Python version
get_specific_python_path() {
  local major_minor="$1"
  local short_ver="${major_minor%.*}"
  if [[ "$short_ver" == *.* ]]; then
    : # Already major.minor
  else
    short_ver="$major_minor"
  fi

  local binary="python${short_ver}"
  command -v "$binary" 2>/dev/null || true
}

# Install or upgrade Python via uv
uv_install_python() {
  local PY_SPEC="${UV_PYTHON_SPEC:-3}"

  echo "[python] Installing Python $PY_SPEC via uv..." >&2

  # Install the requested Python version
  if ! uv python install "$PY_SPEC" 2>&1; then
    # If exact version fails, try without patch version
    local ALT_SPEC="${PY_SPEC%.*}"
    if [ "$ALT_SPEC" != "$PY_SPEC" ]; then
      echo "[python] Trying $ALT_SPEC..." >&2
      uv python install "$ALT_SPEC" 2>&1 || true
    fi
  fi
}

# Create/update a default dev venv using uv if available
uv_setup_default_venv() {
  if command -v uv >/dev/null 2>&1; then
    local PY_SPEC="${UV_PYTHON_SPEC:-3}"
    local ALT_SPEC="$PY_SPEC"
    case "$PY_SPEC" in
      *.*.*) ALT_SPEC="${PY_SPEC%.*}" ;;
    esac

    # Find the interpreter
    local PY_PATH
    PY_PATH="$(uv python find "$PY_SPEC" 2>/dev/null || uv python find "$ALT_SPEC" 2>/dev/null || true)"

    mkdir -p "$HOME/.venvs" || true
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
  local before after path
  local PY_SPEC="${UV_PYTHON_SPEC:-}"

  # Use specific version detection if a version is specified
  if [ -n "$PY_SPEC" ] && [[ "$PY_SPEC" == *.* ]]; then
    before="$(get_specific_python_version "$PY_SPEC")"
  else
    before="$(get_uv_python_version)"
  fi

  ensure_uv || true
  uv_install_python || true
  uv_setup_default_venv || true
  install_or_update_py_cli install

  # Use specific version detection for after check
  if [ -n "$PY_SPEC" ] && [[ "$PY_SPEC" == *.* ]]; then
    after="$(get_specific_python_version "$PY_SPEC")"
    path="$(get_specific_python_path "$PY_SPEC")"
  else
    after="$(get_uv_python_version)"
    path="$(command -v python3 2>/dev/null || true)"
  fi

  printf "[%s] before: %s\n" "python" "${before:-<none>}"
  printf "[%s] after:  %s\n" "python" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "python" "$path"; fi

  refresh_snapshot "python"
}

update_py_stack() {
  local before after path
  local PY_SPEC="${UV_PYTHON_SPEC:-}"

  # Use specific version detection if a version is specified
  if [ -n "$PY_SPEC" ] && [[ "$PY_SPEC" == *.* ]]; then
    before="$(get_specific_python_version "$PY_SPEC")"
  else
    before="$(get_uv_python_version)"
  fi

  ensure_uv || true
  uv_install_python || true
  uv_setup_default_venv || true
  install_or_update_py_cli upgrade

  # Use specific version detection for after check
  if [ -n "$PY_SPEC" ] && [[ "$PY_SPEC" == *.* ]]; then
    after="$(get_specific_python_version "$PY_SPEC")"
    path="$(get_specific_python_path "$PY_SPEC")"
  else
    after="$(get_uv_python_version)"
    path="$(command -v python3 2>/dev/null || true)"
  fi

  printf "[%s] before: %s\n" "python" "${before:-<none>}"
  printf "[%s] after:  %s\n" "python" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "python" "$path"; fi

  refresh_snapshot "python"
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


