#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

TOOL="kubectl"
before="$(kubectl version --client --short 2>/dev/null || true)"

# Detect OS and architecture
OS="linux"
case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  armv7l) ARCH="armv7" ;;
  s390x) ARCH="s390x" ;;
  ppc64le) ARCH="ppc64le" ;;
  *) ARCH="amd64" ;;
esac

# Resolve latest stable version from primary and fallback endpoints
LATEST="$(curl -fsSL https://dl.k8s.io/release/stable.txt 2>/dev/null || true)"
if [ -z "$LATEST" ]; then
  LATEST="$(curl -fsSL https://storage.googleapis.com/kubernetes-release/release/stable.txt 2>/dev/null || true)"
fi

# If still empty, do not proceed blindly
if [ -z "$LATEST" ]; then
  printf "[%s] error: unable to resolve latest version from upstream.\n" "$TOOL" >&2
  printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
  printf "[%s] after:  %s\n"  "$TOOL" "<none>"
  path="$(command -v kubectl 2>/dev/null || true)"
  if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi
  exit 1
fi

PRIMARY_URL="https://dl.k8s.io/release/${LATEST}/bin/${OS}/${ARCH}/kubectl"
FALLBACK_URL="https://storage.googleapis.com/kubernetes-release/release/${LATEST}/bin/${OS}/${ARCH}/kubectl"

# Download with retry and fallback
tmpfile="/tmp/kubectl"
rm -f "$tmpfile"
if ! curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 -o "$tmpfile" "$PRIMARY_URL"; then
  curl -fL --retry 3 --retry-delay 1 --connect-timeout 10 -o "$tmpfile" "$FALLBACK_URL"
fi

# Basic validation: ensure file is not empty and looks like ELF/Mach-O
if ! [ -s "$tmpfile" ]; then
  printf "[%s] error: downloaded file is empty from both endpoints.\n" "$TOOL" >&2
  exit 1
fi

chmod +x "$tmpfile"
# Install atomically with proper permissions
sudo install -m 0755 -T "$tmpfile" /usr/local/bin/kubectl

after="$(kubectl version --client --short 2>/dev/null || true)"
path="$(command -v kubectl 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


