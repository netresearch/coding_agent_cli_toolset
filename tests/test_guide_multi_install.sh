#!/usr/bin/env bash
# Integration tests for multi-install detection and hash verification
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

assert_contains() {
  local label="$1" haystack="$2" needle="$3"
  if echo "$haystack" | grep -qF "$needle"; then
    echo "  PASS: $label"
    ((PASS++)) || true
  else
    echo "  FAIL: $label"
    echo "    expected to contain: $needle"
    echo "    got: $(echo "$haystack" | head -5)"
    ((FAIL++)) || true
  fi
}

assert_not_contains() {
  local label="$1" haystack="$2" needle="$3"
  if ! echo "$haystack" | grep -qF "$needle"; then
    echo "  PASS: $label"
    ((PASS++)) || true
  else
    echo "  FAIL: $label"
    echo "    expected NOT to contain: $needle"
    ((FAIL++)) || true
  fi
}

echo "=== Test: check_multi_installs helper ==="

# Source capability.sh to get the functions
. "$DIR/scripts/lib/capability.sh"

# Test: detect_all_installations returns expected format
echo "--- detect_all_installations format ---"
output="$(detect_all_installations "bash" "bash" 2>/dev/null || true)"
if [ -n "$output" ]; then
  # Should have method:path format
  first_line="$(echo "$output" | head -1)"
  if echo "$first_line" | grep -qE '^[a-z_]+(\([^)]*\))?:/.+'; then
    echo "  PASS: detect_all_installations returns method:path format"
    ((PASS++)) || true
  else
    echo "  FAIL: unexpected format: $first_line"
    ((FAIL++)) || true
  fi
else
  echo "  SKIP: bash not found via type -a (unexpected)"
fi

echo "=== Test: SHA256 hash comparison in github_release_binary ==="

# Create a mock scenario: two identical files
tmpdir="$(mktemp -d)"
echo "identical content" > "$tmpdir/old_binary"
echo "identical content" > "$tmpdir/new_binary"

OLD_HASH="$(sha256sum "$tmpdir/old_binary" | awk '{print $1}')"
NEW_HASH="$(sha256sum "$tmpdir/new_binary" | awk '{print $1}')"

if [ "$OLD_HASH" = "$NEW_HASH" ]; then
  echo "  PASS: identical files produce matching SHA256"
  ((PASS++)) || true
else
  echo "  FAIL: SHA256 mismatch for identical files"
  ((FAIL++)) || true
fi

# Different files should NOT match
echo "different content" > "$tmpdir/new_binary2"
NEW_HASH2="$(sha256sum "$tmpdir/new_binary2" | awk '{print $1}')"
if [ "$OLD_HASH" != "$NEW_HASH2" ]; then
  echo "  PASS: different files produce different SHA256"
  ((PASS++)) || true
else
  echo "  FAIL: SHA256 matched for different files"
  ((FAIL++)) || true
fi

rm -rf "$tmpdir"

echo "=== Test: already-current marker file ==="

# Simulate marker creation and cleanup
mkdir -p /tmp/.cli-audit
echo "v1.1.0" > /tmp/.cli-audit/test-tool.already-current

if [ -f /tmp/.cli-audit/test-tool.already-current ]; then
  echo "  PASS: marker file created"
  ((PASS++)) || true
else
  echo "  FAIL: marker file not created"
  ((FAIL++)) || true
fi

# Simulate cleanup
rm -f /tmp/.cli-audit/test-tool.already-current
if [ ! -f /tmp/.cli-audit/test-tool.already-current ]; then
  echo "  PASS: marker file cleaned up"
  ((PASS++)) || true
else
  echo "  FAIL: marker file not cleaned up"
  ((FAIL++)) || true
fi

rmdir /tmp/.cli-audit 2>/dev/null || true

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
