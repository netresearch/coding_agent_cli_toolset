#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"
. "$DIR/lib/install_strategy.sh"

OS="linux"
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) ARCH="amd64" ;;
esac

# Determine installation directory based on INSTALL_STRATEGY
BIN_DIR="$(get_install_dir terraform)"
get_install_cmd "$BIN_DIR"
mkdir -p "$BIN_DIR" 2>/dev/null || true

# Prefer installing latest official release from HashiCorp; avoid early exit

before="$(command -v terraform >/dev/null 2>&1 && terraform version 2>/dev/null | head -n1 || true)"

# Remove distro package first so new binary takes precedence
apt_remove_if_present terraform || true

TMP="$(mktemp -d)"

# Get latest version from GitHub releases redirect
LATEST_TAG="$(curl -fsSIL -H "User-Agent: cli-audit" -o /dev/null -w '%{url_effective}' https://github.com/hashicorp/terraform/releases/latest | awk -F'/' '{print $NF}')"
VER="${LATEST_TAG#v}"
if [ -z "$VER" ]; then
  echo "Could not resolve latest Terraform version" >&2
  VER=""
fi

if [ -n "$VER" ]; then
  URL="https://releases.hashicorp.com/terraform/${VER}/terraform_${VER}_${OS}_${ARCH}.zip"
  if curl -fsSL "$URL" -o "$TMP/terraform.zip"; then
    unzip -q "$TMP/terraform.zip" -d "$TMP" || true
    if [ -f "$TMP/terraform" ]; then
      # Install using strategy
      $INSTALL "$TMP/terraform" "$BIN_DIR/terraform"
    fi
  fi
fi

# Fallbacks
if ! command -v terraform >/dev/null 2>&1; then
  if have brew; then brew install terraform || true; fi
fi

after="$(command -v terraform >/dev/null 2>&1 && terraform version 2>/dev/null | head -n1 || true)"
path="$(command -v terraform 2>/dev/null || true)"
printf "[%s] before: %s\n" "terraform" "${before:-<none>}"
printf "[%s] after:  %s\n"  "terraform" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "terraform" "$path"; fi


