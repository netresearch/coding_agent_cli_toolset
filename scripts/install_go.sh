#!/usr/bin/env bash
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

TOOL="go"
before="$(have go && go version || true)"
if have brew; then
  if have go; then brew upgrade go || true; else brew install go; fi
else
  echo "Please install Go from https://go.dev/dl/"
fi
after="$(have go && go version || true)"
path="$(command -v go 2>/dev/null || true)"
printf "[%s] before: %s\n" "$TOOL" "${before:-<none>}"
printf "[%s] after:  %s\n"  "$TOOL" "${after:-<none>}"
if [ -n "$path" ]; then printf "[%s] path:   %s\n" "$TOOL" "$path"; fi


