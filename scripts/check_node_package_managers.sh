#!/usr/bin/env bash
# Check for multiple Node.js package managers and recommend consolidation
set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect installed package managers
has_npm=false
has_yarn=false
has_pnpm=false
has_bun=false

if command -v npm >/dev/null 2>&1; then
  has_npm=true
fi

if command -v yarn >/dev/null 2>&1; then
  has_yarn=true
fi

if command -v pnpm >/dev/null 2>&1; then
  has_pnpm=true
fi

if command -v bun >/dev/null 2>&1; then
  has_bun=true
fi

# Count how many are installed
count=0
managers=()
if $has_npm; then count=$((count + 1)); managers+=("npm"); fi
if $has_yarn; then count=$((count + 1)); managers+=("yarn"); fi
if $has_pnpm; then count=$((count + 1)); managers+=("pnpm"); fi
if $has_bun; then count=$((count + 1)); managers+=("bun"); fi

# If only one is installed, check if it's the recommended one
if [ "$count" -eq 1 ]; then
  if $has_pnpm; then
    echo -e "${GREEN}✓ Only pnpm is installed - recommended configuration!${NC}"
    echo "  pnpm is fast, disk-efficient, and strictly follows package.json"
    exit 0
  elif $has_bun; then
    echo -e "${GREEN}✓ Only bun is installed - excellent choice!${NC}"
    echo "  bun is extremely fast and includes runtime + bundler"
    exit 0
  elif $has_npm; then
    echo -e "${YELLOW}ℹ npm is installed (bundled with Node.js)${NC}"
    echo ""
    echo -e "${BLUE}Recommendation: Consider pnpm for better performance and disk efficiency${NC}"
    echo ""
    echo "Why pnpm?"
    echo "  • 2x faster than npm"
    echo "  • Saves disk space with content-addressable storage"
    echo "  • Strict dependency resolution (no phantom dependencies)"
    echo "  • Drop-in replacement for npm"
    echo ""
    echo "Install pnpm:"
    echo "  npm install -g pnpm"
    echo ""
    exit 0
  else
    echo -e "${GREEN}✓ Only ${managers[0]} is installed${NC}"
    exit 0
  fi
fi

# If multiple managers are installed, warn
if [ "$count" -gt 1 ]; then
  echo -e "${YELLOW}⚠ Multiple Node.js package managers detected:${NC}"
  for mgr in "${managers[@]}"; do
    version=""
    case $mgr in
      npm) version=$($mgr --version 2>/dev/null || echo "unknown") ;;
      yarn) version=$($mgr --version 2>/dev/null || echo "unknown") ;;
      pnpm) version=$($mgr --version 2>/dev/null || echo "unknown") ;;
      bun) version=$($mgr --version 2>/dev/null || echo "unknown") ;;
    esac
    echo "  - $mgr ($version)"
  done
  echo ""
  echo -e "${RED}Problems with multiple managers:${NC}"
  echo "  • Lock file conflicts (package-lock.json vs pnpm-lock.yaml vs yarn.lock)"
  echo "  • Different dependency resolution algorithms"
  echo "  • Wasted disk space from multiple caches"
  echo "  • Team confusion about which manager to use"
  echo ""
  echo -e "${BLUE}Recommendation: Choose ONE package manager per project${NC}"
  echo ""
  echo "Recommended priority:"
  echo "  1. pnpm   - Fast, disk-efficient, strict (recommended for most projects)"
  echo "  2. bun    - Extremely fast, includes runtime (good for new projects)"
  echo "  3. npm    - Default, bundled with Node.js (keep for compatibility)"
  echo "  4. yarn   - Classic choice (consider migrating to pnpm or bun)"
  echo ""
  echo "Project-specific guidance:"
  echo "  • Check for existing lock files to see what your project uses"
  echo "  • Use .npmrc or package.json 'packageManager' field to enforce choice"
  echo "  • Consider 'pnpm' as default for new projects"
  echo ""
  echo "Note: npm comes bundled with Node.js and should typically be kept installed."
  echo "You can use other managers alongside npm, but choose ONE for each project."
  echo ""

  exit 1
fi

# If none are installed (unlikely if Node.js is installed)
echo -e "${RED}⚠ No Node.js package manager found${NC}"
echo "Install Node.js to get npm, then optionally install pnpm:"
echo "  nvm install --lts"
echo "  npm install -g pnpm"
exit 1
