#!/usr/bin/env bash
# Generic installer for package manager tools
# Installs tools via system package managers (apt, brew, etc.)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

TOOL="${1:-}"
if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME" >&2
  exit 1
fi

# Validate tool name to prevent path traversal
if [[ "$TOOL" == *"/"* ]] || [[ "$TOOL" == *".."* ]]; then
  echo "Error: Invalid tool name: $TOOL" >&2
  exit 1
fi

CATALOG_FILE="$DIR/../catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Catalog file not found: $CATALOG_FILE" >&2
  exit 1
fi

# Parse catalog
BINARY_NAME="$(jq -r '.binary_name // .name' "$CATALOG_FILE")"
# Support both 'packages' and 'package_managers' field names
PACKAGES="$(jq -r '.packages // .package_managers // {}' "$CATALOG_FILE")"
NOTES="$(jq -r '.notes // empty' "$CATALOG_FILE")"
VERSION_CMD="$(jq -r '.version_command // empty' "$CATALOG_FILE")"
PPA="$(jq -r '.ppa // empty' "$CATALOG_FILE")"

# Handle version-specific binary names (e.g., php8.3, go1.24)
VERSIONED_BINARY="$BINARY_NAME"
if [ -n "${PHP_VERSION:-}" ] && [ "$TOOL" = "php" ]; then
  VERSIONED_BINARY="php${PHP_VERSION}"
fi
if [ -n "${GO_VERSION:-}" ] && [ "$TOOL" = "go" ]; then
  VERSIONED_BINARY="go${GO_VERSION}"
fi

# Print the packages owning the first of the given files that dpkg knows,
# one per line. Parses `dpkg -S`: skips "diversion by X from/to:" and
# "local diversion" lines, splits "a, b: /path", drops ":arch" suffixes.
dpkg_owners() {
  local file line
  for file in "$@"; do
    [ -n "$file" ] || continue
    line="$(LC_ALL=C dpkg -S "$file" 2>/dev/null | grep -vE '^(local )?diversion ' | head -1 || true)"
    [ -n "$line" ] || continue
    line="${line%%: /*}"
    printf '%s\n' "$line" | tr ',' '\n' | sed 's/^ *//; s/:.*$//'
    return 0
  done
}

# Get current version (use versioned binary if specified)
get_version() {
  local bin="$1"
  if [ -n "$VERSION_CMD" ]; then
    eval "$VERSION_CMD" 2>/dev/null || true
  elif command -v "$bin" >/dev/null 2>&1; then
    timeout 2 "$bin" --version </dev/null 2>&1 | head -1 || true
  fi
}

before="$(get_version "$VERSIONED_BINARY")"

# Check if tool is already available (e.g., comes with runtime)
if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  if [ -n "$NOTES" ] && echo "$NOTES" | grep -q "comes with\|bundled with"; then
    # Tool is already available and comes bundled
    after="$before"
    path="$(command -v "$BINARY_NAME" 2>/dev/null || true)"
    printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
    printf "[%s] after:  %s\n" "$TOOL" "${after:-<none>}"
    if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi
    printf "[%s] note:   %s\n" "$TOOL" "Already available (bundled with runtime)"

    # Refresh snapshot to record current version
    refresh_snapshot "$TOOL"
    exit 0
  fi
fi

# Install via appropriate package manager
installed=false
# true only when the package manager itself ran without error; a failed
# install (dpkg lock, refused sudo, no network) must not read as "no newer
# version available"
pm_ok=false

if have brew; then
  pkg="$(echo "$PACKAGES" | jq -r '.brew // empty')"
  if [ "$pkg" != "null" ] && [ -n "$pkg" ]; then
    if brew install "$pkg" || brew upgrade "$pkg"; then pm_ok=true; fi
    installed=true
  fi
fi

if ! $installed && have apt-get; then
  pkg="$(echo "$PACKAGES" | jq -r '.apt // empty')"
  if [ "$pkg" != "null" ] && [ -n "$pkg" ]; then
    # Add PPA if specified (for latest versions on Ubuntu/Debian)
    ppa_added=false
    if [ -n "$PPA" ] && command -v add-apt-repository >/dev/null 2>&1; then
      if ! grep -rq "$PPA" /etc/apt/sources.list.d/ 2>/dev/null; then
        echo "[$TOOL] Adding PPA: ppa:$PPA" >&2
        sudo add-apt-repository -y "ppa:$PPA" || true
        ppa_added=true  # add-apt-repository already runs apt-get update
      fi
    fi

    # Handle version-specific packages (e.g., PHP_VERSION=8.3 -> php8.3-cli)
    if [ -n "${PHP_VERSION:-}" ] && [ "$TOOL" = "php" ]; then
      # Replace generic php packages with version-specific ones
      # e.g., "php php-cli php-mbstring" -> "php8.3 php8.3-cli php8.3-mbstring"
      pkg="$(echo "$pkg" | sed "s/php-/php${PHP_VERSION}-/g; s/^php /php${PHP_VERSION} /; s/ php / php${PHP_VERSION} /g")"
      echo "[$TOOL] Installing PHP ${PHP_VERSION}: $pkg" >&2
    fi

    # Skip apt-get update if PPA was just added (add-apt-repository already updated)
    if ! $ppa_added; then
      sudo apt-get update || true
    fi
    if sudo apt-get install -y $pkg; then
      # Installed version must equal the candidate, or the unchanged version
      # means something else (e.g. another copy earlier on PATH)
      first_pkg="${pkg%% *}"
      pkg_installed="$(dpkg-query -W -f='${Version}' "$first_pkg" 2>/dev/null || true)"
      # apt-cache translates "Candidate:" (German: "Installationskandidat:")
      pkg_candidate="$(LC_ALL=C apt-cache policy "$first_pkg" 2>/dev/null | awk '/Candidate:/ { print $2; exit }' || true)"
      if [ -n "$pkg_installed" ] && [ "$pkg_installed" = "$pkg_candidate" ]; then
        pm_ok=true
      fi
      # The binary on PATH must belong to one of these packages; otherwise
      # another copy shadows the package and "unchanged" says nothing about apt.
      # Versions cannot decide this: universal-ctags 5.9.20210829.0 prints 5.9.0.
      bin_path="$(command -v "$VERSIONED_BINARY" 2>/dev/null || true)"
      bin_real="$(readlink -f "$bin_path" 2>/dev/null || true)"
      owned=false
      if [ -n "$bin_path" ]; then
        # Resolved path first (alternatives: ctags -> ctags-universal), then
        # the PATH entry and /bin/<name>: on merged-/usr systems some packages
        # still record /bin/x while readlink gives /usr/bin/x
        for owner in $(dpkg_owners "$bin_real" "$bin_path" "/bin/${bin_real##*/}"); do
          if [[ " $pkg " == *" $owner "* ]]; then
            owned=true
          fi
        done
      fi
      if ! $owned; then
        pm_ok=false
      fi
    fi
    installed=true
  fi
fi

if ! $installed && have dnf; then
  pkg="$(echo "$PACKAGES" | jq -r '.dnf // .rpm // empty')"
  if [ "$pkg" != "null" ] && [ -n "$pkg" ]; then
    if sudo dnf install -y "$pkg"; then pm_ok=true; fi
    installed=true
  fi
fi

if ! $installed && have pacman; then
  pkg="$(echo "$PACKAGES" | jq -r '.pacman // .arch // empty')"
  if [ "$pkg" != "null" ] && [ -n "$pkg" ]; then
    if sudo pacman -S --noconfirm "$pkg"; then pm_ok=true; fi
    installed=true
  fi
fi

if ! $installed; then
  echo "[$TOOL] No supported package manager found (tried: brew, apt, dnf, pacman)" >&2
  exit 1
fi

# Report (use versioned binary for version-specific installs)
after="$(get_version "$VERSIONED_BINARY")"
path="$(command -v "$VERSIONED_BINARY" 2>/dev/null || true)"

# Display with version suffix if applicable
DISPLAY_NAME="$TOOL"
if [ -n "${PHP_VERSION:-}" ] && [ "$TOOL" = "php" ]; then
  DISPLAY_NAME="php@${PHP_VERSION}"
fi
if [ -n "${GO_VERSION:-}" ] && [ "$TOOL" = "go" ]; then
  DISPLAY_NAME="go@${GO_VERSION}"
fi

printf "[%s] before: %s\n" "$DISPLAY_NAME" "${before:-<none>}"
printf "[%s] after:  %s\n" "$DISPLAY_NAME" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$DISPLAY_NAME" "$path"; fi

# Warn if version didn't change (package manager can't provide newer version)
if $pm_ok && [ -n "$before" ] && [ -n "$after" ] && [ "$before" = "$after" ]; then
  printf "[%s] Note: Package manager has no newer version available\n" "$DISPLAY_NAME" >&2
  # Signal held-back status to callers (guide.sh), so the run is not counted
  # as an upgrade
  marker_dir="${CLI_AUDIT_MARKER_DIR:-/tmp/.cli-audit}"
  mkdir -p "$marker_dir"
  echo "$after" > "$marker_dir/${TOOL}.held-back"
fi

# Refresh snapshot after successful installation
# Need to source install_strategy.sh for refresh_snapshot function
. "$(dirname "${BASH_SOURCE[0]}")/../lib/install_strategy.sh"
refresh_snapshot "$TOOL"
