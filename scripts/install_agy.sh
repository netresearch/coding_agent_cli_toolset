#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
# Dedicated installer for the Google Antigravity CLI (agy)
# Uses the official installer; updates go through the CLI's own updater
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-install}"
INSTALLER_URL="https://antigravity.google/cli/install.sh"
BIN_DIR="$HOME/.local/bin"
AGY_BIN="$BIN_DIR/agy"
# curl may only use https, including on redirects
CURL_HTTPS_ONLY=(--proto '=https')

# The agy to act on: ~/.local/bin/agy (where the official installer puts it),
# else the first agy on PATH (an install with --dir or by another method)
find_agy() {
    if [ -x "$AGY_BIN" ]; then
        printf '%s\n' "$AGY_BIN"
    else
        command -v agy 2>/dev/null || true
    fi
}

get_current_version() {
    local bin
    bin="$(find_agy)"
    [ -n "$bin" ] || return 0
    # macOS has no timeout(1)
    if command -v timeout >/dev/null 2>&1; then
        timeout 2 "$bin" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
    else
        "$bin" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true
    fi
}

# True when a PATH entry is ~/.local/bin, also written with a trailing slash
# or through a symlinked parent
bin_dir_on_path() {
    local entry resolved_bin="" resolved
    local -a entries
    [ -d "$BIN_DIR" ] && resolved_bin="$(cd "$BIN_DIR" && pwd -P)"
    IFS=: read -r -a entries <<<"$PATH"
    for entry in "${entries[@]}"; do
        [ -n "$entry" ] || continue
        [ "${entry%/}" = "$BIN_DIR" ] && return 0
        if [ -n "$resolved_bin" ] && [ -d "$entry" ]; then
            resolved="$(cd "$entry" && pwd -P)" || continue
            [ "$resolved" = "$resolved_bin" ] && return 0
        fi
    done
    return 1
}

warn_path_line() {
    echo "[agy] Warning: $1; the installer may add a PATH line to ~/.bashrc and ~/.profile" >&2
}

# Run the official installer. It downloads the binary, checks its SHA512
# against the release manifest and then runs `agy install`, which appends a
# PATH line to ~/.bashrc and ~/.profile. When ~/.local/bin is already on PATH
# that line only moves the directory to the front, so pass --skip-path.
install_native() {
    if ! command -v curl >/dev/null 2>&1; then
        echo "[agy] curl is required for the official installer" >&2
        return 1
    fi
    local work_dir installer_script
    work_dir="$(mktemp -d "${TMPDIR:-/tmp}/cli-audit-agy.XXXXXX")" || return 1
    installer_script="$work_dir/install.sh"

    if ! curl "${CURL_HTTPS_ONLY[@]}" -fsSL "$INSTALLER_URL" -o "$installer_script"; then
        echo "[agy] Failed to download $INSTALLER_URL" >&2
        rm -rf "$work_dir"
        return 1
    fi

    if bin_dir_on_path; then
        # The anchor is the line that hands over to `agy install`; if Google
        # changes it, install without the patch rather than fail
        if ! grep -qF '"$BINARY_PATH" install || true' "$installer_script"; then
            warn_path_line "installer layout changed"
        # sed without -i: BSD and GNU sed disagree on its argument
        elif ! { sed 's/"\$BINARY_PATH" install || true/"\$BINARY_PATH" install --skip-path || true/' \
            "$installer_script" >"$installer_script.patched" &&
            mv "$installer_script.patched" "$installer_script"; }; then
            warn_path_line "could not patch the installer"
        fi
    fi

    local rc=0
    bash "$installer_script" || rc=$?
    rm -rf "$work_dir"
    return "$rc"
}

refresh_agy_snapshot() {
    if [ -f "$DIR/lib/install_strategy.sh" ]; then
        . "$DIR/lib/install_strategy.sh"
        refresh_snapshot "agy" 2>/dev/null || true
    fi
}

report() {
    local before="$1" after path
    hash -r 2>/dev/null || true
    after="$(get_current_version)"
    path="$(find_agy)"
    printf "[%s] before: %s\n" "agy" "${before:-<none>}"
    printf "[%s] after:  %s\n" "agy" "${after:-<none>}"
    if [ -n "$path" ]; then printf "[%s] path:   %s\n" "agy" "$path"; fi
}

install_agy() {
    local before existing
    before="$(get_current_version)"
    existing="$(find_agy)"

    if [ -n "$existing" ]; then
        echo "[agy] Already installed at $existing; it updates itself (run: agy update)" >&2
    elif ! install_native; then
        echo "[agy] Error: installation failed" >&2
        echo "[agy] Install manually: curl -fsSL $INSTALLER_URL | bash" >&2
        return 1
    fi

    report "$before"
    refresh_agy_snapshot
}

upgrade_agy() {
    local before existing
    existing="$(find_agy)"
    if [ -z "$existing" ]; then
        echo "[agy] Not installed, running install..." >&2
        install_agy
        return $?
    fi
    before="$(get_current_version)"
    if ! "$existing" update </dev/null; then
        echo "[agy] Error: '$existing update' failed" >&2
        return 1
    fi
    report "$before"
    refresh_agy_snapshot
}

uninstall_agy() {
    if [ ! -e "$AGY_BIN" ] && [ ! -L "$AGY_BIN" ]; then
        echo "[agy] Not installed at $AGY_BIN" >&2
        return 0
    fi
    rm -f "$AGY_BIN"
    hash -r 2>/dev/null || true
    echo "[agy] Removed $AGY_BIN" >&2
    echo "[agy] Left in place: settings and sign-in in ~/.config/antigravity, and any" >&2
    echo "[agy] 'Added by Antigravity CLI installer' PATH line in ~/.bashrc and ~/.profile" >&2
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "$ACTION" in
        install) install_agy ;;
        update|upgrade) upgrade_agy ;;
        uninstall) uninstall_agy ;;
        reconcile) install_agy ;;
        *) echo "Usage: $0 {install|update|upgrade|uninstall|reconcile}" ; exit 2 ;;
    esac
fi
