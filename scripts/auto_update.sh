#!/usr/bin/env bash
set -euo pipefail

# Auto-update all package managers and their packages
# Detects installed package managers and runs their native update tools

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"
VERBOSE="${VERBOSE:-0}"
SKIP_SYSTEM="${SKIP_SYSTEM:-0}"

log() {
  printf "[auto-update] %s\n" "$*" >&2
}

vlog() {
  if [ "$VERBOSE" = "1" ]; then
    printf "[auto-update] %s\n" "$*" >&2
  fi
}

run_cmd() {
  local desc="$1"
  shift
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY-RUN: $desc"
    log "  Command: $*"
  else
    log "$desc"
    if [ "$VERBOSE" = "1" ]; then
      "$@"
    else
      "$@" >/dev/null 2>&1 || true
    fi
  fi
}

# ============================================================================
# Package Manager Detection
# ============================================================================

detect_apt() {
  command -v apt-get >/dev/null 2>&1
}

detect_brew() {
  command -v brew >/dev/null 2>&1
}

detect_cargo() {
  command -v cargo >/dev/null 2>&1
}

detect_pip() {
  command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1
}

detect_pipx() {
  command -v pipx >/dev/null 2>&1
}

detect_uv() {
  command -v uv >/dev/null 2>&1
}

detect_npm() {
  command -v npm >/dev/null 2>&1
}

detect_pnpm() {
  command -v pnpm >/dev/null 2>&1
}

detect_yarn() {
  command -v yarn >/dev/null 2>&1
}

detect_go() {
  command -v go >/dev/null 2>&1
}

detect_gem() {
  command -v gem >/dev/null 2>&1
}

detect_snap() {
  command -v snap >/dev/null 2>&1
}

detect_flatpak() {
  command -v flatpak >/dev/null 2>&1
}

detect_rustup() {
  command -v rustup >/dev/null 2>&1
}

detect_nvm() {
  [ -s "$HOME/.nvm/nvm.sh" ] && return 0
  command -v nvm >/dev/null 2>&1
}

detect_gcloud() {
  command -v gcloud >/dev/null 2>&1
}

detect_az() {
  command -v az >/dev/null 2>&1
}

detect_composer() {
  command -v composer >/dev/null 2>&1
}

detect_poetry() {
  command -v poetry >/dev/null 2>&1
}

detect_conda() {
  command -v conda >/dev/null 2>&1
}

detect_mamba() {
  command -v mamba >/dev/null 2>&1
}

detect_bundler() {
  command -v bundle >/dev/null 2>&1
}

detect_jspm() {
  command -v jspm >/dev/null 2>&1
}

detect_nuget() {
  command -v nuget >/dev/null 2>&1 || command -v dotnet >/dev/null 2>&1
}

# ============================================================================
# System Package Managers (requires sudo)
# ============================================================================

update_apt() {
  if ! detect_apt; then return; fi
  log "APT: Updating package lists and upgrading packages"

  if [ "$DRY_RUN" = "1" ]; then
    log "DRY-RUN: sudo apt-get update && sudo apt-get upgrade -y"
  else
    if [ "$VERBOSE" = "1" ]; then
      sudo apt-get update && sudo apt-get upgrade -y
    else
      sudo apt-get update >/dev/null 2>&1 || true
      sudo apt-get upgrade -y >/dev/null 2>&1 || true
    fi
    log "APT: Complete"
  fi
}

update_brew() {
  if ! detect_brew; then return; fi
  log "Homebrew: Updating and upgrading all packages"

  run_cmd "Brew: Update package index" brew update
  run_cmd "Brew: Upgrade packages" brew upgrade
  run_cmd "Brew: Cleanup old versions" brew cleanup

  log "Homebrew: Complete"
}

update_snap() {
  if ! detect_snap; then return; fi
  log "Snap: Refreshing all snaps"

  run_cmd "Snap: Refresh all" sudo snap refresh

  log "Snap: Complete"
}

update_flatpak() {
  if ! detect_flatpak; then return; fi
  log "Flatpak: Updating all applications"

  run_cmd "Flatpak: Update" flatpak update -y

  log "Flatpak: Complete"
}

# ============================================================================
# Language-Specific Package Managers
# ============================================================================

update_cargo() {
  if ! detect_cargo; then return; fi
  log "Cargo: Updating installed packages"

  # Update rustup first
  if detect_rustup; then
    run_cmd "Rustup: Update toolchains" rustup update

    # Update rustup components (clippy, rustfmt, rust-analyzer, etc.)
    vlog "Rustup: Updating components"
    for component in clippy rustfmt rust-analyzer rust-src; do
      if rustup component list 2>/dev/null | grep -q "^${component}.*installed"; then
        vlog "Rustup: Component $component is installed"
        # Components are updated with rustup update, no separate update needed
      fi
    done
  fi

  # Install cargo-update if not present
  if ! command -v cargo-install-update >/dev/null 2>&1; then
    vlog "Installing cargo-update for package upgrades"
    run_cmd "Cargo: Install cargo-update" cargo install cargo-update
  fi

  # Update all cargo-installed packages
  if command -v cargo-install-update >/dev/null 2>&1; then
    run_cmd "Cargo: Upgrade all packages" cargo install-update -a
  fi

  log "Cargo: Complete"
}

update_uv() {
  if ! detect_uv; then return; fi
  log "UV: Updating UV tools"

  # Update uv itself
  run_cmd "UV: Self-update" uv self update

  # Update all uv-managed tools
  if [ "$DRY_RUN" = "0" ]; then
    local tools
    tools="$(uv tool list 2>/dev/null | awk '{print $1}' || true)"
    if [ -n "$tools" ]; then
      log "UV: Upgrading $(echo "$tools" | wc -l) installed tools"
      while IFS= read -r tool; do
        [ -z "$tool" ] && continue
        run_cmd "UV: Upgrade $tool" uv tool upgrade "$tool"
      done <<< "$tools"
    fi
  else
    log "DRY-RUN: uv self update"
    log "DRY-RUN: uv tool upgrade <all-tools>"
  fi

  log "UV: Complete"
}

update_pipx() {
  if ! detect_pipx; then return; fi
  log "Pipx: Updating all packages"

  run_cmd "Pipx: Upgrade pipx" pip3 install --user --upgrade pipx
  run_cmd "Pipx: Upgrade all packages" pipx upgrade-all

  # Explicitly list important dev tools we track via pipx
  local important_tools=("semgrep" "pre-commit" "coverage" "tox" "checkov" "black" "flake8" "pylint" "mypy")
  for tool in "${important_tools[@]}"; do
    if pipx list 2>/dev/null | grep -q "package $tool"; then
      vlog "Pipx: $tool is installed"
    fi
  done

  log "Pipx: Complete"
}

update_pip() {
  if ! detect_pip; then return; fi
  log "Pip: Updating user-installed packages"

  # Update pip itself
  run_cmd "Pip: Self-update" python3 -m pip install --user --upgrade pip

  # List and upgrade user packages
  if [ "$DRY_RUN" = "0" ]; then
    local outdated
    outdated="$(python3 -m pip list --user --outdated --format=json 2>/dev/null || echo '[]')"
    if [ "$outdated" != "[]" ] && [ -n "$outdated" ]; then
      vlog "Found outdated pip packages"
      # Extract package names and upgrade them
      echo "$outdated" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for pkg in data:
        print(pkg['name'])
except:
    pass
" | while IFS= read -r pkg; do
        [ -z "$pkg" ] && continue
        run_cmd "Pip: Upgrade $pkg" python3 -m pip install --user --upgrade "$pkg"
      done
    fi
  else
    log "DRY-RUN: pip list --outdated and upgrade packages"
  fi

  log "Pip: Complete"
}

update_npm() {
  if ! detect_npm; then return; fi
  log "NPM: Updating global packages"

  # Update npm itself
  run_cmd "NPM: Self-update" npm install -g npm@latest

  # Update all global packages
  run_cmd "NPM: Upgrade global packages" npm update -g

  log "NPM: Complete"
}

update_pnpm() {
  if ! detect_pnpm; then return; fi
  log "PNPM: Updating global packages"

  # Update pnpm itself via corepack if available
  if command -v corepack >/dev/null 2>&1; then
    run_cmd "PNPM: Update via corepack" corepack prepare pnpm@latest --activate
  else
    run_cmd "PNPM: Self-update" npm install -g pnpm@latest
  fi

  # Update global packages
  run_cmd "PNPM: Upgrade global packages" pnpm update -g

  log "PNPM: Complete"
}

update_yarn() {
  if ! detect_yarn; then return; fi
  log "Yarn: Updating global packages"

  # Update yarn itself via corepack if available
  if command -v corepack >/dev/null 2>&1; then
    run_cmd "Yarn: Update via corepack" corepack prepare yarn@stable --activate
  else
    run_cmd "Yarn: Self-update" npm install -g yarn@latest
  fi

  # Yarn doesn't have a built-in global package upgrade command
  # Users typically manage this per-project
  vlog "Yarn: Global package upgrades managed per-project"

  log "Yarn: Complete"
}

update_go() {
  if ! detect_go; then return; fi
  log "Go: Updating installed binaries"

  # Go doesn't have a built-in package manager for updating binaries
  # List common go-installed tools and suggest updating
  local gobin gopath
  gobin="$(go env GOBIN 2>/dev/null || true)"
  gopath="$(go env GOPATH 2>/dev/null || true)"

  if [ -z "$gobin" ] && [ -n "$gopath" ]; then
    gobin="$gopath/bin"
  fi

  if [ -n "$gobin" ] && [ -d "$gobin" ]; then
    vlog "Go: Binaries in $gobin (manual upgrade needed: go install <package>@latest)"
    log "Go: Update via go install <package>@latest for each tool"
  fi

  log "Go: Manual updates required"
}

update_gem() {
  if ! detect_gem; then return; fi
  log "RubyGems: Updating all gems"

  run_cmd "Gem: Update system" gem update --system
  run_cmd "Gem: Upgrade all gems" gem update
  run_cmd "Gem: Cleanup old versions" gem cleanup

  log "RubyGems: Complete"
}

update_gcloud() {
  if ! detect_gcloud; then return; fi
  log "Google Cloud SDK: Updating components"

  run_cmd "gcloud: Update all components" gcloud components update --quiet

  log "Google Cloud SDK: Complete"
}

update_az() {
  if ! detect_az; then return; fi
  log "Azure CLI: Updating"

  # Azure CLI update method depends on installation type
  if command -v apt-get >/dev/null 2>&1 && dpkg -l azure-cli >/dev/null 2>&1; then
    # Installed via apt
    run_cmd "Azure CLI: Update via apt" sudo apt-get update && sudo apt-get install --only-upgrade -y azure-cli
  elif command -v brew >/dev/null 2>&1 && brew list azure-cli >/dev/null 2>&1; then
    # Installed via brew
    run_cmd "Azure CLI: Update via brew" brew upgrade azure-cli
  else
    # Try az upgrade command (available in az CLI 2.11.0+)
    run_cmd "Azure CLI: Self-upgrade" az upgrade --yes
  fi

  log "Azure CLI: Complete"
}

# ============================================================================
# Main Orchestration
# ============================================================================

get_manager_stats() {
  local mgr="$1"
  local location version pkg_count

  case "$mgr" in
    apt)
      location="$(command -v apt-get 2>/dev/null || echo "N/A")"
      version="$(apt-get --version 2>/dev/null | head -n1 | awk '{print $2}' || echo "unknown")"
      pkg_count="$(dpkg -l 2>/dev/null | grep '^ii' | wc -l || echo "0")"
      ;;
    brew)
      location="$(command -v brew 2>/dev/null || echo "N/A")"
      version="$(brew --version 2>/dev/null | head -n1 | awk '{print $2}' || echo "unknown")"
      pkg_count="$(brew list --formula 2>/dev/null | wc -l || echo "0")"
      ;;
    snap)
      location="$(command -v snap 2>/dev/null || echo "N/A")"
      version="$(snap version 2>/dev/null | grep '^snap' | awk '{print $2}' || echo "unknown")"
      pkg_count="$(snap list 2>/dev/null | tail -n +2 | wc -l || echo "0")"
      ;;
    flatpak)
      location="$(command -v flatpak 2>/dev/null || echo "N/A")"
      version="$(flatpak --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(flatpak list --app 2>/dev/null | wc -l || echo "0")"
      ;;
    cargo)
      location="$(command -v cargo 2>/dev/null || echo "N/A")"
      version="$(cargo --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(cargo install --list 2>/dev/null | grep -c '^[^ ]' || echo "0")"
      ;;
    rustup)
      location="$(command -v rustup 2>/dev/null || echo "N/A")"
      version="$(rustup --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(rustup toolchain list 2>/dev/null | wc -l || echo "0")"
      ;;
    uv)
      location="$(command -v uv 2>/dev/null || echo "N/A")"
      version="$(uv --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(uv tool list 2>/dev/null | wc -l || echo "0")"
      ;;
    pipx)
      location="$(command -v pipx 2>/dev/null || echo "N/A")"
      version="$(pipx --version 2>/dev/null || echo "unknown")"
      pkg_count="$(pipx list --short 2>/dev/null | wc -l || echo "0")"
      ;;
    pip)
      location="$(command -v pip3 2>/dev/null || command -v pip 2>/dev/null || echo "N/A")"
      version="$(python3 -m pip --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(python3 -m pip list --user 2>/dev/null | tail -n +3 | wc -l || echo "0")"
      ;;
    npm)
      location="$(command -v npm 2>/dev/null || echo "N/A")"
      version="$(npm --version 2>/dev/null || echo "unknown")"
      pkg_count="$(npm list -g --depth=0 2>/dev/null | grep -c '^[├└]' || echo "0")"
      ;;
    pnpm)
      location="$(command -v pnpm 2>/dev/null || echo "N/A")"
      version="$(pnpm --version 2>/dev/null || echo "unknown")"
      pkg_count="$(pnpm list -g --depth=0 2>/dev/null | grep -c '^[├└]' || echo "0")"
      ;;
    yarn)
      location="$(command -v yarn 2>/dev/null || echo "N/A")"
      version="$(yarn --version 2>/dev/null || echo "unknown")"
      pkg_count="$(yarn global list 2>/dev/null | grep -c '^info' || echo "0")"
      ;;
    go)
      location="$(command -v go 2>/dev/null || echo "N/A")"
      version="$(go version 2>/dev/null | awk '{print $3}' | sed 's/go//' || echo "unknown")"
      local gobin="$(go env GOBIN 2>/dev/null || echo "$(go env GOPATH 2>/dev/null)/bin")"
      pkg_count="$([ -d "$gobin" ] && ls -1 "$gobin" 2>/dev/null | wc -l || echo "0")"
      ;;
    gem)
      location="$(command -v gem 2>/dev/null || echo "N/A")"
      version="$(gem --version 2>/dev/null || echo "unknown")"
      pkg_count="$(gem list --no-versions 2>/dev/null | wc -l || echo "0")"
      ;;
    composer)
      location="$(command -v composer 2>/dev/null || echo "N/A")"
      version="$(composer --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")"
      pkg_count="$(composer global show 2>/dev/null | wc -l || echo "0")"
      ;;
    poetry)
      location="$(command -v poetry 2>/dev/null || echo "N/A")"
      version="$(poetry --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")"
      pkg_count="N/A"
      ;;
    conda)
      location="$(command -v conda 2>/dev/null || echo "N/A")"
      version="$(conda --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(conda list 2>/dev/null | tail -n +4 | wc -l || echo "0")"
      ;;
    mamba)
      location="$(command -v mamba 2>/dev/null || echo "N/A")"
      version="$(mamba --version 2>/dev/null | awk '{print $2}' || echo "unknown")"
      pkg_count="$(mamba list 2>/dev/null | tail -n +4 | wc -l || echo "0")"
      ;;
    bundler)
      location="$(command -v bundle 2>/dev/null || echo "N/A")"
      version="$(bundle --version 2>/dev/null | awk '{print $3}' || echo "unknown")"
      pkg_count="N/A"
      ;;
    jspm)
      location="$(command -v jspm 2>/dev/null || echo "N/A")"
      version="$(jspm --version 2>/dev/null || echo "unknown")"
      pkg_count="N/A"
      ;;
    nuget)
      if command -v nuget >/dev/null 2>&1; then
        location="$(command -v nuget)"
        version="$(nuget help 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")"
      else
        location="$(command -v dotnet 2>/dev/null || echo "N/A")"
        version="$(dotnet --version 2>/dev/null || echo "unknown")"
      fi
      pkg_count="N/A"
      ;;
    gcloud)
      location="$(command -v gcloud 2>/dev/null || echo "N/A")"
      version="$(gcloud version 2>/dev/null | grep 'Google Cloud SDK' | awk '{print $4}' || echo "unknown")"
      pkg_count="$(gcloud components list --filter='State.name:Installed' --format='value(id)' 2>/dev/null | wc -l || echo "0")"
      ;;
    az)
      location="$(command -v az 2>/dev/null || echo "N/A")"
      version="$(az version --output tsv 2>/dev/null | grep '^azure-cli' | awk '{print $2}' || echo "unknown")"
      pkg_count="$(az extension list 2>/dev/null | grep -c '"name":' || echo "0")"
      ;;
    *)
      location="unknown"
      version="unknown"
      pkg_count="0"
      ;;
  esac

  printf "%s|%s|%s" "$location" "$version" "$pkg_count"
}

show_detected() {
  log "Detecting installed package managers..."
  echo ""

  local managers=()
  local found=0

  # System package managers
  detect_apt && managers+=("apt") && found=$((found + 1)) || true
  detect_brew && managers+=("brew") && found=$((found + 1)) || true
  detect_snap && managers+=("snap") && found=$((found + 1)) || true
  detect_flatpak && managers+=("flatpak") && found=$((found + 1)) || true

  # Language-specific
  detect_rustup && managers+=("rustup") && found=$((found + 1)) || true
  detect_cargo && managers+=("cargo") && found=$((found + 1)) || true
  detect_uv && managers+=("uv") && found=$((found + 1)) || true
  detect_pipx && managers+=("pipx") && found=$((found + 1)) || true
  detect_pip && managers+=("pip") && found=$((found + 1)) || true
  detect_npm && managers+=("npm") && found=$((found + 1)) || true
  detect_pnpm && managers+=("pnpm") && found=$((found + 1)) || true
  detect_yarn && managers+=("yarn") && found=$((found + 1)) || true
  detect_go && managers+=("go") && found=$((found + 1)) || true
  detect_gem && managers+=("gem") && found=$((found + 1)) || true
  detect_composer && managers+=("composer") && found=$((found + 1)) || true
  detect_poetry && managers+=("poetry") && found=$((found + 1)) || true
  detect_conda && managers+=("conda") && found=$((found + 1)) || true
  detect_mamba && managers+=("mamba") && found=$((found + 1)) || true
  detect_bundler && managers+=("bundler") && found=$((found + 1)) || true
  detect_jspm && managers+=("jspm") && found=$((found + 1)) || true
  detect_nuget && managers+=("nuget") && found=$((found + 1)) || true

  # Cloud CLIs
  detect_gcloud && managers+=("gcloud") && found=$((found + 1)) || true
  detect_az && managers+=("az") && found=$((found + 1)) || true

  if [ $found -eq 0 ]; then
    echo "No package managers detected."
    return
  fi

  echo "Found $found package managers:"
  echo ""
  printf "%-12s %-8s %-8s %s\n" "MANAGER" "VERSION" "PACKAGES" "LOCATION"
  printf "%-12s %-8s %-8s %s\n" "-------" "-------" "--------" "--------"

  for mgr in "${managers[@]}"; do
    local stats location version pkg_count
    stats="$(get_manager_stats "$mgr")"
    IFS='|' read -r location version pkg_count <<< "$stats"
    printf "%-12s %-8s %-8s %s\n" "$mgr" "$version" "$pkg_count" "$location"
  done
  echo ""
}

run_all_updates() {
  log "Starting auto-update for all detected package managers"
  echo ""

  # System package managers (skip if requested)
  if [ "$SKIP_SYSTEM" = "0" ]; then
    update_apt
    update_brew
    update_snap
    update_flatpak
  else
    log "Skipping system package managers (SKIP_SYSTEM=1)"
  fi

  # Language-specific package managers
  update_cargo
  update_uv
  update_pipx
  update_pip
  update_npm
  update_pnpm
  update_yarn
  update_go
  update_gem

  # Cloud CLIs
  update_gcloud
  update_az

  echo ""
  log "Auto-update complete!"
}

# ============================================================================
# CLI Interface
# ============================================================================

usage() {
  cat <<EOF
Usage: $0 [OPTIONS] [COMMAND]

Auto-update all package managers and their packages.

Commands:
  detect    Show detected package managers (default)
  update    Run updates for all detected package managers
  apt       Update only APT packages
  brew      Update only Homebrew packages
  cargo     Update only Cargo packages (includes rustup components)
  uv        Update only UV tools
  pipx      Update only Pipx packages
  pip       Update only Pip packages
  npm       Update only NPM packages
  pnpm      Update only PNPM packages
  yarn      Update only Yarn packages
  go        Show Go update instructions
  gem       Update only RubyGems packages
  snap      Update only Snap packages
  flatpak   Update only Flatpak packages
  gcloud    Update Google Cloud SDK components
  az        Update Azure CLI

Options:
  --dry-run         Show what would be updated without making changes
  --verbose         Show detailed output
  --skip-system     Skip system package managers (apt, brew, snap, flatpak)
  -h, --help        Show this help message

Environment Variables:
  DRY_RUN=1         Enable dry-run mode
  VERBOSE=1         Enable verbose output
  SKIP_SYSTEM=1     Skip system package managers

Examples:
  $0 detect                    # List detected package managers
  $0 update                    # Update all package managers
  $0 --dry-run update          # Show what would be updated
  $0 cargo                     # Update only Cargo packages
  DRY_RUN=1 $0 update          # Dry-run via environment variable
  SKIP_SYSTEM=1 $0 update      # Skip system package managers

EOF
}

# Parse options
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --verbose)
      VERBOSE=1
      shift
      ;;
    --skip-system)
      SKIP_SYSTEM=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    detect)
      show_detected
      exit 0
      ;;
    update)
      run_all_updates
      exit 0
      ;;
    apt)
      update_apt
      exit 0
      ;;
    brew)
      update_brew
      exit 0
      ;;
    cargo)
      update_cargo
      exit 0
      ;;
    uv)
      update_uv
      exit 0
      ;;
    pipx)
      update_pipx
      exit 0
      ;;
    pip)
      update_pip
      exit 0
      ;;
    npm)
      update_npm
      exit 0
      ;;
    pnpm)
      update_pnpm
      exit 0
      ;;
    yarn)
      update_yarn
      exit 0
      ;;
    go)
      update_go
      exit 0
      ;;
    gem)
      update_gem
      exit 0
      ;;
    snap)
      update_snap
      exit 0
      ;;
    flatpak)
      update_flatpak
      exit 0
      ;;
    gcloud)
      update_gcloud
      exit 0
      ;;
    az)
      update_az
      exit 0
      ;;
    *)
      echo "Error: Unknown command '$1'" >&2
      echo "Run '$0 --help' for usage information." >&2
      exit 1
      ;;
  esac
done

# Default: show detected managers
show_detected
