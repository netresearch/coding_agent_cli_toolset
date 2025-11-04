#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"

echo "[smoke] Checking 6-column header in table output"
HDR="$($PY "$ROOT_DIR/audit.py" | head -n1 || true)"
IFS='|' read -r c1 c2 c3 c4 c5 c6 <<<"${HDR:-}"
test -n "$c1" && test -n "$c2" && test -n "$c3" && test -n "$c4" && test -n "$c5" && test -n "$c6"

echo "[smoke] Checking JSON fields presence"
JSON="$(CLI_AUDIT_JSON=1 "$PY" "$ROOT_DIR/audit.py" || true)"
export JSON
"$PY" - <<'PY'
import json, os, sys
data = os.environ.get("JSON", "").strip()
arr = json.loads(data) if data else []
if not isinstance(arr, list) or not arr:
    sys.exit(0)
item = arr[0]
required = [
    "tool",
    "installed",
    "installed_method",
    "installed_path_selected",
    "classification_reason_selected",
    "latest_upstream",
    "upstream_method",
    "status",
]
missing = [k for k in required if k not in item]
if missing:
    raise SystemExit(f"missing keys: {missing}")
PY

echo "[smoke] OK"

