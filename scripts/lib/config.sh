#!/usr/bin/env bash
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

    # Use Python config system to check auto_update
    python3 -c "
import sys
sys.path.insert(0, '$_CONFIG_ROOT')
from cli_audit.config import load_config
config = load_config()
print('true' if config.is_auto_update_enabled('$tool') else 'false')
" 2>/dev/null || echo "false"
}

# Get the global auto_upgrade preference
# Returns: "true" or "false"
config_get_global_auto_upgrade() {
    python3 -c "
import sys
sys.path.insert(0, '$_CONFIG_ROOT')
from cli_audit.config import load_config
config = load_config()
print('true' if config.preferences.auto_upgrade else 'false')
" 2>/dev/null || echo "true"
}
