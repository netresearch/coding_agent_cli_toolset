#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
set -euo pipefail

# reconcile_pip_to_uv.sh - Migrate user-installed pip packages to UV
# This script moves Python packages from pip (user-installed) to UV tool management

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"

echo "════════════════════════════════════════════════════════"
echo "  Reconcile: pip → UV"
echo "════════════════════════════════════════════════════════"
echo ""

# Check prerequisites
if ! command -v uv >/dev/null 2>&1; then
	echo "❌ UV not installed. Install UV first:"
	echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
	exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
	echo "❌ python3 not found"
	exit 1
fi

# Get list of user-installed packages
echo "📋 Scanning user-installed pip packages..."
user_packages=$(python3 -m pip list --user --format=freeze 2>/dev/null | grep -v "^#" || true)

if [ -z "$user_packages" ]; then
	echo "✓ No user-installed pip packages found"
	exit 0
fi

package_count=$(echo "$user_packages" | wc -l)
echo "Found $package_count user-installed packages:"
echo "$user_packages" | sed 's/^/  - /'
echo ""

if [ "$DRY_RUN" = "1" ]; then
	echo "🔍 DRY-RUN MODE: Would migrate these packages"
	exit 0
fi

# Ask for confirmation
read -p "Migrate these packages to UV? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
	echo "❌ Migration cancelled"
	exit 0
fi

echo ""
echo "🔄 Migrating packages to UV..."
echo ""

# Process each package
migrated=0
failed=0
skipped=0

while IFS= read -r package_spec; do
	[ -z "$package_spec" ] && continue

	# Extract package name (before ==, >=, etc.)
	package_name=$(echo "$package_spec" | sed 's/[=<>].*//')

	echo "→ Processing: $package_name"

	# Check if it's a tool candidate (has CLI entry point)
	# Try to find the package in PATH
	if command -v "$package_name" >/dev/null 2>&1; then
		echo "  Installing as UV tool..."
		if uv tool install "$package_name" >/dev/null 2>&1; then
			echo "  ✓ Installed: $package_name (as UV tool)"

			# Uninstall from pip
			echo "  Removing from pip..."
			if python3 -m pip uninstall -y "$package_name" >/dev/null 2>&1; then
				echo "  ✓ Removed from pip"
				migrated=$((migrated + 1))
			else
				echo "  ⚠ Warning: Failed to remove from pip (but UV tool installed)"
				migrated=$((migrated + 1))
			fi
		else
			echo "  ❌ Failed to install as UV tool"
			failed=$((failed + 1))
		fi
	else
		# Not a tool, just a library - keep in pip or skip
		echo "  ⏭ Skipped: $package_name (library, not a tool)"
		skipped=$((skipped + 1))
	fi
	echo ""
done <<< "$user_packages"

echo "════════════════════════════════════════════════════════"
echo "Migration Summary:"
echo "  ✓ Migrated: $migrated packages"
echo "  ⏭ Skipped:  $skipped packages (libraries)"
echo "  ❌ Failed:   $failed packages"
echo "════════════════════════════════════════════════════════"

if [ "$skipped" -gt 0 ]; then
	echo ""
	echo "Note: Library packages (non-CLI tools) were skipped."
	echo "      These should remain managed by pip or moved to project requirements."
fi

if [ "$migrated" -gt 0 ]; then
	echo ""
	echo "✓ Migration complete! UV is now managing your Python tools."
	echo "  Run 'uv tool list' to see installed tools"
fi
