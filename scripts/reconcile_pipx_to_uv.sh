#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
set -euo pipefail

# reconcile_pipx_to_uv.sh - Migrate pipx tools to UV
# This script moves all pipx-installed tools to UV tool management

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"

echo "════════════════════════════════════════════════════════"
echo "  Reconcile: pipx → UV"
echo "════════════════════════════════════════════════════════"
echo ""

# Check prerequisites
if ! command -v uv >/dev/null 2>&1; then
	echo "❌ UV not installed. Install UV first:"
	echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
	exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
	echo "✓ pipx not installed, nothing to migrate"
	exit 0
fi

# Get list of pipx tools
echo "📋 Scanning pipx tools..."
pipx_tools=$(pipx list --short 2>/dev/null || true)

if [ -z "$pipx_tools" ]; then
	echo "✓ No pipx tools found"
	exit 0
fi

tool_count=$(echo "$pipx_tools" | wc -l)
echo "Found $tool_count pipx tools:"
echo "$pipx_tools" | sed 's/^/  - /'
echo ""

if [ "$DRY_RUN" = "1" ]; then
	echo "🔍 DRY-RUN MODE: Would migrate these tools"
	exit 0
fi

# Ask for confirmation
read -p "Migrate all pipx tools to UV? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
	echo "❌ Migration cancelled"
	exit 0
fi

echo ""
echo "🔄 Migrating tools to UV..."
echo ""

# Process each tool
migrated=0
failed=0

while IFS= read -r tool_name; do
	[ -z "$tool_name" ] && continue

	# Extract just the package name (first word)
	package_name=$(echo "$tool_name" | awk '{print $1}')

	echo "→ Migrating: $package_name"

	# Install in UV
	echo "  Installing with UV..."
	if uv tool install "$package_name" >/dev/null 2>&1; then
		echo "  ✓ Installed in UV"

		# Uninstall from pipx
		echo "  Removing from pipx..."
		if pipx uninstall "$package_name" >/dev/null 2>&1; then
			echo "  ✓ Removed from pipx"
			migrated=$((migrated + 1))
		else
			echo "  ⚠ Warning: Failed to remove from pipx (but UV tool installed)"
			migrated=$((migrated + 1))
		fi
	else
		echo "  ❌ Failed to install in UV"
		failed=$((failed + 1))
	fi
	echo ""
done <<< "$pipx_tools"

echo "════════════════════════════════════════════════════════"
echo "Migration Summary:"
echo "  ✓ Migrated: $migrated tools"
echo "  ❌ Failed:   $failed tools"
echo "════════════════════════════════════════════════════════"

if [ "$migrated" -gt 0 ]; then
	echo ""
	echo "✓ Migration complete! UV is now managing your Python tools."
	echo "  Run 'uv tool list' to see installed tools"
	echo ""
	echo "Optional cleanup:"
	echo "  - Remove pipx itself: pip3 uninstall pipx"
	echo "  - Remove pipx directory: rm -rf ~/.local/pipx"
fi
