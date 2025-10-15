#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/install_strategy.sh"

TOOL="aws"
before="$(command -v aws >/dev/null 2>&1 && aws --version || true)"

# Determine installation directory based on INSTALL_STRATEGY
BIN_DIR="$(get_install_dir aws)"
get_install_cmd "$BIN_DIR"
mkdir -p "$BIN_DIR" 2>/dev/null || true

TMP="$(mktemp -d)"
cd "$TMP"
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip

# AWS installer supports --bin-dir and --install-dir options
# Use --bin-dir to control where symlinks are placed
./aws/install --bin-dir "$BIN_DIR" --install-dir "${BIN_DIR%/bin}/aws-cli" --update 2>/dev/null || \
  ./aws/install --bin-dir "$BIN_DIR" --install-dir "${BIN_DIR%/bin}/aws-cli" 2>/dev/null || true
after="$(command -v aws >/dev/null 2>&1 && aws --version || true)"
path="$(command -v aws 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


