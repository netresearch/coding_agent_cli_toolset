#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Netresearch DTT GmbH
# config.sh - Query user configuration from Python config system
#
# This bridges bash scripts to the Python configuration system,
# allowing bash scripts to read user preferences from ~/.config/cli-audit/config.yml
#
# Usage:
#   source "$ROOT/scripts/lib/config.sh"
#   if [ "$(config_get_auto_update prettier)" = "true" ]; then
#     echo "Auto-update enabled"
#   fi

# Get the root directory (assumes sourced from scripts/ or subdirectory)
_CONFIG_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CONFIG_ROOT="$(cd "$_CONFIG_LIB_DIR/../.." && pwd)"

# Check if auto_update is enabled for a specific tool
# Falls back to global preferences.auto_upgrade if no per-tool setting
# Returns: "true" or "false"
config_get_auto_update() {
    local tool="$1"

    if [ -z "$tool" ]; then
        echo "false"
        return 1
    fi

    # Use Python config system to check auto_update. The tool name and the
    # root path reach Python as arguments, never as part of the program text:
    # multi-version keys carry a cycle taken from endoflife.date data.
    python3 - "$_CONFIG_ROOT" "$tool" 2>/dev/null <<'PY' || echo "false"
import sys
sys.path.insert(0, sys.argv[1])
from cli_audit.config import load_config
config = load_config()
print('true' if config.is_auto_update_enabled(sys.argv[2]) else 'false')
PY
}

# Get the global auto_upgrade preference
# Returns: "true" or "false"
config_get_global_auto_upgrade() {
    python3 - "$_CONFIG_ROOT" 2>/dev/null <<'PY' || echo "true"
import sys
sys.path.insert(0, sys.argv[1])
from cli_audit.config import load_config
config = load_config()
print('true' if config.preferences.auto_upgrade else 'false')
PY
}
