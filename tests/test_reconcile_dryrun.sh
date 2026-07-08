#!/usr/bin/env bash
# Guards the safety-critical reconcile invariants at the shell/CLI boundary:
#   - the dry-run make target must NEVER pass --apply (no removals)
#   - the real target must pass --apply
#   - the CLI requires an explicit tool or --all
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
cd "$ROOT"

pass=0
fail=0
check() { # desc, condition-exit-code
  if [ "$2" -eq 0 ]; then echo "  PASS: $1"; pass=$((pass + 1));
  else echo "  FAIL: $1"; fail=$((fail + 1)); fi
}

echo "=== Test: reconcile-all-dry-run never applies ==="
dryrun_recipe="$(grep -A1 '^reconcile-all-dry-run:' Makefile.d/user.mk | tail -1)"
echo "$dryrun_recipe" | grep -q -- '--reconcile'; check "dry-run uses --reconcile" $?
echo "$dryrun_recipe" | grep -q -- '--all'; check "dry-run uses --all" $?
if echo "$dryrun_recipe" | grep -q -- '--apply'; then check "dry-run must NOT use --apply" 1; else check "dry-run must NOT use --apply" 0; fi

echo "=== Test: reconcile-all applies ==="
apply_recipe="$(grep -A1 '^reconcile-all:' Makefile.d/user.mk | tail -1)"
echo "$apply_recipe" | grep -q -- '--apply'; check "reconcile-all uses --apply" $?

echo "=== Test: CLI contract ==="
"$PYTHON" audit.py --reconcile >/dev/null 2>&1; rc=$?
[ "$rc" -ne 0 ]; check "reconcile without tool/--all exits non-zero" $?

"$PYTHON" audit.py --apply >/dev/null 2>&1; rc=$?
[ "$rc" -ne 0 ]; check "reconcile-only flags without --reconcile exit non-zero" $?

"$PYTHON" audit.py --help 2>&1 | grep -q -- '--reconcile'
check "--reconcile listed in --help" $?

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
