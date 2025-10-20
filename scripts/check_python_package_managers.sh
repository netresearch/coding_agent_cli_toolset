#!/usr/bin/env bash
# Check for multiple Python package managers and recommend consolidation to uv
set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect installed package managers
has_pip=false
has_pipx=false
has_uv=false

if command -v pip >/dev/null 2>&1 || command -v pip3 >/dev/null 2>&1; then
  has_pip=true
fi

if command -v pipx >/dev/null 2>&1; then
  has_pipx=true
fi

if command -v uv >/dev/null 2>&1; then
  has_uv=true
fi

# Count how many are installed
count=0
managers=()
if $has_pip; then count=$((count + 1)); managers+=("pip"); fi
if $has_pipx; then count=$((count + 1)); managers+=("pipx"); fi
if $has_uv; then count=$((count + 1)); managers+=("uv"); fi

# If only uv is installed, all good
if $has_uv && ! $has_pip && ! $has_pipx; then
  echo -e "${GREEN}✓ Only uv is installed - optimal configuration!${NC}"
  exit 0
fi

# If multiple managers are installed, warn
if [ "$count" -gt 1 ]; then
  echo -e "${YELLOW}⚠ Multiple Python package managers detected:${NC}"
  for mgr in "${managers[@]}"; do
    echo "  - $mgr"
  done
  echo ""
  echo -e "${BLUE}Recommendation: Consolidate to 'uv' for better performance and simplicity${NC}"
  echo ""
  echo "Why uv?"
  echo "  • 10-100x faster than pip/pipx"
  echo "  • Replaces both pip and pipx functionality"
  echo "  • Better dependency resolution"
  echo "  • Built-in virtual environment management"
  echo ""

  if ! $has_uv; then
    echo -e "${YELLOW}Install uv:${NC}"
    echo "  make install-uv"
    echo ""
  fi

  if $has_pipx; then
    echo -e "${YELLOW}Migrate pipx tools to uv:${NC}"
    echo "  make reconcile-pipx-to-uv"
    echo ""
  fi

  if $has_pip; then
    echo -e "${YELLOW}Migrate pip packages to uv:${NC}"
    echo "  make reconcile-pip-to-uv"
    echo ""
  fi

  echo -e "${BLUE}After migration, you can optionally remove old package managers.${NC}"
  echo "Note: pip is often bundled with Python and can be left installed for compatibility."
  echo ""

  exit 1
fi

# If only pip or pipx (but not uv), recommend installing uv
if ! $has_uv; then
  echo -e "${YELLOW}⚠ Using legacy Python package manager(s):${NC}"
  for mgr in "${managers[@]}"; do
    echo "  - $mgr"
  done
  echo ""
  echo -e "${BLUE}Recommendation: Install 'uv' for 10-100x better performance${NC}"
  echo ""
  echo "Install uv:"
  echo "  make install-uv"
  echo ""
  exit 1
fi

echo -e "${GREEN}✓ Python package manager configuration looks good${NC}"
