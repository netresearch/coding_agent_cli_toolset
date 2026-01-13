#!/usr/bin/env bash
# set_auto_update.sh - Enable/disable automatic updates for a tool
#
# Stores auto_update preferences in user config (~/.config/cli-audit/config.yml)
# instead of catalog files. This keeps user preferences separate from tool definitions.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

TOOL="${1:-}"
VALUE="${2:-true}"  # true or false

if [ -z "$TOOL" ]; then
  echo "Usage: $0 TOOL_NAME [true|false]" >&2
  echo "" >&2
  echo "Enable or disable automatic updates for a tool." >&2
  echo "When enabled, 'make upgrade' will update the tool without asking." >&2
  echo "" >&2
  echo "Settings are stored in: ~/.config/cli-audit/config.yml" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 prettier         # Enable auto-update for prettier" >&2
  echo "  $0 prettier true    # Enable auto-update for prettier" >&2
  echo "  $0 prettier false   # Disable auto-update for prettier" >&2
  exit 1
fi

# Validate tool exists in catalog
CATALOG_FILE="$ROOT/catalog/$TOOL.json"
if [ ! -f "$CATALOG_FILE" ]; then
  echo "Error: Tool '$TOOL' not found in catalog" >&2
  exit 1
fi

# Normalize value
case "$VALUE" in
  true|1|yes|on) VALUE="True" ;;
  false|0|no|off) VALUE="False" ;;
  *)
    echo "Error: Invalid value '$VALUE'. Use 'true' or 'false'" >&2
    exit 1
    ;;
esac

# User config file location
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/cli-audit/config.yml"

# Use project venv Python if available, otherwise fall back to system
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/bin/python3" ]; then
  PY="$ROOT/.venv/bin/python3"
else
  PY="${PYTHON:-python3}"
fi

# Update user config using Python
"$PY" << EOF
import os
import sys

# Ensure we can import yaml
try:
    import yaml
except ImportError:
    print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

config_file = "$CONFIG_FILE"
tool = "$TOOL"
value = $VALUE  # Python bool

# Ensure config directory exists
os.makedirs(os.path.dirname(config_file), exist_ok=True)

# Load existing config or create new
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f) or {}
else:
    config = {'version': 1}

# Ensure tools section exists
if 'tools' not in config:
    config['tools'] = {}

# Set or remove auto_update
if value:
    if tool not in config['tools']:
        config['tools'][tool] = {}
    config['tools'][tool]['auto_update'] = True
    action = "enabled"
else:
    if tool in config['tools'] and 'auto_update' in config['tools'][tool]:
        del config['tools'][tool]['auto_update']
        # Clean up empty tool config
        if not config['tools'][tool]:
            del config['tools'][tool]
    action = "disabled"

# Write back
with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print(f"Auto-update {action} for '{tool}'")
print(f"Config saved to: {config_file}")
EOF

if [ "$VALUE" = "True" ]; then
  echo ""
  echo "This tool will be automatically updated during 'make upgrade' without prompting."
  echo "To disable: $0 $TOOL false"
else
  echo ""
  echo "You will be prompted before updating this tool."
fi
