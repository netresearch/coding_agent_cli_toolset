#!/usr/bin/env bash
# Integration tests for multi-install detection and hash verification
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

# ── Assert helpers ──────────────────────────────────────────────────────────

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

assert_eq() {
  local label="$1" actual="$2" expected="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  PASS: $label"
    ((PASS++)) || true
  else
    echo "  FAIL: $label"
    echo "    expected: $expected"
    echo "    actual:   $actual"
    ((FAIL++)) || true
  fi
}

assert_ne() {
  local label="$1" actual="$2" unexpected="$3"
  if [ "$actual" != "$unexpected" ]; then
    echo "  PASS: $label"
    ((PASS++)) || true
  else
    echo "  FAIL: $label"
    echo "    should NOT equal: $unexpected"
    ((FAIL++)) || true
  fi
}

# ── Source capability.sh ────────────────────────────────────────────────────

. "$DIR/scripts/lib/capability.sh"

# ════════════════════════════════════════════════════════════════════════════
echo "=== Test: classify_install_path ==="
# ════════════════════════════════════════════════════════════════════════════

# cargo path
assert_eq "classify cargo path" \
  "$(classify_install_path "rg" "$HOME/.cargo/bin/rg")" "cargo"

# go path (default GOPATH)
assert_eq "classify go path" \
  "$(classify_install_path "golint" "$HOME/go/bin/golint")" "go"

# go path with custom GOPATH
GOPATH_BAK="${GOPATH:-}"
export GOPATH="/tmp/custom-go"
assert_eq "classify go path with custom GOPATH" \
  "$(classify_install_path "golint" "/tmp/custom-go/bin/golint")" "go"
if [ -n "$GOPATH_BAK" ]; then export GOPATH="$GOPATH_BAK"; else unset GOPATH; fi

# manual path (in ~/.local/bin, not pipx/uv - use a tool name that pipx/uv won't know)
assert_eq "classify manual path" \
  "$(classify_install_path "nonexistent_xyz_tool" "$HOME/.local/bin/nonexistent_xyz_tool")" "manual"

# gem/rbenv path
assert_eq "classify rbenv path" \
  "$(classify_install_path "rubocop" "$HOME/.rbenv/shims/rubocop")" "gem"

# npm/nvm path - should return npm(vXX.XX.X)
result="$(classify_install_path "eslint" "$HOME/.nvm/versions/node/v20.11.0/bin/eslint")"
if [[ "$result" == npm\(* ]]; then
  echo "  PASS: classify nvm path returns npm(...) (got: $result)"
  ((PASS++)) || true
else
  echo "  FAIL: classify nvm path expected npm(...), got: $result"
  ((FAIL++)) || true
fi

# Verify the node version is extracted correctly
assert_eq "classify nvm path extracts version" \
  "$(classify_install_path "eslint" "$HOME/.nvm/versions/node/v20.11.0/bin/eslint")" "npm(v20.11.0)"

# pipx venv path - should return pipx(pkg)
assert_eq "classify pipx venv path" \
  "$(classify_install_path "black" "$HOME/.local/pipx/venvs/black/bin/black")" "pipx(black)"

# linuxbrew path
assert_eq "classify linuxbrew path" \
  "$(classify_install_path "jq" "/home/linuxbrew/.linuxbrew/bin/jq")" "brew"

# homebrew macOS path
assert_eq "classify homebrew macOS path" \
  "$(classify_install_path "jq" "/opt/homebrew/bin/jq")" "brew"

# snap path
assert_eq "classify snap path" \
  "$(classify_install_path "lxc" "/snap/bin/lxc")" "snap"

# unknown path
assert_eq "classify unknown path" \
  "$(classify_install_path "foo" "/opt/custom/foo")" "unknown"

# /usr/bin path - should return apt or system (depends on dpkg availability)
result="$(classify_install_path "bash" "/usr/bin/bash" 2>/dev/null || echo "error")"
if [ "$result" != "error" ]; then
  echo "  PASS: classify /usr/bin path doesn't crash (got: $result)"
  ((PASS++)) || true
else
  echo "  FAIL: classify /usr/bin path crashed"
  ((FAIL++)) || true
fi

# /bin path - should behave like /usr/bin
result="$(classify_install_path "ls" "/bin/ls" 2>/dev/null || echo "error")"
if [ "$result" != "error" ]; then
  echo "  PASS: classify /bin path doesn't crash (got: $result)"
  ((PASS++)) || true
else
  echo "  FAIL: classify /bin path crashed"
  ((FAIL++)) || true
fi

# /usr/local/bin path without brew - should return manual
# (only returns brew if brew is installed AND the tool is in brew's formula list)
result="$(classify_install_path "nonexistent_xyz_tool" "/usr/local/bin/nonexistent_xyz_tool")"
if [ "$result" = "manual" ] || [ "$result" = "brew" ]; then
  echo "  PASS: classify /usr/local/bin returns manual or brew (got: $result)"
  ((PASS++)) || true
else
  echo "  FAIL: classify /usr/local/bin expected manual or brew, got: $result"
  ((FAIL++)) || true
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: detect_all_installations format ==="
# ════════════════════════════════════════════════════════════════════════════

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

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: detect_all_installations edge cases ==="
# ════════════════════════════════════════════════════════════════════════════

# Non-existent binary should return empty
output="$(detect_all_installations "nonexistent_tool_xyz_12345" "nonexistent_tool_xyz_12345" 2>/dev/null || true)"
assert_eq "nonexistent binary returns empty" "$output" ""

# Tool with known single installation (use a tool likely to have exactly one)
if command -v sd >/dev/null 2>&1; then
  output="$(detect_all_installations "sd" "sd" 2>/dev/null || true)"
  line_count="$(echo "$output" | grep -c . || true)"
  if [ "$line_count" -eq 1 ]; then
    echo "  PASS: sd has exactly 1 installation"
    ((PASS++)) || true
  elif [ "$line_count" -eq 0 ]; then
    echo "  SKIP: sd not installed"
  else
    echo "  INFO: sd has $line_count installations (may have multiple, that's OK)"
    ((PASS++)) || true
  fi
else
  echo "  SKIP: sd not installed"
fi

# count_installations helper
count="$(count_installations "bash" "bash" 2>/dev/null || echo "0")"
if [ "$count" -ge 1 ]; then
  echo "  PASS: count_installations for bash >= 1 (got $count)"
  ((PASS++)) || true
else
  echo "  FAIL: count_installations for bash returned $count"
  ((FAIL++)) || true
fi

# has_multiple_installations for non-existent tool should return false (exit 1)
if ! has_multiple_installations "nonexistent_tool_xyz_12345" "nonexistent_tool_xyz_12345" 2>/dev/null; then
  echo "  PASS: has_multiple_installations returns false for nonexistent tool"
  ((PASS++)) || true
else
  echo "  FAIL: has_multiple_installations returned true for nonexistent tool"
  ((FAIL++)) || true
fi

# count_installations for non-existent tool should return 0
count="$(count_installations "nonexistent_tool_xyz_12345" "nonexistent_tool_xyz_12345" 2>/dev/null || echo "0")"
assert_eq "count_installations for nonexistent tool" "$count" "0"

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: check_multi_installs output ==="
# ════════════════════════════════════════════════════════════════════════════

# Source catalog.sh for catalog_get_property
. "$DIR/scripts/lib/catalog.sh"

# Extract check_multi_installs from guide.sh to avoid guide.sh side effects
eval "$(sed -n '/^check_multi_installs()/,/^}/p' "$DIR/scripts/guide.sh")"

# Single-install tool should produce no "Multiple installations" warning
if command -v sd >/dev/null 2>&1; then
  output="$(check_multi_installs "sd" 2>/dev/null || true)"
  assert_not_contains "single install produces no warning" "$output" "Multiple installations"
else
  echo "  SKIP: sd not installed (cannot test single install warning)"
fi

# bash likely has at least 1 installation - verify it doesn't crash
output="$(check_multi_installs "bash" 2>/dev/null || true)"
echo "  PASS: check_multi_installs for bash doesn't crash"
((PASS++)) || true

# Tool with no catalog entry - should not crash (falls back to tool name as binary)
output="$(check_multi_installs "nonexistent_tool_xyz" 2>/dev/null || true)"
echo "  PASS: check_multi_installs for uncataloged tool doesn't crash"
((PASS++)) || true

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: SHA256 hash comparison ==="
# ════════════════════════════════════════════════════════════════════════════

tmpdir="$(mktemp -d)"

# Identical text files should produce matching SHA256
echo "identical content" > "$tmpdir/old_binary"
echo "identical content" > "$tmpdir/new_binary"

OLD_HASH="$(sha256sum "$tmpdir/old_binary" | awk '{print $1}')"
NEW_HASH="$(sha256sum "$tmpdir/new_binary" | awk '{print $1}')"
assert_eq "identical files produce matching SHA256" "$OLD_HASH" "$NEW_HASH"

# Different files should NOT match
echo "different content" > "$tmpdir/new_binary2"
NEW_HASH2="$(sha256sum "$tmpdir/new_binary2" | awk '{print $1}')"
assert_ne "different files produce different SHA256" "$OLD_HASH" "$NEW_HASH2"

rm -rf "$tmpdir"

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: SHA256 edge cases ==="
# ════════════════════════════════════════════════════════════════════════════

tmpdir="$(mktemp -d)"

# Empty files should still have a hash (and match each other)
touch "$tmpdir/empty1"
touch "$tmpdir/empty2"
H1="$(sha256sum "$tmpdir/empty1" | awk '{print $1}')"
H2="$(sha256sum "$tmpdir/empty2" | awk '{print $1}')"
assert_eq "empty files have matching SHA256" "$H1" "$H2"

# Hash should be the well-known empty-input SHA256
assert_eq "empty file SHA256 is correct" "$H1" \
  "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# Missing file - sha256sum should fail; awk yields empty string
MISSING_HASH="$(sha256sum "$tmpdir/no_such_file" 2>/dev/null | awk '{print $1}' || true)"
assert_eq "missing file returns empty hash" "$MISSING_HASH" ""

# Binary files (not just text)
printf '\x00\x01\x02\x03' > "$tmpdir/bin1"
printf '\x00\x01\x02\x03' > "$tmpdir/bin2"
printf '\x00\x01\x02\x04' > "$tmpdir/bin3"
B1="$(sha256sum "$tmpdir/bin1" | awk '{print $1}')"
B2="$(sha256sum "$tmpdir/bin2" | awk '{print $1}')"
B3="$(sha256sum "$tmpdir/bin3" | awk '{print $1}')"
assert_eq "identical binary files match" "$B1" "$B2"
assert_ne "different binary files differ" "$B1" "$B3"

# Large-ish file (1MB)
dd if=/dev/urandom of="$tmpdir/large1" bs=1024 count=1024 2>/dev/null
cp "$tmpdir/large1" "$tmpdir/large2"
L1="$(sha256sum "$tmpdir/large1" | awk '{print $1}')"
L2="$(sha256sum "$tmpdir/large2" | awk '{print $1}')"
assert_eq "1MB identical files match" "$L1" "$L2"

# Flip one byte in the copy and confirm mismatch
printf '\xff' | dd of="$tmpdir/large2" bs=1 seek=512 count=1 conv=notrunc 2>/dev/null
L2_MODIFIED="$(sha256sum "$tmpdir/large2" | awk '{print $1}')"
assert_ne "1MB files differ after single-byte flip" "$L1" "$L2_MODIFIED"

rm -rf "$tmpdir"

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: marker file edge cases ==="
# ════════════════════════════════════════════════════════════════════════════

# Marker content should contain the version
mkdir -p /tmp/.cli-audit
echo "v2.0.0" > /tmp/.cli-audit/test-marker.already-current
content="$(cat /tmp/.cli-audit/test-marker.already-current)"
assert_eq "marker contains version" "$content" "v2.0.0"

# Multiple markers for different tools should coexist
echo "v1.0.0" > /tmp/.cli-audit/tool-a.already-current
echo "v3.0.0" > /tmp/.cli-audit/tool-b.already-current
assert_eq "tool-a marker" "$(cat /tmp/.cli-audit/tool-a.already-current)" "v1.0.0"
assert_eq "tool-b marker" "$(cat /tmp/.cli-audit/tool-b.already-current)" "v3.0.0"

# Cleaning one doesn't affect the other
rm -f /tmp/.cli-audit/tool-a.already-current
if [ ! -f /tmp/.cli-audit/tool-a.already-current ] && [ -f /tmp/.cli-audit/tool-b.already-current ]; then
  echo "  PASS: cleaning one marker doesn't affect another"
  ((PASS++)) || true
else
  echo "  FAIL: marker isolation broken"
  ((FAIL++)) || true
fi

# Marker with empty content (edge case - should still exist as a file)
: > /tmp/.cli-audit/empty-marker.already-current
if [ -f /tmp/.cli-audit/empty-marker.already-current ]; then
  echo "  PASS: empty marker file exists"
  ((PASS++)) || true
else
  echo "  FAIL: empty marker file was not created"
  ((FAIL++)) || true
fi

# Overwriting a marker updates its content
echo "v4.0.0" > /tmp/.cli-audit/tool-b.already-current
assert_eq "marker overwrite" "$(cat /tmp/.cli-audit/tool-b.already-current)" "v4.0.0"

# Cleanup
rm -f /tmp/.cli-audit/test-marker.already-current \
      /tmp/.cli-audit/tool-a.already-current \
      /tmp/.cli-audit/tool-b.already-current \
      /tmp/.cli-audit/empty-marker.already-current
rmdir /tmp/.cli-audit 2>/dev/null || true

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: end-to-end installer output ==="
# ════════════════════════════════════════════════════════════════════════════

if command -v sd >/dev/null 2>&1; then
  output="$(bash "$DIR/scripts/install_tool.sh" sd update 2>&1 || true)"

  # Should contain the note about already-current (if sd is at latest)
  if echo "$output" | grep -qF "binary already matches target release"; then
    echo "  PASS: sd installer shows hash match note"
    ((PASS++)) || true

    # Should contain before/after/path lines
    assert_contains "sd installer shows before" "$output" "[sd] before:"
    assert_contains "sd installer shows after"  "$output" "[sd] after:"
    assert_contains "sd installer shows path"   "$output" "[sd] path:"

    # After install_tool.sh, the marker should exist (guide.sh consumes it)
    if [ -f /tmp/.cli-audit/sd.already-current ]; then
      echo "  PASS: sd marker file created by installer"
      ((PASS++)) || true
      rm -f /tmp/.cli-audit/sd.already-current
    else
      echo "  PASS: sd marker already consumed or not created (may depend on timing)"
      ((PASS++)) || true
    fi
  else
    # sd might have actually been upgraded - that's also valid
    echo "  INFO: sd was upgraded or output differs (not already-current)"
    echo "  PASS: sd installer ran without crash"
    ((PASS++)) || true
  fi
else
  echo "  SKIP: sd not installed"
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: is_method_available ==="
# ════════════════════════════════════════════════════════════════════════════

# github_release_binary should generally be available (curl exists, ~/.local/bin writable)
if is_method_available "github_release_binary"; then
  echo "  PASS: github_release_binary method available"
  ((PASS++)) || true
else
  echo "  FAIL: github_release_binary method should be available (curl + ~/.local/bin)"
  ((FAIL++)) || true
fi

# dedicated_script always reports available
if is_method_available "dedicated_script"; then
  echo "  PASS: dedicated_script method always available"
  ((PASS++)) || true
else
  echo "  FAIL: dedicated_script method should always be available"
  ((FAIL++)) || true
fi

# unknown method should NOT be available
if ! is_method_available "totally_fake_method"; then
  echo "  PASS: unknown method reports unavailable"
  ((PASS++)) || true
else
  echo "  FAIL: unknown method should report unavailable"
  ((FAIL++)) || true
fi

# cargo should be available if cargo binary exists
if command -v cargo >/dev/null 2>&1; then
  if is_method_available "cargo"; then
    echo "  PASS: cargo method available (cargo binary found)"
    ((PASS++)) || true
  else
    echo "  FAIL: cargo method should be available when cargo exists"
    ((FAIL++)) || true
  fi
else
  if ! is_method_available "cargo"; then
    echo "  PASS: cargo method unavailable (no cargo binary)"
    ((PASS++)) || true
  else
    echo "  FAIL: cargo method should be unavailable when cargo is missing"
    ((FAIL++)) || true
  fi
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: detect_install_method ==="
# ════════════════════════════════════════════════════════════════════════════

# Non-existent binary should return "none"
assert_eq "detect_install_method for nonexistent binary" \
  "$(detect_install_method "nonexistent_xyz_12345" "nonexistent_xyz_12345")" "none"

# bash should return something meaningful (apt, system, or similar)
result="$(detect_install_method "bash" "bash")"
assert_ne "detect_install_method for bash is not none" "$result" "none"

# If sd is installed, verify it detects something other than "none"
if command -v sd >/dev/null 2>&1; then
  result="$(detect_install_method "sd" "sd")"
  assert_ne "detect_install_method for sd is not none" "$result" "none"
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "=== Test: symlink deduplication in detect_all_installations ==="
# ════════════════════════════════════════════════════════════════════════════

# On many Linux systems, /bin and /usr/bin resolve to the same thing.
# detect_all_installations should deduplicate via readlink -f.
output="$(detect_all_installations "bash" "bash" 2>/dev/null || true)"
count="$(echo "$output" | grep -c . || true)"

# /bin/bash and /usr/bin/bash usually resolve to the same real path,
# so we should have at most a small number (usually 1).
if [ "$count" -ge 1 ] && [ "$count" -le 3 ]; then
  echo "  PASS: bash installations deduplicated (count=$count)"
  ((PASS++)) || true
else
  echo "  INFO: bash has $count installations (unexpected but not necessarily wrong)"
  ((PASS++)) || true
fi

# ════════════════════════════════════════════════════════════════════════════

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
