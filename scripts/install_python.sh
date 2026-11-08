#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
. "$DIR/lib/common.sh"
# shellcheck source=scripts/lib/install_strategy.sh
. "$DIR/lib/install_strategy.sh"

ACTION="${1:-install}"

ensure_python_distro() {
  if ! have python3 && have apt-get; then sudo apt-get update && sudo apt-get install -y python3 python3-pip; fi
}

# Reduce a version spec to major.minor: "3.14.10" -> "3.14", "3.14" -> "3.14".
python_minor() {
  case "$1" in
    *.*.*) echo "${1%.*}" ;;
    *) echo "$1" ;;
  esac
}

# Print "<version> <path>" for each uv-managed CPython of one series ("3.14",
# or "" for all), highest version first. The path prefers uv's executable link
# (~/.local/bin/python3.14) over the install directory. Free-threaded builds
# and pre-releases are skipped. PATH is not consulted: an activated virtualenv
# shadows python3.14 there and reports the interpreter it was created from.
uv_managed_pythons() {
  local minor="$1"
  command -v uv >/dev/null 2>&1 || return 0
  uv python list --only-installed --managed-python 2>/dev/null \
    | awk -v pre="cpython-${minor:+$minor.}" '
        index($1, pre) == 1 && $1 ~ /^cpython-[0-9]+\.[0-9]+\.[0-9]+-/ {
          v = $1; sub(/^cpython-/, "", v); sub(/-.*/, "", v)
          if (!(v in path) || $3 == "->") path[v] = $2
        }
        END { for (v in path) print v, path[v] }' \
    | sort -k1,1Vr || true
}

# Get the highest Python version managed by uv
get_uv_python_version() {
  uv_managed_pythons "" | head -1 | cut -d' ' -f1
}

# Get the installed version of one Python series (spec "3.13" or "3.13.11")
get_specific_python_version() {
  local short_ver
  short_ver="$(python_minor "$1")"
  if command -v uv >/dev/null 2>&1; then
    uv_managed_pythons "$short_ver" | head -1 | cut -d' ' -f1
  elif command -v "python${short_ver}" >/dev/null 2>&1; then
    "python${short_ver}" --version 2>&1 | sed 's/Python //' || true
  fi
}

# Get the binary path for one Python series (spec "3.13" or "3.13.11")
get_specific_python_path() {
  local short_ver
  short_ver="$(python_minor "$1")"
  if command -v uv >/dev/null 2>&1; then
    uv_managed_pythons "$short_ver" | head -1 | cut -d' ' -f2
  else
    command -v "python${short_ver}" 2>/dev/null || true
  fi
}

# Install or upgrade Python via uv
uv_install_python() {
  local PY_SPEC="${UV_PYTHON_SPEC:-3}"

  echo "[python] Installing Python $PY_SPEC via uv..." >&2

  case "$PY_SPEC" in
    *.*.*) ;;
    *.*)
      # Any installed 3.14.x satisfies "3.14", so a plain install keeps the old
      # patch. --upgrade moves the series to the newest patch uv can download.
      if uv python install --upgrade "$PY_SPEC" 2>&1; then
        return 0
      fi
      echo "[python] Warning: Could not install Python $PY_SPEC via uv" >&2
      return 1
      ;;
    *)
      if uv python install "$PY_SPEC" 2>&1; then
        return 0
      fi
      echo "[python] Warning: Could not install Python $PY_SPEC via uv" >&2
      return 1
      ;;
  esac

  if uv python install "$PY_SPEC" 2>&1; then
    return 0
  fi

  # uv cannot download this exact patch (its download list ships inside the uv
  # binary). Install the newest lower patch it can download instead, and stop
  # before reaching the patch that is already installed.
  local minor="${PY_SPEC%.*}" patch="${PY_SPEC##*.}"
  local installed installed_patch=-1 p
  installed="$(get_specific_python_version "$minor")"
  if [[ "$installed" =~ ^[0-9]+\.[0-9]+\.([0-9]+)$ ]]; then
    installed_patch="${BASH_REMATCH[1]}"
  fi
  if [[ "$patch" =~ ^[0-9]+$ ]]; then
    for ((p = patch - 1; p > installed_patch; p--)); do
      echo "[python] Version $minor.$((p + 1)) not available via uv, trying $minor.$p..." >&2
      if uv python install "$minor.$p" 2>&1; then
        echo "[python] Note: Installed $minor.$p (target $PY_SPEC not yet available in uv)" >&2
        return 0
      fi
    done
  fi

  if [ -n "$installed" ]; then
    echo "[python] No patch between installed $installed and target $PY_SPEC is available via uv; a newer uv may have it (make upgrade-uv)" >&2
  else
    echo "[python] Warning: Could not install Python $PY_SPEC via uv" >&2
  fi
  return 1
}

# Create the default dev venv (~/.venvs/dev) when it is missing or broken.
# A working venv is left alone: it can hold packages the user installed, and a
# run for one series (UV_PYTHON_SPEC=3.15) must not move it to that series.
# uv builds it on the series link (cpython-3.14-...), so patch upgrades reach
# it without a rebuild. It is rebuilt only when its interpreter no longer runs.
uv_setup_default_venv() {
  local venv="$HOME/.venvs/dev"
  if "$venv/bin/python" -c '' >/dev/null 2>&1; then
    return 0
  fi
  mkdir -p "$HOME/.venvs" || true
  if command -v uv >/dev/null 2>&1; then
    local series
    series="$(python_minor "$(get_uv_python_version)")"
    uv venv --clear --managed-python --python "${series:-3}" "$venv" >/dev/null 2>&1 || true
  else
    ensure_python_distro
    python3 -m venv --clear "$venv" >/dev/null 2>&1 || true
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
        # Upgrade only tools that are already installed. A failed upgrade
        # commonly means that the tool was deliberately removed; installing it
        # here would undo `make uninstall-<tool>`.
        uv tool upgrade -q "$p" >/dev/null 2>&1 || true
      fi
    done
  else
    ensure_python_distro
    python3 -m pip install --only-binary :all: --user -U pip >/dev/null 2>&1 || true
    python3 -m pip install --only-binary :all: --user -U pipx >/dev/null 2>&1 || true
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
    for p in "${tools[@]}"; do
      if [ "$cmd" = install ]; then
        pipx install "$p" >/dev/null 2>&1 || true
      else
        pipx upgrade "$p" >/dev/null 2>&1 || true
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
    path="$(uv_managed_pythons "" | head -1 | cut -d' ' -f2)"
  fi

  printf "[%s] before: %s\n" "python" "${before:-<none>}"
  printf "[%s] after:  %s\n" "python" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "python" "$path"; fi

  refresh_snapshot "python" || true
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
    path="$(uv_managed_pythons "" | head -1 | cut -d' ' -f2)"
  fi

  printf "[%s] before: %s\n" "python" "${before:-<none>}"
  printf "[%s] after:  %s\n" "python" "${after:-<none>}"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "python" "$path"; fi

  refresh_snapshot "python" || true
}

uninstall_py_tools() {
  local PY_SPEC="${UV_PYTHON_SPEC:-}"

  if [ -n "$PY_SPEC" ]; then
    # Version-specific removal (e.g., UV_PYTHON_SPEC=3.10)
    local short_ver="${PY_SPEC}"
    # Extract major.minor from full version like 3.10.19
    case "$PY_SPEC" in
      *.*.*)  short_ver="${PY_SPEC%.*}" ;;
    esac

    echo "[python] Removing Python $short_ver..." >&2

    # Pre-cache sudo credentials to avoid repeated password prompts
    if have sudo && have apt-get; then
      sudo -v 2>/dev/null || true
    fi

    # Remove via uv if available
    if command -v uv >/dev/null 2>&1; then
      uv python uninstall "$short_ver" 2>/dev/null || true
    fi

    # Remove version-specific apt packages (e.g., python3.10)
    # BUT skip if this version is the system default python3 (dependency of python3 metapackage)
    if have apt-get; then
      local system_py_ver=""
      system_py_ver="$(/usr/bin/python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
      if [ "$short_ver" = "$system_py_ver" ]; then
        echo "[python] Skipping apt removal: python${short_ver} is the system Python (dependency of python3)" >&2
      else
        apt_remove_if_present "python${short_ver}" "python${short_ver}-venv" "python${short_ver}-dev" 2>/dev/null || true
      fi
    fi

    # Remove version-specific brew formula if it exists
    if have brew; then
      brew uninstall "python@${short_ver}" 2>/dev/null || true
    fi

    echo "[python] Python $short_ver removal complete" >&2
  else
    # Full uninstall: remove all CLI tools
    local tools=(black isort flake8 bandit httpie pre-commit poetry semgrep)
    if command -v uv >/dev/null 2>&1; then
      for p in "${tools[@]}"; do uv tool uninstall "$p" >/dev/null 2>&1 || true; done
    else
      for p in "${tools[@]}"; do pipx uninstall "$p" >/dev/null 2>&1 || true; done
    fi
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
