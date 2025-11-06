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

# Count how many NON-npm managers are installed (npm doesn't count, it's bundled with Node)
count=0
managers=()
if $has_yarn; then count=$((count + 1)); managers+=("yarn"); fi
if $has_pnpm; then count=$((count + 1)); managers+=("pnpm"); fi
if $has_bun; then count=$((count + 1)); managers+=("bun"); fi

# Check for conflicting lock files in current directory
has_package_lock=false
has_yarn_lock=false
has_pnpm_lock=false
has_bun_lock=false

if [ -f "package-lock.json" ]; then has_package_lock=true; fi
if [ -f "yarn.lock" ]; then has_yarn_lock=true; fi
if [ -f "pnpm-lock.yaml" ]; then has_pnpm_lock=true; fi
if [ -f "bun.lockb" ]; then has_bun_lock=true; fi

lock_count=0
if $has_package_lock; then lock_count=$((lock_count + 1)); fi
if $has_yarn_lock; then lock_count=$((lock_count + 1)); fi
if $has_pnpm_lock; then lock_count=$((lock_count + 1)); fi
if $has_bun_lock; then lock_count=$((lock_count + 1)); fi

# If multiple lock files exist in current directory, warn about project-level conflict
if [ "$lock_count" -gt 1 ]; then
  echo -e "${RED}⚠ Multiple package manager lock files detected in current directory:${NC}"
  if $has_package_lock; then echo "  - package-lock.json (npm)"; fi
  if $has_yarn_lock; then echo "  - yarn.lock (yarn)"; fi
  if $has_pnpm_lock; then echo "  - pnpm-lock.yaml (pnpm)"; fi
  if $has_bun_lock; then echo "  - bun.lockb (bun)"; fi
  echo ""
  echo -e "${RED}Problem: This project has conflicting lock files!${NC}"
  echo "  • Delete all but ONE lock file"
  echo "  • Reinstall dependencies with chosen package manager"
  echo "  • Add others to .gitignore"
  echo ""
  exit 1
fi

# If only npm or npm + one other manager, that's fine (npm is unavoidable)
if [ "$count" -eq 0 ]; then
  if $has_npm; then
    echo -e "${GREEN}✓ npm installed (bundled with Node.js)${NC}"
  else
    echo -e "${RED}⚠ No Node.js package manager found${NC}"
    echo "Install Node.js to get npm"
    exit 1
  fi
  exit 0
fi

if [ "$count" -eq 1 ]; then
  # npm + one other manager is the common, recommended setup
  echo -e "${GREEN}✓ Package managers: npm (Node.js bundled) + ${managers[0]}${NC}"
  exit 0
fi

# If multiple NON-npm managers installed, provide guidance (not an error, just info)
if [ "$count" -gt 1 ]; then
  echo -e "${BLUE}ℹ Multiple Node.js package managers available:${NC}"
  if $has_npm; then
    version=$(npm --version 2>/dev/null || echo "unknown")
    echo "  - npm ($version) [bundled with Node.js]"
  fi
  for mgr in "${managers[@]}"; do
    version=""
    case $mgr in
      yarn) version=$(yarn --version 2>/dev/null || echo "unknown") ;;
      pnpm) version=$(pnpm --version 2>/dev/null || echo "unknown") ;;
      bun) version=$(bun --version 2>/dev/null || echo "unknown") ;;
    esac
    echo "  - $mgr ($version)"
  done
  echo ""
  echo -e "${BLUE}Tip: Use one package manager per project (check lock files)${NC}"
  echo ""
fi

exit 0
