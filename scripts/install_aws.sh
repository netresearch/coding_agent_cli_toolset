#!/usr/bin/env bash
set -euo pipefail

TOOL="aws"
before="$(command -v aws >/dev/null 2>&1 && aws --version || true)"
TMP="$(mktemp -d)"
cd "$TMP"
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip
sudo ./aws/install --update || true
after="$(command -v aws >/dev/null 2>&1 && aws --version || true)"
path="$(command -v aws 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


