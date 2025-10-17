#!/usr/bin/env bash
# path_check.sh - PATH validation and auto-fix for package managers and language environments

set -euo pipefail

PATH_CHECK_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect user's shell RC file
detect_shell_rc() {
  local shell_name="${SHELL##*/}"
  
  case "$shell_name" in
    bash)
      # Prefer .bashrc for interactive shells
      if [ -f "$HOME/.bashrc" ]; then
        echo "$HOME/.bashrc"
      elif [ -f "$HOME/.bash_profile" ]; then
        echo "$HOME/.bash_profile"
      else
        echo "$HOME/.bashrc"  # Create it
      fi
      ;;
    zsh)
      if [ -f "$HOME/.zshrc" ]; then
        echo "$HOME/.zshrc"
      else
        echo "$HOME/.zshrc"  # Create it
      fi
      ;;
    fish)
      echo "$HOME/.config/fish/config.fish"
      ;;
    *)
      # Fallback to .profile
      echo "$HOME/.profile"
      ;;
  esac
}

# Check if a PATH entry exists
path_contains() {
  local dir="$1"
  case ":$PATH:" in
    *":$dir:"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Check if a PATH entry comes before another
path_order_ok() {
  local earlier="$1"
  local later="$2"
  
  # Get positions
  local pos_earlier=-1
  local pos_later=-1
  local pos=0
  
  IFS=':' read -ra PATHS <<< "$PATH"
  for p in "${PATHS[@]}"; do
    if [ "$p" = "$earlier" ]; then
      pos_earlier=$pos
    fi
    if [ "$p" = "$later" ]; then
      pos_later=$pos
    fi
    pos=$((pos + 1))
  done
  
  # If earlier not found, bad
  [ $pos_earlier -eq -1 ] && return 1
  
  # If later not found, order is OK (nothing to conflict with)
  [ $pos_later -eq -1 ] && return 0
  
  # Earlier should have lower position number
  [ $pos_earlier -lt $pos_later ]
}

# Package manager PATH requirements
# Format: name|path|init_command|description|priority(1=highest)
declare -A PATH_REQUIREMENTS=(
  # Python/UV
  ["uv"]="$HOME/.local/bin|export PATH=\"\$HOME/.local/bin:\$PATH\"|UV package manager binaries|1"
  
  # Ruby/rbenv
  ["rbenv"]="$HOME/.rbenv/bin|export PATH=\"\$HOME/.rbenv/bin:\$PATH\"\neval \"\$(rbenv init - bash)\"|rbenv Ruby version manager|2"
  ["rbenv-shims"]="$HOME/.rbenv/shims||rbenv shims (auto-managed)|1"
  
  # Node/nvm (requires sourcing, not just PATH)
  ["nvm"]="$HOME/.nvm|export NVM_DIR=\"\$HOME/.nvm\"\n[ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\"|nvm Node.js version manager|1"
  
  # Python/pyenv
  ["pyenv"]="$HOME/.pyenv/bin|export PYENV_ROOT=\"\$HOME/.pyenv\"\nexport PATH=\"\$PYENV_ROOT/bin:\$PATH\"\neval \"\$(pyenv init --path)\"\neval \"\$(pyenv init -)\"|pyenv Python version manager|2"
  ["pyenv-shims"]="$HOME/.pyenv/shims||pyenv shims (auto-managed)|1"
  
  # Rust/cargo
  ["cargo"]="$HOME/.cargo/bin|. \"\$HOME/.cargo/env\"|Rust cargo package manager|3"
  
  # Go
  ["go-bin"]="$HOME/go/bin|export PATH=\"\$HOME/go/bin:\$PATH\"|Go installed binaries|3"
  
  # General user binaries
  ["local-bin"]="$HOME/.local/bin|export PATH=\"\$HOME/.local/bin:\$PATH\"|User-installed binaries|2"
)

# Priority order rules: lower number = should come earlier in PATH
# This ensures language version managers take precedence over system packages

# Check if a tool is properly configured in RC file
is_configured_in_rc() {
  local init_cmd="$1"
  local rc_file
  rc_file=$(detect_shell_rc)

  # Extract first significant line from init command
  local first_line
  first_line=$(echo -e "$init_cmd" | head -1)

  # Check if it's in the RC file
  grep -qF "${first_line}" "$rc_file" 2>/dev/null
}

# Check a single PATH requirement
check_path_requirement() {
  local name="$1"
  local requirement="${PATH_REQUIREMENTS[$name]}"

  IFS='|' read -r dir init_cmd description priority <<< "$requirement"

  # Expand home directory
  dir="${dir/#\~/$HOME}"

  local result=""
  local warning=""
  local fix=""

  # Check if directory exists
  if [ ! -d "$dir" ]; then
    result="not_installed"
    return 0
  fi

  # Check if already configured in RC file (more reliable than checking current PATH)
  if is_configured_in_rc "$init_cmd"; then
    result="ok"
    echo "$result|$warning|$fix"
    return 0
  fi

  # Not in RC file - check if in current PATH (might be manually set)
  if ! path_contains "$dir"; then
    result="missing"
    warning="⚠️  $description not configured in shell RC file"
    fix="add_to_path|$name|$dir|$init_cmd"
  else
    result="ok"

    # Check priority ordering (e.g., ~/.local/bin should come before /usr/bin)
    if [ "$name" = "local-bin" ] || [ "$name" = "cargo" ] || [ "$name" = "rbenv-shims" ]; then
      if ! path_order_ok "$dir" "/usr/bin"; then
        result="wrong_order"
        warning="⚠️  $description should come before /usr/bin in PATH"
        fix="reorder_path|$name|$dir|$init_cmd"
      fi
    fi
  fi

  echo "$result|$warning|$fix"
}

# Check all PATH requirements
check_all_paths() {
  local issues=()
  
  for name in "${!PATH_REQUIREMENTS[@]}"; do
    local check_result
    check_result=$(check_path_requirement "$name")
    
    IFS='|' read -r result warning fix <<< "$check_result"
    
    if [ "$result" = "missing" ] || [ "$result" = "wrong_order" ]; then
      issues+=("$name|$warning|$fix")
    fi
  done
  
  # Print issues
  if [ ${#issues[@]} -gt 0 ]; then
    echo "# PATH Configuration Issues Found:" >&2
    echo "#" >&2
    for issue in "${issues[@]}"; do
      IFS='|' read -r name warning fix <<< "$issue"
      echo "#   $warning" >&2
    done
    echo "#" >&2
    echo "# Run 'make fix-path' to automatically fix these issues" >&2
    return 1
  fi
  
  return 0
}

# Add init commands to shell RC file
add_to_shell_rc() {
  local name="$1"
  local init_cmd="$2"
  local rc_file
  rc_file=$(detect_shell_rc)
  
  # Check if already present
  local first_line
  first_line=$(echo -e "$init_cmd" | head -1)
  
  if grep -qF "${first_line}" "$rc_file" 2>/dev/null; then
    echo "# [$name] Already configured in $rc_file" >&2
    return 0
  fi
  
  echo "# [$name] Adding to $rc_file..." >&2
  
  # Add with clear section marker
  {
    echo ""
    echo "# $name initialization (added by ai_cli_preparation)"
    echo -e "$init_cmd"
  } >> "$rc_file"
  
  echo "# [$name] ✓ Added to $rc_file" >&2
}

# Fix all PATH issues
fix_all_paths() {
  local rc_file
  rc_file=$(detect_shell_rc)
  local fixed_count=0
  
  echo "# Fixing PATH configuration issues..." >&2
  echo "# Target RC file: $rc_file" >&2
  echo "#" >&2
  
  for name in "${!PATH_REQUIREMENTS[@]}"; do
    local check_result
    check_result=$(check_path_requirement "$name")
    
    IFS='|' read -r result warning fix <<< "$check_result"
    
    if [ "$result" = "missing" ] || [ "$result" = "wrong_order" ]; then
      IFS='|' read -r fix_type fix_name fix_dir fix_init_cmd <<< "$fix"
      
      if [ -n "$fix_init_cmd" ]; then
        add_to_shell_rc "$fix_name" "$fix_init_cmd"
        fixed_count=$((fixed_count + 1))
      fi
    fi
  done
  
  if [ $fixed_count -gt 0 ]; then
    echo "#" >&2
    echo "# ✓ Fixed $fixed_count PATH issues" >&2
    echo "#" >&2
    echo "# To apply changes, run:" >&2
    echo "#   source $rc_file" >&2
    echo "# Or start a new shell session" >&2
  else
    echo "# No PATH issues found" >&2
  fi
}

# Export functions for use in other scripts
export -f detect_shell_rc
export -f path_contains
export -f path_order_ok
export -f check_path_requirement
export -f check_all_paths
export -f add_to_shell_rc
export -f fix_all_paths
