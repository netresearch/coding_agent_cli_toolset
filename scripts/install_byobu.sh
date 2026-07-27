#!/usr/bin/env bash
# Install the newest stable Byobu tag from upstream source.
# Distribution packages commonly lag behind the upstream release.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/install_strategy.sh
. "$DIR/lib/install_strategy.sh"

TOOL="byobu"
INSTALL_PREFIX="${INSTALL_PREFIX:-${HOME}/.local}"
GITHUB_REPO="dustinkirkland/byobu"
MANIFEST_DIR="$INSTALL_PREFIX/share/cli-audit/manifests"
MANIFEST_FILE="$MANIFEST_DIR/byobu.txt"
BUILD_LOG=""
BUILD_TMPDIR=""

cleanup() {
    if [ -n "$BUILD_TMPDIR" ] && [ -d "$BUILD_TMPDIR" ]; then
        rm -rf "$BUILD_TMPDIR"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

show_build_failure() {
    local step="$1"
    echo "[$TOOL] Error: $step failed" >&2
    if [ -n "$BUILD_LOG" ] && [ -f "$BUILD_LOG" ]; then
        echo "[$TOOL] Last build output:" >&2
        tail -n 40 "$BUILD_LOG" >&2
    fi
}

require_commands() {
    local command_name
    local missing=()

    for command_name in curl jq tar sort make autoreconf automake autoconf; do
        command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
    done

    if [ "${#missing[@]}" -gt 0 ]; then
        echo "[$TOOL] Error: Missing build commands: ${missing[*]}" >&2
        return 1
    fi
}

get_installed_version() {
    local installed_binary="$INSTALL_PREFIX/bin/byobu"
    if [ -x "$installed_binary" ]; then
        awk -F= '$1 == "VERSION" { print $2; exit }' "$installed_binary"
    fi
}

get_target_version() {
    local tags_json=""
    local version=""

    if command -v gh >/dev/null 2>&1; then
        tags_json="$(gh api "repos/$GITHUB_REPO/tags?per_page=100" 2>/dev/null || true)"
    fi
    if [ -z "$tags_json" ]; then
        tags_json="$(curl --proto '=https' --proto-redir '=https' -fsSL \
            --retry 3 --retry-delay 1 --connect-timeout 10 \
            -H "Accept: application/vnd.github+json" \
            -H "User-Agent: cli-audit" \
            "https://api.github.com/repos/$GITHUB_REPO/tags?per_page=100")"
    fi

    version="$(printf '%s' "$tags_json" |
        jq -r '.[].name' |
        grep -E '^[0-9]+([.][0-9]+)+$' |
        sort -V |
        tail -1)"
    printf '%s' "$version"
}

remove_manifest_files() {
    local relative_path

    if [ ! -f "$MANIFEST_FILE" ]; then
        return 0
    fi

    while IFS= read -r relative_path; do
        if [ -n "$relative_path" ]; then
            rm -f "$INSTALL_PREFIX/$relative_path"
        fi
    done <"$MANIFEST_FILE"
    rm -f "$MANIFEST_FILE"
}

install_byobu() {
    local version="${1:-}"
    local before=""
    local after=""
    local archive=""
    local url=""
    local src_dir=""
    local stage_dir=""
    local installed_binary="$INSTALL_PREFIX/bin/byobu"

    require_commands

    if [ -z "$version" ]; then
        echo "[$TOOL] Fetching latest stable tag..." >&2
        version="$(get_target_version)"
    fi
    if ! grep -Eq '^[0-9]+([.][0-9]+)+$' <<<"$version"; then
        echo "[$TOOL] Error: Invalid stable version: ${version:-<none>}" >&2
        return 1
    fi

    before="$(get_installed_version)"
    BUILD_TMPDIR="$(mktemp -d)"
    BUILD_LOG="$BUILD_TMPDIR/build.log"
    archive="$BUILD_TMPDIR/byobu-$version.tar.gz"
    stage_dir="$BUILD_TMPDIR/stage"
    url="https://github.com/$GITHUB_REPO/archive/refs/tags/${version}.tar.gz"

    echo "[$TOOL] Downloading $url..." >&2
    if ! curl --proto '=https' --proto-redir '=https' -fL \
        --retry 3 --retry-delay 1 --connect-timeout 10 \
        "$url" -o "$archive"; then
        echo "[$TOOL] Error: Failed to download $url" >&2
        return 1
    fi
    if ! tar -xzf "$archive" -C "$BUILD_TMPDIR"; then
        echo "[$TOOL] Error: Invalid source archive: $url" >&2
        return 1
    fi

    src_dir="$(find "$BUILD_TMPDIR" -maxdepth 1 -type d -name 'byobu-*' | head -1)"
    if [ -z "$src_dir" ]; then
        echo "[$TOOL] Error: Could not find source directory in archive" >&2
        return 1
    fi

    cd "$src_dir"
    if ! ./autogen.sh >"$BUILD_LOG" 2>&1; then
        show_build_failure "autogen"
        return 1
    fi
    if ! ./configure --prefix="$INSTALL_PREFIX" --disable-trustmux >>"$BUILD_LOG" 2>&1; then
        show_build_failure "configure"
        return 1
    fi
    if ! make -j"$(nproc)" >>"$BUILD_LOG" 2>&1; then
        show_build_failure "build"
        return 1
    fi
    if ! make install DESTDIR="$stage_dir" >>"$BUILD_LOG" 2>&1; then
        show_build_failure "staged install"
        return 1
    fi

    mkdir -p "$INSTALL_PREFIX" "$MANIFEST_DIR"
    remove_manifest_files
    if ! cp -a "$stage_dir$INSTALL_PREFIX/." "$INSTALL_PREFIX/" >>"$BUILD_LOG" 2>&1; then
        show_build_failure "install"
        return 1
    fi
    find "$stage_dir$INSTALL_PREFIX" \( -type f -o -type l \) -printf '%P\n' |
        sort >"$MANIFEST_FILE"

    cd /
    if [ -x "$installed_binary" ]; then
        after="$(get_installed_version)"
    fi
    if [ "$after" != "$version" ]; then
        echo "[$TOOL] Error: Installed binary reports '${after:-<none>}', expected '$version'" >&2
        return 1
    fi

    printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
    printf "[%s] after:  %s\n" "$TOOL" "$after"
    printf "[%s] path:   %s\n" "$TOOL" "$installed_binary"
    refresh_snapshot "$TOOL"
}

case "${1:-install}" in
    install|update)
        install_byobu "${2:-}"
        ;;
    uninstall)
        echo "[$TOOL] Removing user-local installation" >&2
        remove_manifest_files
        hash -r 2>/dev/null || true
        ;;
    *)
        echo "Usage: $0 [install|update|uninstall] [version]" >&2
        exit 1
        ;;
esac
